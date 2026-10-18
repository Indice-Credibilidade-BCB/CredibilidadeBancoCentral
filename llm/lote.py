# -*- coding: utf-8 -*-
"""Pontuação EM LOTE (economia de tokens): várias notícias por chamada.

O prompt de sistema (~870 tokens) era 83% da entrada de cada chamada. Em lotes
de 10, ele é pago uma vez por lote: a entrada cai de ~1.050 para ~260 tokens
por notícia, e a saída compacta (`<n>|<d1>|<d2>|<d3>`) de ~26 para ~5.

Cuidados de desenho:
* lotes formados ao ACASO (semente fixa), misturando épocas e veículos — um
  lote de uma só época convidaria comparação dentro do contexto;
* ``separar_por``: coluna cujos valores não podem dividir o mesmo lote (no T5,
  os dois textos de um par sintético nunca vão juntos — seriam comparados);
* resposta incompleta: as notícias que faltarem viram erro e são refeitas na
  retomada (mesmo comando), em lotes novos.

Saída no MESMO schema do `scorer.py` (uma linha por notícia), com
``empacotamento = "lote<N>"`` e ``lote_id``; variante com sufixo ``|lote``.

Uso:
  python lote.py --provider sabia --input X.parquet --out Y.jsonl [--n 10]
                 [--date-mode omitida] [--anonimizacao L5] [--separar-por texto_grupo]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import time

import pandas as pd

import prompts
from providers import make_provider
from scorer import RateLimiter, _carregar_ja_feitos, cache_key, load_cfg

ROOT = pathlib.Path(__file__).parent
VERSAO = "v1.1"
# "S" e "-" são aceitos como "sem sinal" nas três dimensões: o sabiazinho troca
# um pelo outro com frequência (visto no teste de equivalência de 2026-10-18).
_SEM = r"S|s|-"
_LINHA = re.compile(rf"^\s*\[?#?\s*(?:TRECHO\s*)?(\d+)\]?\s*[|;,]\s*([1-5]|{_SEM})\s*[|;,]\s*([1-5]|{_SEM})"
                    rf"\s*[|;,]\s*([1-5]|{_SEM})\s*$")


def formar_lotes(df: pd.DataFrame, n: int, semente: int = 7,
                 separar_por: str | None = None) -> list[pd.DataFrame]:
    """Embaralha e corta em lotes de até ``n``. Com ``separar_por``, garante que
    um mesmo valor dessa coluna não apareça duas vezes no mesmo lote."""
    d = df.sample(frac=1, random_state=semente).reset_index(drop=True)
    if not separar_por:
        return [d.iloc[i:i + n] for i in range(0, len(d), n)]
    lotes: list[list[int]] = []
    vistos: list[set] = []
    for i, v in enumerate(d[separar_por]):
        for k, ids in enumerate(lotes):
            if len(ids) < n and v not in vistos[k]:
                ids.append(i); vistos[k].add(v); break
        else:
            lotes.append([i]); vistos.append({v})
    return [d.iloc[ids] for ids in lotes]


def parse_lote(texto: str, n_itens: int) -> dict[int, dict]:
    """``<n>|<d1>|<d2>|<d3>`` por linha -> {posição: {d1, d1_sem_sinal, d2, d3}}.
    Linhas malformadas ou posições fora de 1..n são ignoradas (viram erro)."""
    out: dict[int, dict] = {}
    for linha in (texto or "").splitlines():
        m = _LINHA.match(linha.strip().strip("`"))
        if not m:
            continue
        k = int(m.group(1))
        if not 1 <= k <= n_itens or k in out:
            continue
        nota = lambda g: None if g in ("S", "s", "-") else int(g)  # noqa: E731
        out[k] = {"d1": nota(m.group(2)), "d1_sem_sinal": nota(m.group(2)) is None,
                  "d2": nota(m.group(3)), "d3": nota(m.group(4))}
    return out


def pontuar(provider_name: str, df: pd.DataFrame, out_path: pathlib.Path, n: int = 10,
            date_mode: str = "real", anonimizacao: str = "nenhuma", separar_por: str | None = None,
            semente: int = 7, log_raw: pathlib.Path | None = None) -> dict:
    """Pontua ``df`` em lotes; retomável pelo mesmo ``cache_key`` do scorer."""
    from diagnostics.leakage import aplicar_anonimizacao

    cfg = load_cfg()
    pcfg = cfg["providers"][provider_name]
    # Saída limitada ao que as linhas do lote ocupam (~7 tokens por notícia):
    # o sabiazinho acrescenta "observações" depois das linhas, apesar do prompt,
    # e esse texto custaria tokens de saída sem uso.
    req = dict(cfg["request"], max_tokens=12 + 9 * n)
    provider = make_provider(provider_name, pcfg, req)
    limiter = RateLimiter(pcfg.get("rpm", 10), pcfg.get("rpd", 10**9),
                          ROOT / cfg["paths"]["cache_dir"] / f"rpd_{provider_name}.json")
    variante = f"producao|{date_mode}|{anonimizacao}|lote"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ja = _carregar_ja_feitos(out_path)
    base = aplicar_anonimizacao(df, anonimizacao) if anonimizacao != "nenhuma" else df
    base = base.assign(_ck=[cache_key(provider_name, provider.model, str(i), variante, VERSAO)
                            for i in base["item_id"]])
    pend = base[~base["_ck"].isin(ja)]
    lotes = formar_lotes(pend, n, semente, separar_por)
    cont = {"pendentes": len(pend), "lotes": len(lotes), "ok": 0, "faltou_no_lote": 0, "chamada_falhou": 0,
            "tokens_entrada_aprox": 0}
    raw_f = (log_raw or out_path.with_suffix(".raw.jsonl")).open("a", encoding="utf-8")
    with out_path.open("a", encoding="utf-8") as f:
        for lote in lotes:
            if not limiter.acquire():
                print("Teto diário (RPD) atingido — retome com o mesmo comando.")
                break
            itens = lote.to_dict("records")
            user = prompts.build_user_msg_lote(itens, date_mode=date_mode)
            cont["tokens_entrada_aprox"] += int((len(prompts.PROMPT_SISTEMA_LOTE_V11) + len(user)) / 3.6)
            texto, erro = None, None
            for tent in range(cfg["request"].get("max_retries", 5)):
                try:
                    texto = provider.complete(prompts.PROMPT_SISTEMA_LOTE_V11, user)
                    break
                except Exception as e:  # noqa: BLE001
                    erro = str(e)
                    time.sleep(min(2 ** tent * 5, 120))
            lote_id = hashlib.sha1("|".join(map(str, lote["item_id"])).encode()).hexdigest()[:12]
            raw_f.write(json.dumps({"lote_id": lote_id, "n": len(itens), "raw": texto, "erro": erro},
                                   ensure_ascii=False) + "\n")
            notas = parse_lote(texto, len(itens)) if texto else {}
            ts = dt.datetime.now().isoformat(timespec="seconds")
            for k, it in enumerate(itens, start=1):
                nota = notas.get(k)
                rec = {"cache_key": it["_ck"], "item_id": it["item_id"], "provider": provider_name,
                       "model": provider.model, "prompt_version": VERSAO,
                       "prompt_hash": prompts.PROMPT_HASH_V11_LOTE, "empacotamento": f"lote{n}",
                       "lote_id": lote_id, "posicao": k, "variante": variante, "variante_vazamento": None,
                       "ts": ts, "erro": None if nota else (erro or "faltou_no_lote"),
                       "d1": (nota or {}).get("d1"), "d1_sem_sinal": (nota or {}).get("d1_sem_sinal"),
                       "d2": (nota or {}).get("d2"), "d3": (nota or {}).get("d3")}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                cont["ok" if nota else ("chamada_falhou" if texto is None else "faltou_no_lote")] += 1
            f.flush(); raw_f.flush()
    raw_f.close()
    return cont


def reprocessar(out_path: pathlib.Path) -> dict:
    """Refaz o parse das respostas brutas já pagas (``<out>.raw.jsonl``) com o
    parser atual e regrava ``out_path``. Não chama a API."""
    raw = {}
    for l in out_path.with_suffix(".raw.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(l)
        if r.get("raw"):
            raw[r["lote_id"]] = r
    recs = [json.loads(l) for l in out_path.read_text(encoding="utf-8").splitlines()]
    antes = sum(r["erro"] is None for r in recs)
    for r in recs:
        if r["erro"] is None or r.get("lote_id") not in raw:
            continue
        nota = parse_lote(raw[r["lote_id"]]["raw"], raw[r["lote_id"]]["n"]).get(r["posicao"])
        if nota:
            r.update(nota); r["erro"] = None
    out_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
    return {"validos_antes": antes, "validos_depois": sum(r["erro"] is None for r in recs), "total": len(recs)}


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--date-mode", choices=["real", "omitida", "trocada"], default="real")
    ap.add_argument("--anonimizacao", choices=["nenhuma", "L1", "L2", "L3", "L4", "L5"], default="nenhuma")
    ap.add_argument("--separar-por", default=None)
    ap.add_argument("--semente", type=int, default=7)
    a = ap.parse_args()
    df = pd.read_csv(a.input) if a.input.endswith(".csv") else pd.read_parquet(a.input)
    r = pontuar(a.provider, df, pathlib.Path(a.out), a.n, a.date_mode, a.anonimizacao, a.separar_por, a.semente)
    print(json.dumps(r, ensure_ascii=False))

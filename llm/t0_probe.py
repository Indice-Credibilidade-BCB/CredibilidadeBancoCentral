# -*- coding: utf-8 -*-
"""T0 — roda a sonda de identificabilidade temporal nos 4 níveis da escada
(D11/4.2.3). Round-trip de API; a estatística pura vive em
`diagnostics/temporal_probe.py` (testável sem rede).

Uso:
  python t0_probe.py --provider sabia --input ../dados/llm/piloto/pilot_items.csv \
      --out ../dados/llm/piloto/t0_respostas.jsonl

Roda os 4 níveis (L1..L4) sobre a mesma amostra do piloto; ao final imprime
EAM e acurácia de episódio por nível e o NÍVEL MÍNIMO que atinge cegueira
(critério: EAM >= 4 anos E acurácia <= 0,25). Esse nível vira o V-min de
produção (D12) — cada nível é uma chamada extra por item, então isto roda
UMA VEZ no piloto, não em produção.

Reaproveita cache/rate-limit de scorer.py (mesmo desenho: free tier fatia o
job em vários dias; cache é checkpoint).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import time

import pandas as pd
import yaml

import prompts
from diagnostics.leakage import anonimizar
from diagnostics.temporal_probe import (NIVEIS_ESCADA, avaliar_t0,
                                        nivel_minimo_cego)
from providers import make_provider
from scorer import RateLimiter  # reaproveita a mesma infra de retomada/RPD

ROOT = pathlib.Path(__file__).parent


def _cache_key_t0(provider: str, model: str, item_id: str, nivel: str) -> str:
    raw = f"t0|{provider}|{model}|{prompts.PROMPT_VERSION}|{item_id}|{nivel}"
    return hashlib.sha1(raw.encode()).hexdigest()


def _parse_t0(texto: str) -> dict | None:
    """Extrai {"ano_estimado": <int>} da resposta (tolera cercas de markdown)."""
    t = re.sub(r"```(json)?", "", texto or "").strip()
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    ano = parsed.get("ano_estimado")
    return {"ano_estimado": ano} if isinstance(ano, (int, float)) else None


def rodar(provider_name: str, input_path: str, out_path: str,
         niveis: tuple = NIVEIS_ESCADA) -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    pcfg = cfg["providers"][provider_name]
    provider = make_provider(provider_name, pcfg, cfg["request"])

    cache_dir = ROOT / cfg["paths"]["cache_dir"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    limiter = RateLimiter(pcfg.get("rpm", 10), pcfg.get("rpd", 10**9),
                          cache_dir / f"rpd_t0_{provider_name}.json")

    df = pd.read_csv(input_path)
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    ja_feitos = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if rec.get("erro") is None and rec.get("ano_estimado") is not None:
                    ja_feitos.add(rec["cache_key"])
            except (json.JSONDecodeError, KeyError):
                pass

    with out.open("a", encoding="utf-8") as f:
        for nivel in niveis:
            for _, row in df.iterrows():
                ck = _cache_key_t0(provider_name, provider.model, str(row["item_id"]), nivel)
                if ck in ja_feitos:
                    continue
                if not limiter.acquire():
                    print("Teto diário (RPD) atingido — retome amanhã com o mesmo comando.")
                    return
                item = {k: anonimizar(row.get(k), nivel) if k in
                        ("titulo", "lead", "paragrafo_1") else row.get(k)
                        for k in ("veiculo", "titulo", "lead", "paragrafo_1")}
                user = prompts.build_user_msg_t0(item)
                texto, erro = None, None
                for tent in range(cfg["request"].get("max_retries", 5)):
                    try:
                        texto = provider.complete(prompts.PROMPT_SISTEMA_T0, user)
                        break
                    except Exception as e:  # noqa: BLE001
                        erro = str(e)
                        time.sleep(min(2 ** tent * 5, 120))
                parsed = _parse_t0(texto) if texto else None
                rec = {
                    "cache_key": ck, "item_id": row["item_id"], "nivel": nivel,
                    "provider": provider_name, "model": provider.model,
                    "data_publicacao_real": row["data_publicacao"],
                    "ano_estimado": (parsed or {}).get("ano_estimado"),
                    "erro": None if parsed else (erro or "parse_falhou"),
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
    print(f"Concluído: {out}")


def relatorio(jsonl_path: str) -> dict:
    recs = [json.loads(l) for l in
            pathlib.Path(jsonl_path).read_text(encoding="utf-8").splitlines()]
    df = pd.DataFrame(recs)
    resultados = {}
    for nivel, g in df.groupby("nivel"):
        r = avaliar_t0(g[["item_id", "ano_estimado", "data_publicacao_real"]])
        resultados[nivel] = r
        print(f"{nivel}: n={r['n']} EAM={r.get('eam', float('nan')):.2f} "
              f"acurácia={r.get('acuracia_episodio', float('nan')):.2f} "
              f"(taxa-base={r.get('taxa_base', float('nan')):.2f}) "
              f"cego={r.get('cego')}")
    minimo = nivel_minimo_cego(resultados)
    print(f"\nNível mínimo que cega o modelo: {minimo or 'NENHUM — T0 reprovou'}")
    return {"por_nivel": resultados, "nivel_minimo_vmin": minimo}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_rodar = sub.add_parser("rodar")
    p_rodar.add_argument("--provider", required=True)
    p_rodar.add_argument("--input", required=True)
    p_rodar.add_argument("--out", required=True)

    p_rel = sub.add_parser("relatorio")
    p_rel.add_argument("--respostas", required=True)

    a = ap.parse_args()
    if a.cmd == "rodar":
        rodar(a.provider, a.input, a.out)
    else:
        relatorio(a.respostas)

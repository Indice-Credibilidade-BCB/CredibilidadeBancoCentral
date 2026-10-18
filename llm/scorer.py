# -*- coding: utf-8 -*-
"""Pontuação em lote com free tiers.

Desenho (decisões travadas + extensões desta sessão):
  - 1 chamada por item, 3 dimensões, temperatura 0.
  - Cache JSONL por (provider, model, prompt_version, item_id, variante):
    o cache É o checkpoint — reexecutar retoma de onde parou. Essencial
    porque tetos diários (RPD) do free tier fatiam o corpus em vários dias.
  - Rate limiter: respeita RPM (intervalo mínimo) e RPD (contador diário
    persistido); ao bater o RPD, o job encerra limpo e retoma no dia seguinte.
  - Registro de proveniência em cada linha: provider, model, prompt_version,
    variante de data (real/omitida/trocada) e nível de anonimização.

Uso:
  python scorer.py --provider gemini_flash_lite --input data/piloto/pilot_items.csv \
      --mode piloto --out data/scores/pilot_gemini.jsonl
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
import yaml

import prompts
from providers import make_provider

ROOT = pathlib.Path(__file__).parent


def load_cfg() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def cache_key(provider: str, model: str, item_id: str, variante: str,
              versao: str | None = None) -> str:
    raw = f"{provider}|{model}|{versao or prompts.PROMPT_VERSION}|{item_id}|{variante}"
    return hashlib.sha1(raw.encode()).hexdigest()


def _campos_por_regex(bloco: str) -> dict | None:
    """Fallback para JSON malformado: extrai d1..d3 e os *_sem_sinal por regex.
    Exige ao menos o campo d1 (número ou null) para aceitar a resposta."""
    obj = {}
    for k in ("d1", "d2", "d3"):
        m = re.search(rf'"{k}"\s*:\s*(null|\d+(?:\.0)?)', bloco)
        if m:
            obj[k] = None if m.group(1) == "null" else int(float(m.group(1)))
    for k in ("d1_sem_sinal", "d2_sem_sinal", "d3_sem_sinal"):
        m = re.search(rf'"{k}"\s*:\s*(true|false)', bloco)
        if m:
            obj[k] = m.group(1) == "true"
    return obj if "d1" in obj else None


def parse_json_resposta(texto: str, versao: str | None = None) -> dict | None:
    """Extrai o primeiro objeto JSON da resposta (tolera cercas de markdown).

    v1.1: d1 nulo (ou d1_sem_sinal = true) é resposta VÁLIDA — o texto não
    traz sinal sobre a meta; d1 fica None e d1_sem_sinal = True.
    v1.0: comportamento original preservado (d1 nulo vira 3) para que a
    série do apêndice seja reproduzível."""
    versao = versao or prompts.PROMPT_VERSION
    texto = re.sub(r"```(json)?", "", texto).strip()
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        # O sabiazinho às vezes duplica aspas na chave (`""d1_sem_sinal": true`,
        # `" "d1_sem_sinal"`) — ~10% das respostas no teste da v1.1 com o
        # formato novo. O conteúdo é inequívoco: recupera os campos por regex.
        obj = _campos_por_regex(m.group(0))
        if obj is None:
            return None
    def _nota(v):
        """Aceita int ou float integral (modelos às vezes emitem 4.0)."""
        if isinstance(v, bool):
            return None
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return v if isinstance(v, int) and 1 <= v <= 5 else None

    d1_bruto = obj.get("d1")
    if versao != "v1.0":
        sem = obj.get("d1_sem_sinal") is True or d1_bruto is None
        if sem:
            obj["d1"], obj["d1_sem_sinal"] = None, True
        else:
            obj["d1"], obj["d1_sem_sinal"] = _nota(d1_bruto), False
            if obj["d1"] is None:
                return None
        for k in ("d2", "d3"):
            obj[k] = _nota(obj.get(k))
        return obj
    if d1_bruto is None:
        # D1 nunca deveria ser nulo (D4: corpus já filtrado por relevância;
        # "sem sinal claro" já tem representação própria — nota 3). Na
        # prática, o Sabiá às vezes devolve d1=null mesmo assim quando não
        # vê nenhuma menção ao BCB/meta no texto (visto na pontuação-piloto:
        # ~40% dos itens numa amostra pequena). Em vez de descartar o item
        # inteiro como falha de parse — perdendo o dado e gastando retry —
        # trata como o "3 = neutro" que o próprio prompt já define.
        obj["d1"] = 3
    else:
        obj["d1"] = _nota(d1_bruto)
        if obj["d1"] is None:
            return None
    for k in ("d2", "d3"):
        obj[k] = _nota(obj.get(k))
    return obj


class RateLimiter:
    def __init__(self, rpm: int, rpd: int, state_path: pathlib.Path):
        self.min_interval = 60.0 / max(rpm, 1)
        self.rpd = rpd
        self.state_path = state_path
        self._last = 0.0
        self._hoje, self._count = self._load()

    def _load(self):
        if self.state_path.exists():
            st = json.loads(self.state_path.read_text())
            return st.get("dia"), st.get("count", 0)
        return None, 0

    def _save(self):
        self.state_path.write_text(json.dumps({"dia": self._hoje, "count": self._count}))

    def acquire(self) -> bool:
        dia = dt.date.today().isoformat()
        if dia != self._hoje:
            self._hoje, self._count = dia, 0
        if self._count >= self.rpd:
            return False  # teto diário: encerrar limpo e retomar amanhã
        espera = self.min_interval - (time.time() - self._last)
        if espera > 0:
            time.sleep(espera)
        self._last = time.time()
        self._count += 1
        self._save()
        return True


def _carregar_ja_feitos(out: pathlib.Path) -> set:
    """Retomada: só pula itens que já têm escore VÁLIDO; linhas com erro
    (parse_falhou, exceção de rede) são reprocessadas na reexecução."""
    ja_feitos = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if rec.get("erro") is None and (rec.get("d1") is not None
                                                or rec.get("d1_sem_sinal") is True):
                    ja_feitos.add(rec["cache_key"])
            except (json.JSONDecodeError, KeyError):
                pass
    return ja_feitos


def _rodar_passada(df: pd.DataFrame, cfg: dict, provider, provider_name: str,
                   system: str, date_mode: str, variante: str,
                   variante_vazamento: str | None, limiter: "RateLimiter",
                   ja_feitos: set, out_handle, versao: str | None = None) -> bool:
    """Roda uma passada de pontuação (um valor de anonimização) sobre `df`,
    já mascarado como esta passada exige. Retorna False se o teto diário foi
    atingido no meio da passada (chamador deve encerrar)."""
    for _, row in df.iterrows():
        versao = versao or prompts.PROMPT_VERSION
        ck = cache_key(provider_name, provider.model, str(row["item_id"]), variante, versao)
        if ck in ja_feitos:
            continue
        if not limiter.acquire():
            print("Teto diário (RPD) atingido — retome amanhã com o mesmo comando.")
            return False
        user = prompts.build_user_msg(row.to_dict(), date_mode=date_mode,
                                      data_falsa=row.get("data_falsa"))
        texto, erro = None, None
        for tent in range(cfg["request"].get("max_retries", 5)):
            try:
                texto = provider.complete(system, user)
                break
            except Exception as e:  # noqa: BLE001 — backoff genérico p/ 429/5xx
                erro = str(e)
                time.sleep(min(2 ** tent * 5, 120))
        parsed = parse_json_resposta(texto, versao) if texto else None
        rec = {
            "cache_key": ck,
            "item_id": row["item_id"],
            "provider": provider_name,
            "model": provider.model,
            "prompt_version": versao,
            "prompt_hash": prompts.VERSOES[versao]["hash"],  # D13: congelamento verificável
            "variante": variante,
            "variante_vazamento": variante_vazamento,  # "vmax"/"vmin"/None (D12)
            "ts": dt.datetime.now().isoformat(timespec="seconds"),
            "raw": texto,
            "erro": None if parsed else (erro or "parse_falhou"),
            **{k: (parsed or {}).get(k) for k in
               ("d1", "d1_sem_sinal", "d2", "d3", "d2_sem_sinal", "d3_sem_sinal", "justificativa")},
        }
        out_handle.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out_handle.flush()
        ja_feitos.add(ck)
    return True


def score_batch(provider_name: str, input_path: str, mode: str, out_path: str,
                date_mode: str = "real", anonimizacao: str = "nenhuma",
                dupla_vmax_vmin: bool = False, nivel_vmin: str = "L2",
                prompt_versao: str | None = None) -> None:
    """Pontua o corpus. `dupla_vmax_vmin` (D12/pendência 5) roda CADA item
    duas vezes na mesma passagem — uma com `anonimizacao` (V-max, tipicamente
    "nenhuma": texto integral) e outra forçada no `nivel_vmin` (o nível
    mínimo que T0 comprovou cegar o modelo, ver t0_probe.py) — e grava as
    duas no mesmo arquivo, distinguidas por sufixo `|vmax`/`|vmin` na chave
    de cache e pelo campo `variante_vazamento`. `aggregate.py` separa as duas
    séries e publica Δt = c_llm_vmax - c_llm_vmin. Dobra as chamadas de API;
    custo é irrelevante mesmo para o corpus inteiro (D5).
    Sem `dupla_vmax_vmin` (uso normal fora do diagnóstico de vazamento), o
    comportamento e a chave de cache são IDÊNTICOS aos de antes — não invalida
    cache já coletado."""
    cfg = load_cfg()
    pcfg = cfg["providers"][provider_name]
    provider = make_provider(provider_name, pcfg, cfg["request"])
    versao = prompt_versao or prompts.PROMPT_VERSION
    textos = prompts.VERSOES[versao]
    system = textos["piloto"] if mode == "piloto" else textos["producao"]

    cache_dir = ROOT / cfg["paths"]["cache_dir"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    limiter = RateLimiter(pcfg.get("rpm", 10), pcfg.get("rpd", 10**9),
                          cache_dir / f"rpd_{provider_name}.json")

    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    ja_feitos = _carregar_ja_feitos(out)

    df_base = (pd.read_csv(input_path) if input_path.endswith(".csv")
              else pd.read_parquet(input_path))

    from diagnostics.leakage import aplicar_anonimizacao

    if dupla_vmax_vmin:
        passadas = [("vmax", anonimizacao), ("vmin", nivel_vmin)]
    else:
        passadas = [(None, anonimizacao)]

    with out.open("a", encoding="utf-8") as f:
        for rotulo, nivel in passadas:
            df = aplicar_anonimizacao(df_base, nivel) if nivel != "nenhuma" else df_base
            variante = f"{mode}|{date_mode}|{nivel}"
            if dupla_vmax_vmin:
                variante += f"|{rotulo}"  # sufixo de variante (pendência 5)
            continuar = _rodar_passada(df, cfg, provider, provider_name, system,
                                       date_mode, variante, rotulo, limiter,
                                       ja_feitos, f, versao)
            if not continuar:
                return
    print(f"Concluído: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--mode", choices=["piloto", "producao"], default="piloto")
    ap.add_argument("--out", required=True)
    ap.add_argument("--date-mode", choices=["real", "omitida", "trocada"], default="real")
    ap.add_argument("--anonimizacao", choices=["nenhuma", "L1", "L2", "L3", "L4", "L5"],
                    default="nenhuma")
    ap.add_argument("--dupla-vmax-vmin", action="store_true",
                    help="D12: pontua cada item 2x (texto integral + nivel-vmin) "
                         "no mesmo arquivo, distinguido por variante_vazamento")
    ap.add_argument("--nivel-vmin", choices=["L1", "L2", "L3", "L4", "L5"], default="L2",
                    help="nível aprovado no T0 (t0_probe.py) para a variante V-min")
    ap.add_argument("--prompt-versao", choices=sorted(prompts.VERSOES), default=prompts.PROMPT_VERSION,
                    help="versão do prompt (padrão: a corrente; v1.0 reproduz a série do apêndice)")
    a = ap.parse_args()
    score_batch(a.provider, a.input, a.mode, a.out, a.date_mode, a.anonimizacao,
               a.dupla_vmax_vmin, a.nivel_vmin, a.prompt_versao)

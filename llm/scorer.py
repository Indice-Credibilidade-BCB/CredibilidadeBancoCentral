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


def cache_key(provider: str, model: str, item_id: str, variante: str) -> str:
    raw = f"{provider}|{model}|{prompts.PROMPT_VERSION}|{item_id}|{variante}"
    return hashlib.sha1(raw.encode()).hexdigest()


def parse_json_resposta(texto: str) -> dict | None:
    """Extrai o primeiro objeto JSON da resposta (tolera cercas de markdown)."""
    texto = re.sub(r"```(json)?", "", texto).strip()
    m = re.search(r"\{.*\}", texto, re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    def _nota(v):
        """Aceita int ou float integral (modelos às vezes emitem 4.0)."""
        if isinstance(v, bool):
            return None
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        return v if isinstance(v, int) and 1 <= v <= 5 else None

    obj["d1"] = _nota(obj.get("d1"))
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


def score_batch(provider_name: str, input_path: str, mode: str, out_path: str,
                date_mode: str = "real", anonimizacao: str = "nenhuma") -> None:
    cfg = load_cfg()
    pcfg = cfg["providers"][provider_name]
    provider = make_provider(provider_name, pcfg, cfg["request"])
    system = (prompts.PROMPT_SISTEMA_PILOTO if mode == "piloto"
              else prompts.PROMPT_SISTEMA_PRODUCAO)

    cache_dir = ROOT / cfg["paths"]["cache_dir"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    limiter = RateLimiter(pcfg.get("rpm", 10), pcfg.get("rpd", 10**9),
                          cache_dir / f"rpd_{provider_name}.json")

    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Retomada: só pula itens que já têm escore VÁLIDO; linhas com erro
    # (parse_falhou, exceção de rede) são reprocessadas na reexecução.
    ja_feitos = set()
    if out.exists():
        for line in out.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                if rec.get("erro") is None and rec.get("d1") is not None:
                    ja_feitos.add(rec["cache_key"])
            except (json.JSONDecodeError, KeyError):
                pass

    df = (pd.read_csv(input_path) if input_path.endswith(".csv")
          else pd.read_parquet(input_path))
    if anonimizacao != "nenhuma":
        # Aplica a máscara DE FATO ao corpo do texto (título/lead/1º§).
        # Sem isto a flag seria só proveniência — e o T3 rodaria inválido
        # com texto original rotulado como anonimizado.
        from diagnostics.leakage import aplicar_anonimizacao
        df = aplicar_anonimizacao(df, anonimizacao)
    variante = f"{mode}|{date_mode}|{anonimizacao}"

    with out.open("a", encoding="utf-8") as f:
        for _, row in df.iterrows():
            ck = cache_key(provider_name, provider.model, str(row["item_id"]), variante)
            if ck in ja_feitos:
                continue
            if not limiter.acquire():
                print("Teto diário (RPD) atingido — retome amanhã com o mesmo comando.")
                return
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
            parsed = parse_json_resposta(texto) if texto else None
            rec = {
                "cache_key": ck,
                "item_id": row["item_id"],
                "provider": provider_name,
                "model": provider.model,
                "prompt_version": prompts.PROMPT_VERSION,
                "variante": variante,
                "ts": dt.datetime.now().isoformat(timespec="seconds"),
                "raw": texto,
                "erro": None if parsed else (erro or "parse_falhou"),
                **{k: (parsed or {}).get(k) for k in
                   ("d1", "d2", "d3", "d2_sem_sinal", "d3_sem_sinal", "justificativa")},
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
    print(f"Concluído: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--mode", choices=["piloto", "producao"], default="piloto")
    ap.add_argument("--out", required=True)
    ap.add_argument("--date-mode", choices=["real", "omitida", "trocada"], default="real")
    ap.add_argument("--anonimizacao", choices=["nenhuma", "L1", "L2", "L3"],
                    default="nenhuma")
    a = ap.parse_args()
    score_batch(a.provider, a.input, a.mode, a.out, a.date_mode, a.anonimizacao)

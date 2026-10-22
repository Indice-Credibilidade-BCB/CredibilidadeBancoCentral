# -*- coding: utf-8 -*-
"""Pontuação pelo Batch API do Gemini (metade do preço, resposta em até 24 h).

O instrumento é o MESMO da chamada individual (providers/gemini.py e
scorer.py): mesmo modelo, prompt de sistema v1.1 de produção, mensagem do
usuário, temperatura, teto de tokens e saída em JSON. As notas saem no
formato do scorer.py, com a mesma cache_key, então o resto do pipeline
(_validos, consolidar) não distingue lote de chamada individual.

``pontuar`` não bloqueia: recolhe os lotes prontos, grava as notas e envia
um lote novo com o que ainda falta. Chamar de novo até ``em_lote`` zerar.
Estado dos lotes em ``<pasta do out>/lotes_gemini.json``.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib

import pandas as pd
import requests

import prompts
from scorer import cache_key, load_cfg, parse_json_resposta

API = "https://generativelanguage.googleapis.com"
VARIANTE = "producao|real|nenhuma"
VERSAO = "v1.1"
# O nível 1 de faturamento limita os tokens em lotes na fila: 10 mil notícias
# (~10 M tokens) deram 429 ao criar o lote; 5,4 mil passaram. Um lote de 3 mil
# por vez, e o próximo só quando o anterior termina.
MAX_POR_LOTE = 3_000
MAX_EM_VOO = 1
FINAIS_OK = {"BATCH_STATE_SUCCEEDED", "JOB_STATE_SUCCEEDED"}
FINAIS_FALHA = {"BATCH_STATE_FAILED", "BATCH_STATE_CANCELLED", "BATCH_STATE_EXPIRED",
                "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}


def _chave() -> dict:
    return {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}


def _carregar_env() -> None:
    env = pathlib.Path(__file__).resolve().parent / ".env"
    if "GEMINI_API_KEY" not in os.environ and env.exists():
        for linha in env.read_text(encoding="utf-8").splitlines():
            linha = linha.strip().removeprefix("export ").strip()
            if linha.startswith("GEMINI_API_KEY="):
                os.environ["GEMINI_API_KEY"] = linha.split("=", 1)[1].strip().strip('"').strip("'")


def requisicao(row: dict, pcfg: dict, req: dict) -> dict:
    """Corpo idêntico ao de GeminiProvider.complete."""
    system = prompts.VERSOES[VERSAO]["producao"]
    user = prompts.build_user_msg(row, date_mode="real", data_falsa=row.get("data_falsa"))
    corpo = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "temperature": req.get("temperature", 0.0),
            "maxOutputTokens": req.get("max_tokens", 200),
            "responseMimeType": "application/json",
        },
    }
    if pcfg.get("thinking_budget") is not None:
        corpo["generationConfig"]["thinkingConfig"] = {"thinkingBudget": pcfg["thinking_budget"]}
    return corpo


def _enviar_arquivo(linhas: list[str], nome: str) -> str:
    dados = ("\n".join(linhas) + "\n").encode("utf-8")
    r = requests.post(f"{API}/upload/v1beta/files", headers={
        **_chave(), "X-Goog-Upload-Protocol": "resumable", "X-Goog-Upload-Command": "start",
        "X-Goog-Upload-Header-Content-Length": str(len(dados)),
        "X-Goog-Upload-Header-Content-Type": "application/jsonl", "Content-Type": "application/json"},
        json={"file": {"display_name": nome}}, timeout=60)
    r.raise_for_status()
    url = r.headers["x-goog-upload-url"]
    r = requests.post(url, headers={"X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize",
                                    "Content-Length": str(len(dados))}, data=dados, timeout=600)
    r.raise_for_status()
    return r.json()["file"]["name"]


def _criar_lote(modelo: str, arquivo: str, nome: str) -> str:
    r = requests.post(f"{API}/v1beta/models/{modelo}:batchGenerateContent", headers=_chave(),
                      json={"batch": {"display_name": nome, "input_config": {"file_name": arquivo}}}, timeout=60)
    if not r.ok:
        raise RuntimeError(f"Gemini batch {r.status_code}: {r.text[:300]}")
    return r.json()["name"]


def _achar(obj, chave):
    """Primeiro valor de `chave` em qualquer nível (a resposta é uma operação)."""
    if isinstance(obj, dict):
        if chave in obj:
            return obj[chave]
        for v in obj.values():
            achado = _achar(v, chave)
            if achado is not None:
                return achado
    return None


def _estado(nome: str) -> dict:
    r = requests.get(f"{API}/v1beta/{nome}", headers=_chave(), timeout=60)
    r.raise_for_status()
    return r.json()


def _baixar(arquivo: str) -> list[dict]:
    r = requests.get(f"{API}/download/v1beta/{arquivo}:download", params={"alt": "media"},
                     headers=_chave(), timeout=600)
    r.raise_for_status()
    return [json.loads(l) for l in r.text.splitlines() if l.strip()]


def _registro(provider: str, modelo: str, item_id: str, resp: dict | None, erro: str | None, lote: str) -> dict:
    texto = None
    if resp is not None:
        try:
            texto = resp["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            fr = ((resp.get("candidates") or [{}])[0] or {}).get("finishReason")
            erro = erro or f"sem texto (finishReason={fr})"
    parsed = parse_json_resposta(texto, VERSAO) if texto else None
    return {
        "cache_key": cache_key(provider, modelo, item_id, VARIANTE, VERSAO),
        "item_id": item_id, "provider": provider, "model": modelo,
        "prompt_version": VERSAO, "prompt_hash": prompts.VERSOES[VERSAO]["hash"],
        "variante": VARIANTE, "variante_vazamento": None,
        "ts": dt.datetime.now().isoformat(timespec="seconds"), "raw": texto, "lote": lote,
        "erro": None if parsed else (erro or "parse_falhou"),
        **{k: (parsed or {}).get(k) for k in
           ("d1", "d1_sem_sinal", "d2", "d3", "d2_sem_sinal", "d3_sem_sinal", "justificativa")},
    }


def _feitos(out: pathlib.Path) -> set:
    if not out.exists():
        return set()
    s = pd.read_json(out, lines=True)
    if not len(s):
        return set()
    ok = s["erro"].isna() & (s["d1"].notna() | s["d1_sem_sinal"].eq(True))
    return set(s.loc[ok, "item_id"].astype(str))


def _esgotados(out: pathlib.Path, max_tentativas: int = 2) -> set:
    """Notícias que já voltaram com erro `max_tentativas` vezes: não são reenviadas."""
    if not out.exists():
        return set()
    s = pd.read_json(out, lines=True)
    if not len(s):
        return set()
    n = s[s["erro"].notna()].groupby(s["item_id"].astype(str)).size()
    return set(n[n >= max_tentativas].index)


def pontuar(provider: str, df: pd.DataFrame, out: pathlib.Path) -> dict:
    _carregar_env()
    out = pathlib.Path(out).resolve()
    cfg = load_cfg()
    pcfg, req = cfg["providers"][provider], cfg["request"]
    modelo = pcfg["model"]
    estado_path = out.parent / "lotes_gemini.json"
    lotes = json.loads(estado_path.read_text(encoding="utf-8")) if estado_path.exists() else []
    salvar = lambda: estado_path.write_text(json.dumps(lotes, indent=1), encoding="utf-8")  # noqa: E731

    # 1) recolhe o que ficou pronto
    for lt in (x for x in lotes if x["status"] == "enviado"):
        info = _estado(lt["nome"])
        st = _achar(info, "state")
        lt["estado"] = st
        if st in FINAIS_OK:
            arq = _achar(info, "responsesFile")
            linhas = _baixar(arq) if arq else []
            # cada lote grava no próprio destino (rotulagem e roteamento dividem o estado)
            with pathlib.Path(lt.get("out", out)).open("a", encoding="utf-8") as f:
                for l in linhas:
                    erro = json.dumps(l["error"])[:300] if l.get("error") else None
                    f.write(json.dumps(_registro(provider, modelo, l["key"], l.get("response"), erro, lt["nome"]),
                                       ensure_ascii=False) + "\n")
            lt["status"], lt["recebidas"] = "recolhido", len(linhas)
        elif st in FINAIS_FALHA:
            lt["status"] = "falhou"
        salvar()

    # 2) envia o que falta (fora de lote em andamento e sem nota válida)
    em_voo = {k for x in lotes if x["status"] == "enviado" and x.get("out", str(out)) == str(out) for k in x["ids"]}
    feitos = _feitos(out)
    falta = df[~df["item_id"].astype(str).isin(feitos | em_voo | _esgotados(out))]
    vagas = MAX_EM_VOO - sum(1 for x in lotes if x["status"] == "enviado")
    for ini in range(0, min(len(falta), max(vagas, 0) * MAX_POR_LOTE), MAX_POR_LOTE):
        bloco = falta.iloc[ini:ini + MAX_POR_LOTE]
        linhas = [json.dumps({"key": str(r["item_id"]), "request": requisicao(r, pcfg, req)}, ensure_ascii=False)
                  for r in bloco.to_dict("records")]
        nome = f"credibilidade-{out.stem}-{dt.datetime.now():%Y%m%d-%H%M%S}-{ini}"
        arquivo = _enviar_arquivo(linhas, nome)
        try:
            nome_lote = _criar_lote(modelo, arquivo, nome)
        except RuntimeError as e:
            if "429" not in str(e):
                raise
            print(f"Gemini: cota de lote cheia, fica para a próxima chamada ({str(e)[:80]})")
            break
        lotes.append({"nome": nome_lote, "arquivo": arquivo, "status": "enviado",
                      "out": str(out),
                      "enviado_em": dt.datetime.now().isoformat(timespec="seconds"),
                      "ids": bloco["item_id"].astype(str).tolist()})
        salvar()
    em_voo = {k for x in lotes if x["status"] == "enviado" for k in x["ids"]}
    feitos = _feitos(out)
    pedidos = set(df["item_id"].astype(str))
    return {"pedidos": len(pedidos), "validos": len(pedidos & feitos),
            "em_lote": len(pedidos & em_voo) or (len(pedidos - feitos) if len(falta) else 0),
            "lotes": [(x["nome"], x["status"], x.get("estado")) for x in lotes[-5:]]}

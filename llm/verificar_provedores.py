# -*- coding: utf-8 -*-
"""Confere, para cada provedor de config.yaml, se a variável de ambiente da
chave está definida e se ela de fato autentica — com UMA chamada mínima e
barata, não a pontuação de verdade.

Existe porque "a chave está definida" e "a chave funciona" são coisas
diferentes: chave revogada, digitada errada, ou pedido de créditos
acadêmicos da Maritaca ainda não aprovado dão erro só na primeira chamada
real do scorer, potencialmente já em produção. Rodar isto antes resolve.

Uso:
  python verificar_provedores.py                # todos os provedores do config
  python verificar_provedores.py --provider sabia claude
"""
from __future__ import annotations

import argparse
import os

import yaml

from providers import make_provider

PERGUNTA_MINIMA = "Responda apenas com o número 1."


def verificar_um(nome: str, cfg: dict, request_cfg: dict) -> dict:
    key_env = cfg.get("api_key_env")
    if key_env and not os.environ.get(key_env):
        return {"provedor": nome, "status": "SEM CHAVE",
                "detalhe": f"variável de ambiente {key_env} não definida"}
    try:
        provider = make_provider(nome, cfg, request_cfg)
    except Exception as e:  # noqa: BLE001
        return {"provedor": nome, "status": "ERRO AO CONSTRUIR",
                "detalhe": f"{type(e).__name__}: {e}"}
    try:
        resposta = provider.complete("Você responde de forma direta e curta.",
                                     PERGUNTA_MINIMA)
        return {"provedor": nome, "status": "OK",
                "detalhe": f"modelo={provider.model} resposta={resposta[:40]!r}"}
    except Exception as e:  # noqa: BLE001
        return {"provedor": nome, "status": "FALHOU NA CHAMADA",
                "detalhe": f"{type(e).__name__}: {e}"}


def verificar(provedores: list[str] | None = None) -> list[dict]:
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    nomes = provedores or list(cfg["providers"].keys())
    resultados = []
    for nome in nomes:
        if nome not in cfg["providers"]:
            resultados.append({"provedor": nome, "status": "DESCONHECIDO",
                               "detalhe": "não está em config.yaml"})
            continue
        r = verificar_um(nome, cfg["providers"][nome], cfg["request"])
        resultados.append(r)
        # marcador ASCII, não símbolo unicode: console Windows em cp1252
        # (comum em pt-BR/en-US) derruba o script no meio da checagem — o
        # mesmo motivo que tira "κ" dos prints de local_encoder/train.py.
        marca = {"OK": "OK", "SEM CHAVE": "--"}.get(r["status"], "X")
        print(f"  [{marca:2}] {r['provedor']:16} {r['status']:20} {r['detalhe']}")
    return resultados


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", nargs="*", default=None,
                    help="nomes de provedores em config.yaml; default: todos")
    a = ap.parse_args()
    verificar(a.provider)

# -*- coding: utf-8 -*-
"""Camada de abstração de provedores.

Contrato: um provedor recebe (system, user) e devolve o texto bruto da resposta.
Trocar de modelo/provedor = mudar config.yaml; o resto do pipeline não muda.
O par (provider_name, model, prompt_version) é registrado em cada escore para
reprodutibilidade e para tratar migrações como quebra estrutural.
"""
from __future__ import annotations

import abc
import os


class ProviderBase(abc.ABC):
    kind = "base"

    def __init__(self, name: str, cfg: dict, request_cfg: dict):
        self.name = name
        self.cfg = cfg
        self.request_cfg = request_cfg
        self.model = cfg["model"]
        key_env = cfg.get("api_key_env")
        self.api_key = os.environ.get(key_env, "") if key_env else ""
        if not self.api_key:
            raise RuntimeError(f"Defina a variável de ambiente {key_env} para {name}")

    @abc.abstractmethod
    def complete(self, system: str, user: str) -> str:
        """Retorna o texto bruto da resposta do modelo."""


def make_provider(name: str, cfg: dict, request_cfg: dict) -> ProviderBase:
    from .anthropic_provider import AnthropicProvider
    from .gemini import GeminiProvider
    from .openai_compat import OpenAICompatProvider

    kinds = {"gemini": GeminiProvider, "openai_compat": OpenAICompatProvider,
             "anthropic": AnthropicProvider}
    return kinds[cfg["kind"]](name, cfg, request_cfg)

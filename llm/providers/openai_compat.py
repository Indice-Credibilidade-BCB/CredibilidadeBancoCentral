# -*- coding: utf-8 -*-
"""Provedor OpenAI-compatible.

Cobre, com um único cliente:
  - Maritaca (Sabiá):  base_url https://chat.maritaca.ai/api
  - Groq (Llama etc.): base_url https://api.groq.com/openai/v1
"""
from __future__ import annotations

import requests

from .base import ProviderBase


class OpenAICompatProvider(ProviderBase):
    kind = "openai_compat"

    def complete(self, system: str, user: str) -> str:
        url = self.cfg["base_url"].rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.request_cfg.get("temperature", 0.0),
            "max_tokens": self.request_cfg.get("max_tokens", 200),
        }
        r = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=self.request_cfg.get("timeout_s", 60),
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

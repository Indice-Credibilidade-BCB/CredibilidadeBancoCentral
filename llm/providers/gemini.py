# -*- coding: utf-8 -*-
"""Provedor Gemini (REST v1beta, chave do AI Studio — free tier)."""
from __future__ import annotations

import requests

from .base import ProviderBase


class GeminiProvider(ProviderBase):
    kind = "gemini"

    def complete(self, system: str, user: str) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self.request_cfg.get("temperature", 0.0),
                "maxOutputTokens": self.request_cfg.get("max_tokens", 200),
                "responseMimeType": "application/json",
            },
        }
        tb = self.cfg.get("thinking_budget")
        if tb is not None:  # 2.5: "pensamento" consome maxOutputTokens
            payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": tb}
        r = requests.post(
            url,
            json=payload,
            headers={"x-goog-api-key": self.api_key},
            timeout=self.request_cfg.get("timeout_s", 60),
        )
        r.raise_for_status()
        data = r.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            fr = (data.get("candidates") or [{}])[0].get("finishReason")
            raise RuntimeError(f"Gemini sem texto (finishReason={fr}; "
                               f"bloqueio de segurança ou teto de tokens)")

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
        if not r.ok:
            # r.raise_for_status() sozinho só dá "429 Client Error: Too Many
            # Requests for url: ..." -- sem a mensagem de verdade. Visto na
            # prática: um 429 de "Your prepayment credits are depleted"
            # ficou indistinguível de rate-limit comum por 16h, retentando
            # à toa sem que ninguém percebesse a causa real a tempo.
            try:
                detalhe = r.json().get("error", {}).get("message", r.text[:300])
            except ValueError:
                detalhe = r.text[:300]
            raise RuntimeError(f"Gemini {r.status_code}: {detalhe}")
        data = r.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError):
            fr = (data.get("candidates") or [{}])[0].get("finishReason")
            raise RuntimeError(f"Gemini sem texto (finishReason={fr}; "
                               f"bloqueio de segurança ou teto de tokens)")

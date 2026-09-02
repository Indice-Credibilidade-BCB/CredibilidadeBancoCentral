# -*- coding: utf-8 -*-
"""Provedor Anthropic (Claude), via SDK oficial `anthropic`.

Não é free-tier (D5 é "free-first", não "free-only"): entra como quarta
medida independente do piloto — ao lado de Sabiá, Gemini Flash-Lite e Groq
Llama — para a tese de robustez à troca de modelo (D5), e como candidato a
"juiz" de maior capacidade para desempate/validação cruzada em itens onde os
três provedores free divergem muito. Custo é trivial para o corpus inteiro
(ver D5: ordem de R$100-150 mesmo no modelo mais caro da família).

Notas de implementação (ver skill claude-api para o porquê de cada uma):
  - Usa o SDK oficial (`anthropic.Anthropic`), não requests cru.
  - A partir de Claude Opus 5, "thinking" vem ligado por padrão (adaptativo)
    e os parâmetros de amostragem (temperature/top_p/top_k) são REMOVIDOS —
    `messages.create()` nem aceita `temperature` (TypeError na SDK, não um
    400 do servidor). Por isso este provedor, ao contrário dos outros
    (que usam `request.temperature=0.0` do config para determinismo), não
    passa temperatura nenhuma. O determinismo aqui vem de `effort` baixo +
    prompt restrito, não de amostragem — diferença estrutural registrada
    também no README, para não confundir quem comparar as saídas.
  - Blocos de pensamento não fazem parte da resposta; extraímos só o
    primeiro bloco de texto. `effort` é configurável (default "low": tarefa
    é classificação, não raciocínio longo — ver guidance da skill).
  - `max_tokens` do config.yaml (request.max_tokens=300) é baixo demais
    quando thinking está ativo por padrão: usamos o maior entre o valor do
    config e um piso de 1024, para não cortar o JSON de saída no meio.
  - `stop_reason == "refusal"` é tratado explicitamente (mesmo padrão do
    tratamento de `finishReason` do provedor Gemini): erro claro em vez de
    KeyError críptico tentando ler um content vazio.
"""
from __future__ import annotations

from .base import ProviderBase

_MAX_TOKENS_PISO = 1024  # thinking adaptativo consome budget além do JSON de saída


class AnthropicProvider(ProviderBase):
    kind = "anthropic"

    def __init__(self, name: str, cfg: dict, request_cfg: dict):
        super().__init__(name, cfg, request_cfg)
        import anthropic  # import tardio: só quem usa este provedor precisa do pacote
        self._client = anthropic.Anthropic(api_key=self.api_key)
        self._effort = cfg.get("effort", "low")  # classificação: baixo raciocínio basta

    def complete(self, system: str, user: str) -> str:
        max_tokens = max(self.request_cfg.get("max_tokens", 300), _MAX_TOKENS_PISO)
        resposta = self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            # SEM temperature: removida do SDK para modelos com thinking
            # adaptativo por padrão (ver docstring do módulo).
            system=system,
            messages=[{"role": "user", "content": user}],
            thinking={"type": "adaptive"},
            output_config={"effort": self._effort},
            timeout=self.request_cfg.get("timeout_s", 60),
        )
        if resposta.stop_reason == "refusal":
            det = resposta.stop_details
            categoria = getattr(det, "category", None) if det else None
            raise RuntimeError(f"Claude recusou a resposta (categoria={categoria})")
        for bloco in resposta.content:
            if bloco.type == "text":
                return bloco.text
        raise RuntimeError(
            f"Claude sem bloco de texto (stop_reason={resposta.stop_reason}; "
            "provavelmente cortado por max_tokens antes do texto — "
            "aumentar request.max_tokens ou baixar o effort)"
        )

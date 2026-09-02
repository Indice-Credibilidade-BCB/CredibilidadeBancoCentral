# -*- coding: utf-8 -*-
"""BERTimbau + cabeça CORAL (D7).

Por que BERTimbau: pré-treinado no brWaC, cutoff de corpus conhecido e
anterior (~2019) a boa parte da amostra (2000-2026). Um classificador
encoder fine-tuned não faz "recall generativo" de desfechos futuros da forma
que um LLM de chat faz — ele aprende uma representação estatística da
LÍNGUA até o cutoff, não fatos específicos de eventos como "a meta estourou
em 2015" amarrados à cadeia de geração. É a opção estruturalmente mais à
prova de vazamento (D7), com a ressalva importante do D14: só é limpo (não
sofre de h_leak_t < 0) para itens de 2019 em diante — ver
`diagnostics/leakage.comparar_t6`.

Guarda de import: torch/transformers são pesados e só quem for treinar ou
rodar o braço local precisa deles (não entram no requirements.txt padrão).
"""
from __future__ import annotations

try:
    import torch
    from torch import nn
except ImportError as e:  # pragma: no cover - ambiente sem torch
    raise ImportError(
        "local_encoder precisa de torch e transformers: "
        "pip install torch transformers"
    ) from e

try:
    from transformers import AutoModel
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "local_encoder precisa de transformers: pip install transformers"
    ) from e

MODELO_PADRAO = "neuralmind/bert-base-portuguese-cased"


class CoralHead(nn.Module):
    """K-1 limiares binários "y > k?" compartilhando a projeção linear —
    ver `coral.py` para a codificação/decodificação de rótulo.

    Simplificado (sem a restrição de bias estritamente decrescente do paper
    original): na prática, com temperatura baixa e dados suficientes, a
    violação de monotonicidade é rara e não compromete a decodificação por
    limiar de `coral.coral_probs_to_label`."""

    def __init__(self, in_features: int, num_classes: int):
        super().__init__()
        self.fc = nn.Linear(in_features, 1, bias=False)
        self.bias = nn.Parameter(torch.zeros(num_classes - 1))

    def forward(self, x):
        return self.fc(x) + self.bias  # (batch, num_classes-1): logits de P(y>k)


class BertimbauCoralClassifier(nn.Module):
    """Encoder (BERTimbau) + pooling [CLS] + CoralHead p/ D1 (dimensão
    principal — probabilidade percebida de cumprimento da meta)."""

    def __init__(self, modelo_base: str = MODELO_PADRAO, num_classes: int = 5,
                dropout: float = 0.1):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(modelo_base)
        hidden = self.encoder.config.hidden_size
        self.dropout = nn.Dropout(dropout)
        self.head = CoralHead(hidden, num_classes)
        self.num_classes = num_classes

    def forward(self, input_ids, attention_mask):
        saida = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        cls = saida.last_hidden_state[:, 0, :]  # embedding do token [CLS]
        return self.head(self.dropout(cls))     # logits (batch, num_classes-1)

    def coral_loss(self, logits, targets):
        """targets: (batch, num_classes-1) de `coral.coral_targets`, já como
        float tensor 0/1. BCE-with-logits soma nos K-1 limiares — é a perda
        do paper original (sem peso extra; a ordinalidade já vem da própria
        decomposição em limiares, ao contrário de uma softmax de 5 classes
        onde errar por 1 e por 4 custam o mesmo)."""
        return nn.functional.binary_cross_entropy_with_logits(logits, targets)

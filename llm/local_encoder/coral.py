# -*- coding: utf-8 -*-
"""CORAL (COnsistent RAnk Logits) — a parte puramente numérica, sem torch.

D7 pede "regressão ordinal (CORAL) ou classificação com perda ponderada
quadrática (coerente com o κ_qw)". CORAL decompõe a classe ordinal 1..K em
K-1 problemas binários "y > k?", compartilhando a representação e só
variando o limiar — é isso que faz o erro previsto respeitar a ordem (a
perda binária comum, uma cabeça softmax de 5 classes, trata "errar por 1"
igual a "errar por 4").

Separado de `model.py` (que precisa de torch) porque a codificação/decodificação
de rótulo é lógica pura e deve ser testável sem a dependência pesada — mesmo
padrão de `diagnostics/leakage.py` vs. o resto do pipeline.

Referência: Cao, Mirjalili & Raschka (2020), "Rank consistent ordinal
regression for neural networks with application to age estimation".
"""
from __future__ import annotations

import numpy as np


def coral_targets(y: np.ndarray, num_classes: int) -> np.ndarray:
    """y: rótulos inteiros 1..num_classes. Retorna matriz (n, num_classes-1)
    de targets binários: coluna k (0-indexado) = 1{y > k+1}."""
    y = np.asarray(y, dtype=int)
    limiares = np.arange(1, num_classes)  # 1..num_classes-1
    return (y[:, None] > limiares[None, :]).astype(np.float32)


def coral_probs_to_label(probs: np.ndarray) -> np.ndarray:
    """probs: (n, num_classes-1) de P(y > k) (após sigmoid dos logits).
    Rótulo previsto = 1 + número de limiares "excedidos" (P > 0,5) — é a
    regra de decodificação do paper original; funciona mesmo se as
    probabilidades não saírem perfeitamente monótonas (CORAL suave, sem a
    restrição rígida de bias decrescente)."""
    probs = np.asarray(probs, dtype=float)
    return 1 + (probs > 0.5).sum(axis=1)


def coral_esperanca_label(probs: np.ndarray) -> np.ndarray:
    """Alternativa suave à decodificação por limiar: E[y] = 1 + soma das
    probabilidades (em vez de binarizar em 0,5). Útil para reportar um
    escore contínuo em vez de só o rótulo discreto."""
    probs = np.asarray(probs, dtype=float)
    return 1.0 + probs.sum(axis=1)

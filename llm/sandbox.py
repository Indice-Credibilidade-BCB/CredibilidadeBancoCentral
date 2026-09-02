# -*- coding: utf-8 -*-
"""D13 — quarentena de desenvolvimento: sandbox permanente de 10% do corpus.

O vazamento do PESQUISADOR não vem do modelo: é calibrar o prompt até a
série "parecer certa" olhando o agregado. Isso injeta futuro no instrumento
e nenhum cutoff de treino do LLM conserta. Mitigação: separar uma fração do
corpus, sorteada UMA vez, permanentemente excluída de qualquer iteração de
prompt/agregação/regra de anonimização — só sintéticos (T5, que não têm
desfecho verdadeiro) servem para calibrar de olho na série.

A separação é por HASH do item_id, não por `sample()` com seed: `sample`
muda de resultado quando o corpus cresce (índices deslocam); hash de um id
que já existe não muda quando novos itens chegam depois. Isso é o que torna
a quarentena estável ao longo do projeto, e não só no dia em que foi sorteada.

O manifesto (lista de item_id em sandbox — só ids opacos, sem texto) é
versionado em dados/derivados/ (permitido pelo .gitignore: agregado que não
reconstrói o texto original) para que o corte fique registrado e auditável.
"""
from __future__ import annotations

import hashlib
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).parent
MANIFESTO_PADRAO = ROOT / "../dados/derivados/sandbox_ids.csv"
FRACAO_PADRAO = 0.10


def _hash_fracao(item_id: str) -> float:
    """Mapeia item_id -> [0,1) de forma determinística e estável (não
    depende do tamanho do corpus nem de uma seed de RNG)."""
    h = hashlib.sha256(str(item_id).encode()).hexdigest()
    return int(h[:8], 16) / 0xFFFFFFFF


def em_sandbox(item_id: str, fracao: float = FRACAO_PADRAO) -> bool:
    return _hash_fracao(item_id) < fracao


def separar(df: pd.DataFrame, fracao: float = FRACAO_PADRAO,
           col_id: str = "item_id") -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retorna (producao, sandbox). NUNCA usar `sandbox` para calibrar prompt,
    regra de agregação ou esquema de ancoragem — só para checagem final,
    idealmente uma única vez, perto da publicação."""
    mask = df[col_id].map(lambda i: em_sandbox(i, fracao))
    return df.loc[~mask].copy(), df.loc[mask].copy()


def congelar_manifesto(df: pd.DataFrame, caminho: pathlib.Path = MANIFESTO_PADRAO,
                       fracao: float = FRACAO_PADRAO, col_id: str = "item_id") -> pd.DataFrame:
    """Grava o manifesto de ids em sandbox. Idempotente: se o corpus crescer,
    reexecutar só ACRESCENTA novos ids que caírem em sandbox pelo hash — os
    já congelados não mudam de lado porque a decisão é por hash do próprio
    id, não por amostragem sobre o corpus inteiro."""
    _, sandbox = separar(df, fracao, col_id)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    existente = (pd.read_csv(caminho)[col_id].astype(str).tolist()
                if caminho.exists() else [])
    todos = sorted(set(existente) | set(sandbox[col_id].astype(str)))
    manifesto = pd.DataFrame({col_id: todos})
    manifesto.to_csv(caminho, index=False)
    return manifesto


def carregar_manifesto(caminho: pathlib.Path = MANIFESTO_PADRAO) -> set:
    if not caminho.exists():
        return set()
    return set(pd.read_csv(caminho)["item_id"].astype(str))

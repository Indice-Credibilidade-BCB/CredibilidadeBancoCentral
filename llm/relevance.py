# -*- coding: utf-8 -*-
"""Filtro de relevância (novo estágio, anterior à anotação/pontuação).

Estágio 1 (regex, barato): mantém itens que mencionam o universo BCB/meta;
descarta procedurais óbvios (agenda, calendário).
Estágio 2 (opcional, LLM com PROMPT_RELEVANCIA): resolve os limítrofes.

Racional: forçar nota 1-5 em item sem sinal ("Copom se reúne amanhã") injeta
ruído no índice e derruba o kappa do piloto por razões erradas.
"""
from __future__ import annotations

import re

import pandas as pd

INCLUIR = re.compile(
    r"banco central|\bbcb\b|copom|\bselic\b|meta de infla|política monetária"
    r"|politica monetaria|juros? básic|taxa básica|autoridade monetária"
    r"|autoridade monetaria|relatório de inflação|relatorio de inflacao"
    r"|boletim focus",
    re.IGNORECASE,
)

PROCEDURAL = re.compile(
    r"re[úu]ne(?:-se)? (?:nesta|amanh[ãa]|na pr[óo]xima)|calend[áa]rio de reuni"
    r"|ata do copom ser[áa] divulgada|agenda da semana|expediente banc[áa]rio",
    re.IGNORECASE,
)


def prefiltro(df: pd.DataFrame) -> pd.DataFrame:
    texto = (df["titulo"].fillna("") + " " + df["lead"].fillna("")
             + " " + df["paragrafo_1"].fillna(""))
    df = df.copy()
    df["rel_menciona"] = texto.str.contains(INCLUIR)
    df["rel_procedural"] = texto.str.contains(PROCEDURAL)
    df["relevante_regex"] = df["rel_menciona"] & ~df["rel_procedural"]
    return df

# -*- coding: utf-8 -*-
"""Construção do conjunto de treino do braço local (D7).

Anti-contaminação da destilação (D7): "o professor (API) pode vazar; o
aluno só herda o vazamento que estiver correlacionado a traços textuais de
era." Três mitigações, as duas primeiras implementadas aqui:

  (i)   entrada de treino em anonimização L1 (sem datas no corpo) —
        `montar_exemplos`;
  (ii)  validação cruzada POR BLOCOS TEMPORAIS (treina numa era, testa em
        outra) — `dividir_blocos_temporais`;
  (iii) o ouro humano ancora a calibração — `montar_exemplos` marca a
        origem ("ouro"/"prata") para que `train.py` possa, por exemplo,
        dar peso maior ao ouro ou usá-lo só para validação final.

Tudo aqui é pandas/numpy puro — sem torch — para ficar testável sem a
dependência pesada.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from diagnostics.leakage import anonimizar  # noqa: E402


def montar_texto(row, nivel_anonimizacao: str = "L1") -> str:
    """Título + lead + 1º parágrafo, mascarados e concatenados — mesma
    construção usada no treino (`montar_exemplos`) e na inferência
    (`infer.py`), para que o encoder veja o texto no mesmo formato nas duas
    pontas."""
    partes = [anonimizar(row.get("titulo"), nivel_anonimizacao)]
    for col in ("lead", "paragrafo_1"):
        v = anonimizar(row.get(col), nivel_anonimizacao)
        if v:
            partes.append(v)
    return " [SEP] ".join(partes)


def montar_exemplos(itens: pd.DataFrame, rotulos: pd.DataFrame,
                    origem: str, nivel_anonimizacao: str = "L1") -> pd.DataFrame:
    """itens: item_id, data_publicacao, titulo, lead, paragrafo_1.
    rotulos: item_id, d1 (rótulo 1-5 — prata do provedor aprovado, ou ouro
    humano/consenso). Retorna item_id, data_publicacao, texto (mascarado em
    L1, já concatenado p/ tokenizar), d1, origem ('ouro'/'prata')."""
    df = itens.merge(rotulos[["item_id", "d1"]], on="item_id", how="inner")
    df = df[pd.to_numeric(df["d1"], errors="coerce").notna()].copy()
    df["d1"] = df["d1"].astype(int)
    df["texto"] = df.apply(lambda r: montar_texto(r, nivel_anonimizacao), axis=1)
    df["origem"] = origem
    return df[["item_id", "data_publicacao", "texto", "d1", "origem"]]


def amostrar_prata(ex_prata: pd.DataFrame, n_max: int | None, semente: int = 42,
                   data_col: str = "data_publicacao") -> pd.DataFrame:
    """Amostra até ``n_max`` exemplos prata, ESTRATIFICADA POR ANO.

    D7 previa destilação com 2–5 mil rótulos-prata (o corpus inteiro tem
    ~66 mil; treinar com todos custa ~13× mais e não melhora a régua, que é
    ancorada pelo ouro humano). A estratificação por ano preserva a
    cobertura temporal — a amostra aleatória simples sub-representaria os
    anos com pouco corpus (2011–2018), justamente os que a validação por
    blocos temporais precisa ver. Determinística dada a ``semente``.
    ``n_max=None`` ou ``>= len`` devolve tudo.
    """
    if n_max is None or n_max >= len(ex_prata):
        return ex_prata
    anos = pd.to_datetime(ex_prata[data_col], format="mixed").dt.year
    frac = n_max / len(ex_prata)
    partes = []
    for ano, g in ex_prata.groupby(anos):
        k = max(1, int(round(len(g) * frac)))
        partes.append(g.sample(n=min(k, len(g)), random_state=semente + int(ano)))
    amostra = pd.concat(partes)
    if len(amostra) > n_max:  # arredondamento por ano pode passar um pouco
        amostra = amostra.sample(n=n_max, random_state=semente)
    return amostra.sort_values(data_col)


def dividir_blocos_temporais(df: pd.DataFrame, data_col: str = "data_publicacao",
                             n_blocos: int = 5) -> pd.Series:
    """Atribui cada linha a um bloco 0..n_blocos-1 por QUANTIL de data (não
    por embaralhamento aleatório): validação cruzada por blocos temporais —
    treinar num bloco de tempo e testar em outro. CV aleatória colocaria
    itens do mesmo mês/episódio em treino E teste, inflando a validação com
    vazamento de vizinhança temporal (duas matérias do mesmo dia de Copom
    compartilham vocabulário de forma mais forte que a distância temporal
    típica do corpus)."""
    d = pd.to_datetime(df[data_col])
    ordem = d.rank(method="first")  # ordinal denso, sem empate
    blocos = pd.cut(ordem, bins=n_blocos, labels=False)
    return pd.Series(blocos.to_numpy(), index=df.index, name="bloco_temporal")


def resumo_blocos(df: pd.DataFrame, blocos: pd.Series,
                  data_col: str = "data_publicacao") -> pd.DataFrame:
    """Diagnóstico: intervalo de datas e contagem por bloco — confirma que a
    partição é de fato temporal (blocos não se sobrepõem no tempo)."""
    d = pd.to_datetime(df[data_col])
    return (pd.DataFrame({"bloco": blocos, "data": d})
            .groupby("bloco")["data"].agg(["min", "max", "count"])
            .rename(columns={"min": "inicio", "max": "fim", "count": "n"}))

# -*- coding: utf-8 -*-
"""Schema do corpus (Etapa 0) e utilidades de deduplicação.

Colunas obrigatórias:
  item_id, data_publicacao (YYYY-MM-DD), veiculo, tipo_veiculo {imprensa, research},
  titulo, lead, paragrafo_1, fonte_ref (url ou identificador)

Regras:
  - Dedup exata: mesmo (veiculo, titulo_norm, data) => manter 1.
  - Matéria de agência replicada entre veículos (wire): NÃO é dup para fins de
    corpus, mas recebe wire_cluster; na agregação, cada cluster conta UMA vez
    por mês (evita contar o mesmo sinal 3x porque saiu em 3 jornais).
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

import pandas as pd

REQUIRED_COLS = [
    "item_id", "data_publicacao", "veiculo", "tipo_veiculo",
    "titulo", "lead", "paragrafo_1", "fonte_ref",
]

TIPOS_VALIDOS = {"imprensa", "research"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def text_hash(row: pd.Series) -> str:
    base = _norm(row["titulo"]) + "|" + _norm(row.get("lead", ""))
    return hashlib.sha1(base.encode()).hexdigest()[:16]


def validate(df: pd.DataFrame) -> pd.DataFrame:
    faltantes = [c for c in REQUIRED_COLS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Corpus sem colunas obrigatórias: {faltantes}")
    tipos_invalidos = set(df["tipo_veiculo"].unique()) - TIPOS_VALIDOS
    if tipos_invalidos:
        raise ValueError(f"tipo_veiculo inválido: {tipos_invalidos}")
    df = df.copy()
    df["data_publicacao"] = pd.to_datetime(df["data_publicacao"]).dt.strftime("%Y-%m-%d")
    if df["item_id"].duplicated().any():
        raise ValueError("item_id duplicado no corpus")
    tit = df["titulo"].astype(str).str.strip()
    vazios = df["titulo"].isna() | (tit == "") | (tit.str.lower() == "nan")
    if vazios.any():
        raise ValueError(f"{int(vazios.sum())} item(ns) sem título — hash de "
                         "dedup/wire ficaria degenerado; corrigir na Etapa 0")
    return df


def dedup(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicatas exatas dentro do mesmo veículo e marca clusters wire."""
    df = df.copy()
    df["titulo_norm"] = df["titulo"].map(_norm)
    df = df.drop_duplicates(subset=["veiculo", "titulo_norm", "data_publicacao"])
    df["texto_hash"] = df.apply(text_hash, axis=1)
    # Cluster wire: mesmo texto_hash (título+lead normalizados); a agregação
    # colapsa por (mês, cluster) — logo a janela efetiva do wire é o mês.
    # Wire com títulos reescritos entre veículos NÃO é capturado (dedup é
    # exata; fuzzy fica p/ Etapa 3 se a taxa de wire observada justificar).
    df["wire_cluster"] = df["texto_hash"]  # agregação agrupa por (mes, wire_cluster)
    return df.drop(columns=["titulo_norm"])

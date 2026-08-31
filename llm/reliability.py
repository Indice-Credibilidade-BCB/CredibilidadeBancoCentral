# -*- coding: utf-8 -*-
"""Confiabilidade inter-anotadores do piloto (Etapa 2).

Gate pré-registrado: kappa de Cohen ponderado QUADRÁTICO na dimensão D1,
com 2 anotadores. Regra: κ_qw >= 0,6 prossegue; 0,5–0,6 aciona 3º anotador
desempatador + α de Krippendorff; < 0,5 volta à Etapa 1.
Robustez: α de Krippendorff (métrica ordinal) reportado sempre — lida com
valores faltantes (d2/d3 "sem sinal") e generaliza para 3+ anotadores.

Também computa a matriz de correlação entre dimensões por anotador
(checagem de halo effect: correlação LLM vs. correlação humana).
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

CATS = (1, 2, 3, 4, 5)


def kappa_quadratico(a, b, cats=CATS) -> float:
    """Kappa de Cohen com pesos quadráticos w_ij = (i-j)^2/(k-1)^2."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ok = ~np.isnan(a) & ~np.isnan(b)
    a, b = a[ok].astype(int), b[ok].astype(int)
    k = len(cats)
    idx = {c: i for i, c in enumerate(cats)}
    O = np.zeros((k, k))
    for x, y in zip(a, b):
        O[idx[x], idx[y]] += 1
    O /= O.sum()
    pa, pb = O.sum(axis=1), O.sum(axis=0)
    E = np.outer(pa, pb)
    W = np.array([[(i - j) ** 2 for j in range(k)] for i in range(k)],
                 dtype=float) / (k - 1) ** 2
    return float(1 - (W * O).sum() / (W * E).sum())


def alpha_krippendorff_ordinal(ratings: np.ndarray, cats=CATS) -> float:
    """α de Krippendorff (métrica ordinal).

    ratings: matriz (unidades x anotadores), NaN = faltante.
    Implementação via matriz de coincidências; unidades com <2 notas são
    descartadas (padrão do α).
    """
    ratings = np.asarray(ratings, dtype=float)
    k = len(cats)
    idx = {c: i for i, c in enumerate(cats)}
    coinc = np.zeros((k, k))
    for u in range(ratings.shape[0]):
        vals = ratings[u][~np.isnan(ratings[u])].astype(int)
        m = len(vals)
        if m < 2:
            continue
        for x, y in itertools.permutations(vals, 2):
            coinc[idx[x], idx[y]] += 1.0 / (m - 1)
    n_c = coinc.sum(axis=1)
    n = n_c.sum()
    if n <= 1:
        return float("nan")
    # métrica ordinal: delta_ck = (soma_{g=c..k} n_g - (n_c + n_k)/2)^2
    delta = np.zeros((k, k))
    for c in range(k):
        for kk in range(c + 1, k):
            s = n_c[c:kk + 1].sum() - (n_c[c] + n_c[kk]) / 2.0
            delta[c, kk] = delta[kk, c] = s ** 2
    Do = (coinc * delta).sum() / n
    De = (np.outer(n_c, n_c) * delta).sum() / (n * (n - 1))
    return float(1 - Do / De) if De > 0 else float("nan")


def correlacao_dimensoes(df: pd.DataFrame, prefixo: str) -> pd.DataFrame:
    """Correlação Spearman entre D1/D2/D3 de um mesmo anotador ou modelo.

    Uso na checagem de halo: se corr(D1,D2) do LLM >> corr(D1,D2) humana,
    o modelo não está tratando as dimensões como independentes.
    """
    cols = [f"{prefixo}_d1", f"{prefixo}_d2", f"{prefixo}_d3"]
    cols = [c for c in cols if c in df.columns]
    return df[cols].corr(method="spearman")


def checar_halo(corr_llm: pd.DataFrame, corr_humana: pd.DataFrame,
                limiar: float = 0.20) -> dict:
    """Regra D10 pré-registrada: alerta se corr(LLM) > corr(humana) + limiar
    em QUALQUER par de dimensões (o LLM estaria colando as dimensões)."""
    alertas = []
    for i in corr_llm.index:
        for j in corr_llm.columns:
            if i >= j:
                continue
            cl, ch = corr_llm.loc[i, j], corr_humana.loc[i, j]
            if pd.notna(cl) and pd.notna(ch) and cl > ch + limiar:
                alertas.append({"par": f"{i}x{j}", "corr_llm": float(cl),
                                "corr_humana": float(ch)})
    return {"halo_alerta": bool(alertas), "pares": alertas}


def _coerce_notas(s: pd.Series, nome: str, avisos: list) -> pd.Series:
    """Célula vazia/'sem_sinal' vira NaN; valor fora de 1–5 gera aviso."""
    num = pd.to_numeric(s, errors="coerce")
    invalidos = num.notna() & ~num.isin(CATS)
    if invalidos.any():
        avisos.append(f"{nome}: {int(invalidos.sum())} nota(s) fora de 1–5 "
                      f"(linhas {list(num.index[invalidos])}) — tratadas como faltantes")
        num[invalidos] = np.nan
    return num


def relatorio_piloto(csv_anotado: str) -> dict:
    """Espera colunas: anot1_d1, anot2_d1, anot1_d2, anot2_d2, anot1_d3, anot2_d3."""
    df = pd.read_csv(csv_anotado)
    out, avisos = {}, []
    for d in ("d1", "d2", "d3"):
        a, b = df.get(f"anot1_{d}"), df.get(f"anot2_{d}")
        if a is None or b is None:
            continue
        a = _coerce_notas(a, f"anot1_{d}", avisos)
        b = _coerce_notas(b, f"anot2_{d}", avisos)
        out[f"kappa_qw_{d}"] = kappa_quadratico(a, b)
        out[f"alpha_ord_{d}"] = alpha_krippendorff_ordinal(
            np.column_stack([a.to_numpy(float), b.to_numpy(float)]))
        ok = a.notna() & b.notna()
        # Concordância bruta: contexto p/ o paradoxo do kappa (distribuições
        # concentradas — ex.: calmaria, tudo "3" — derrubam κ mesmo com alta
        # concordância; reportar ambos evita reprovação injusta no gate).
        out[f"concord_bruta_{d}"] = (float((a[ok] == b[ok]).mean())
                                     if ok.any() else float("nan"))
    if "contexto_insuficiente" in df.columns:
        flag = df["contexto_insuficiente"].astype(str).str.strip().str.lower()
        out["pct_contexto_insuficiente"] = float(
            flag.isin({"true", "1", "sim", "x", "verdadeiro"}).mean())
    if avisos:
        out["avisos"] = avisos
    return out


if __name__ == "__main__":
    import sys
    print(relatorio_piloto(sys.argv[1]))

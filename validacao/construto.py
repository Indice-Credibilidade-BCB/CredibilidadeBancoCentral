# -*- coding: utf-8 -*-
"""Validade de construto do índice (artigo de medição, seção 7).

Sem um gabarito observável da credibilidade, o índice é defendido por uma
bateria, no modelo do EPU (Baker, Bloom e Davis, 2016):

* convergente (7.1): anda junto com medidas que deveriam medir algo parecido;
* discriminante (7.2): não é só a leitura da inflação corrente;
* preditiva (7.3): antecipa expectativas e preços, além do que eles já sabem.

Especificações e critérios registrados ANTES de rodar em
docs/local/CONTEXTO_Projeto_Indice_Credibilidade_BCB.md, seção 4.2.17.
Toda variável vem orientada "maior = mais credibilidade". Erro HAC
(Newey-West) com defasagens h + floor(4 (n/100)^(2/9)).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests

ALVOS_CONVERGENTE = ("breakeven_neg", "embi_neg", "cds_neg", "dm2007", "dm2009", "disp_focus_neg",
                     "foc_gap_neg", "inclinacao", "c_kf_suavizado")
ANCORAS = ("breakeven_neg", "embi_neg", "foc_gap_neg")
CONTROLES_INFLACAO = ("gap_ipca", "d12_ipca", "acima_teto")
HORIZONTES = (1, 3, 6)


def defasagens_hac(n: int, h: int = 0) -> int:
    return int(h + np.floor(4 * (n / 100.0) ** (2.0 / 9.0)))


def ols_hac(y: pd.Series, X: pd.DataFrame, h: int = 0):
    d = pd.concat([y.rename("_y"), X], axis=1).dropna()
    res = sm.OLS(d["_y"], sm.add_constant(d.drop(columns="_y"))).fit(
        cov_type="HAC", cov_kwds={"maxlags": defasagens_hac(len(d), h)})
    return res, len(d)


def _z(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std(ddof=0)


def preparar(painel: pd.DataFrame, rivais: pd.DataFrame, kf: pd.DataFrame | None = None) -> pd.DataFrame:
    """Painel mensal com as variáveis orientadas e os controles de inflação."""
    df = painel.join(rivais, how="left", rsuffix="_riv")
    if kf is not None and "c_kf_suavizado" in kf:
        df["c_kf_suavizado"] = kf["c_kf_suavizado"]
    df["foc_gap_neg"] = -(df["pi_focus"] - df["pi_star"])
    df["gap_ipca"] = df["pi_lag"] - df["pi_star"]
    df["d12_ipca"] = df["pi_lag"] - df["pi_lag"].shift(12)
    df["acima_teto"] = (df["pi_lag"] > df["pi_star"] + df["banda"]).astype(float).where(df["pi_lag"].notna())
    return df


# ── 7.1 convergente ─────────────────────────────────────────────────────────

def convergente(df: pd.DataFrame, cols_c, alvos=ALVOS_CONVERGENTE) -> pd.DataFrame:
    """corr(C, x) com p HAC: regressão de z(x) em z(C) na amostra comum."""
    linhas = []
    for c in cols_c:
        for x in alvos:
            if x not in df or c not in df:
                continue
            d = df[[c, x]].dropna()
            if len(d) < 36:
                continue
            res, n = ols_hac(_z(d[x]), _z(d[c]).to_frame("C"))
            linhas.append({"indice": c, "alvo": x, "n": n, "corr": d[c].corr(d[x]),
                           "b_padronizado": res.params["C"], "p_hac": res.pvalues["C"]})
    return pd.DataFrame(linhas)


def veredito_convergente(tab: pd.DataFrame, indice: str = "c_llm", alpha: float = 0.05) -> dict:
    t = tab[tab["indice"] == indice].set_index("alvo")
    ok = lambda x: x in t.index and t.loc[x, "corr"] > 0 and t.loc[x, "p_hac"] < alpha  # noqa: E731
    focus = ok("dm2007") or ok("foc_gap_neg")
    return {"breakeven": ok("breakeven_neg"), "focus": focus, "aprovado": ok("breakeven_neg") and focus}


# ── 7.2 discriminante ───────────────────────────────────────────────────────

def discriminante(df: pd.DataFrame, cols_c, ancoras=ANCORAS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(a) quanto do índice a inflação explica; (b) o índice explica as âncoras além da inflação?"""
    a, b = [], []
    ctl = list(CONTROLES_INFLACAO)
    ancoras = [x for x in ancoras if x in df]   # CDS/EMBI só existem com os dados do fornecedor
    for c in cols_c:
        res, n = ols_hac(df[c], df[ctl])
        a.append({"indice": c, "n": n, "r2_inflacao": res.rsquared,
                  **{f"coef_{k}": res.params[k] for k in ctl}, **{f"p_{k}": res.pvalues[k] for k in ctl}})
        for anc in ancoras:
            X = pd.concat([_z(df[c]).rename("C"), df[ctl]], axis=1)
            res2, n2 = ols_hac(df[anc], X)
            b.append({"indice": c, "ancora": anc, "n": n2, "c": res2.params["C"], "p_hac": res2.pvalues["C"],
                      "r2": res2.rsquared})
    return pd.DataFrame(a), pd.DataFrame(b)


def veredito_discriminante(tab_a: pd.DataFrame, tab_b: pd.DataFrame, indice: str = "c_llm",
                           alpha: float = 0.05) -> dict:
    r2 = float(tab_a.set_index("indice").loc[indice, "r2_inflacao"])
    tb = tab_b[tab_b["indice"] == indice].set_index("ancora")
    mercado = [a for a in ("breakeven_neg", "embi_neg")
               if a in tb.index and tb.loc[a, "c"] > 0 and tb.loc[a, "p_hac"] < alpha]
    return {"r2_inflacao": r2, "ancoras_de_mercado_aprovadas": mercado, "aprovado": r2 < 0.8 and bool(mercado)}


# ── 7.3 preditiva ───────────────────────────────────────────────────────────

def preditiva(df: pd.DataFrame, cols_c, alvos=ANCORAS, horizontes=HORIZONTES) -> pd.DataFrame:
    """y(t+h) − y(t) = a + b z(C_t) + c y_t + d Δy_t + g gap_ipca_t + e (HAC com h)."""
    linhas = []
    alvos = [x for x in alvos if x in df]       # CDS/EMBI só existem com os dados do fornecedor
    for c in cols_c:
        for y in alvos:
            for h in horizontes:
                frente = df[y].shift(-h) - df[y]
                X = pd.concat([_z(df[c]).rename("C"), df[y].rename("y_t"), df[y].diff().rename("dy_t"),
                               df["gap_ipca"]], axis=1)
                res, n = ols_hac(frente, X, h=h)
                linhas.append({"indice": c, "alvo": y, "h": h, "n": n, "b": res.params["C"],
                               "ep_hac": res.bse["C"], "p_hac": res.pvalues["C"]})
    tab = pd.DataFrame(linhas)
    tab["p_holm_h6"] = np.nan
    for c in cols_c:
        m = (tab["indice"] == c) & (tab["h"] == 6)
        if m.sum():
            tab.loc[m, "p_holm_h6"] = multipletests(tab.loc[m, "p_hac"], method="holm")[1]
    return tab


def veredito_preditiva(tab: pd.DataFrame, indice: str = "c_llm", alpha: float = 0.05) -> dict:
    t = tab[(tab["indice"] == indice) & (tab["h"] == 6)].set_index("alvo")
    prim = t.loc["foc_gap_neg"]
    return {"b_primario": float(prim["b"]), "p_primario": float(prim["p_hac"]),
            "aprovado_primario": bool(prim["b"] > 0 and prim["p_hac"] < alpha),
            "secundarios_holm": {a: float(t.loc[a, "p_holm_h6"]) for a in t.index}}

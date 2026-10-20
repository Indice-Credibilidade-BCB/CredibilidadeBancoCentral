# -*- coding: utf-8 -*-
r"""Bloco 3 — encompassing: o índice LLM explica o latente além dos rivais?

.. math::

    \hat{C}^{KF}_t = a + b_1\,\hat{C}^{LLM}_t + b_2\,\hat{C}^{rival}_t + u_t

Critério do desenho: índice validado se :math:`b_1` permanece significativo
com **cada** rival incluído (uma regressão por rival) e com todos juntos.
Erro-padrão Newey-West.

Convenções de saída (uma linha por regressão):

* ``variante_llm`` — qual série LLM entrou (``c_llm``, ``c_llm_vmax``,
  ``c_llm_vmin``, ``c_llm_gemini``…). Toda tabela principal traz V-max e
  V-min lado a lado (D12); se divergirem, o V-min manda.
* ``rival`` — ``nenhum``, o nome do rival, ou ``todos``.
* ``b1, ep_b1, t_b1, p_b1`` — coeficiente do LLM; ``b2…`` idem do rival
  (NaN em ``nenhum``/``todos``; para ``todos``, os coeficientes individuais
  ficam em ``extras``).
* ``padronizado`` — se os regressores e o dependente foram padronizados
  (média 0, dp 1) na amostra comum, para comparabilidade de magnitude.
* ``em_diferencas`` — robustez: regressão em primeiras diferenças, porque
  latente, LLM e rivais são todos persistentes e a regressão em nível pode
  ser espúria. Reportar as duas.

Alinhamento temporal: contemporâneo (:math:`t` com :math:`t`). O índice LLM
de um mês agrega textos publicados naquele mês; o latente usa o Focus do
mesmo mês. Não há defasagem embutida — o Bloco 6 é que usa o índice
defasado.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .econometria import ResultadoRegressao, ols_hac


def _padronizar(df: pd.DataFrame) -> pd.DataFrame:
    return (df - df.mean()) / df.std(ddof=0)


def _uma(y: pd.Series, X: pd.DataFrame, defasagens: int | None) -> ResultadoRegressao:
    return ols_hac(y, X, constante=True, defasagens=defasagens)


def encompassing(latente: pd.Series, llm: pd.Series, rivais: pd.DataFrame,
                 defasagens: int | None = None, padronizar: bool = True,
                 em_diferencas: bool = False, min_obs: int = 36) -> pd.DataFrame:
    """Tabela de encompassing para UMA variante do índice LLM.

    ``latente``: c_kf (suavizado, por padrão); ``llm``: série mensal do LLM;
    ``rivais``: DataFrame com um rival por coluna (NaNs permitidos —
    cada regressão usa a amostra comum das suas variáveis).
    """
    linhas = []
    nome_llm = llm.name or "c_llm"
    base = pd.concat([latente.rename("latente"), llm.rename("llm"), rivais], axis=1)
    if em_diferencas:
        base = base.diff()

    def rodar(colunas_rival: list[str], rotulo: str):
        df = base[["latente", "llm"] + colunas_rival].dropna()
        if len(df) < min_obs:
            linhas.append({"variante_llm": nome_llm, "rival": rotulo, "n": len(df),
                           "obs": f"amostra insuficiente (<{min_obs})"})
            return
        if padronizar:
            df = _padronizar(df)
        res = _uma(df["latente"], df[["llm"] + colunas_rival], defasagens)
        linha = {
            "variante_llm": nome_llm, "rival": rotulo, "n": res.n, "r2": res.r2,
            "hac_lags": res.defasagens_hac, "padronizado": padronizar, "em_diferencas": em_diferencas,
            "a": res.params["const"],
            "b1": res.params["llm"], "ep_b1": res.ep["llm"], "t_b1": res.t["llm"], "p_b1": res.p["llm"],
        }
        if len(colunas_rival) == 1:
            r = colunas_rival[0]
            linha.update({"b2": res.params[r], "ep_b2": res.ep[r], "t_b2": res.t[r], "p_b2": res.p[r]})
        elif colunas_rival:
            linha["extras"] = {r: (float(res.params[r]), float(res.p[r])) for r in colunas_rival}
        linhas.append(linha)

    rodar([], "nenhum")
    for r in rivais.columns:
        rodar([r], r)
    todos = [r for r in rivais.columns if rivais[r].notna().sum() >= min_obs]
    if len(todos) > 1:
        rodar(todos, "todos")
    # Um rival curto (ex.: CDS só desde 2019) encolhe a amostra de "todos";
    # repete só com os rivais que cobrem >= 80% da amostra do índice.
    n_llm = base["llm"].notna().sum()
    longos = [r for r in todos if base[r].notna().sum() >= 0.8 * n_llm]
    if 1 < len(longos) < len(todos):
        rodar(longos, "todos_longos")
    return pd.DataFrame(linhas)


def encompassing_variantes(latente: pd.Series, variantes: pd.DataFrame, rivais: pd.DataFrame,
                           **kw) -> pd.DataFrame:
    """Roda ``encompassing`` para cada coluna de ``variantes`` (c_llm, c_llm_vmax, …) e empilha."""
    partes = [encompassing(latente, variantes[c].rename(c), rivais, **kw) for c in variantes.columns]
    return pd.concat(partes, ignore_index=True)


def veredito(tabela: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame:
    """Resumo por variante: b1 significativo com cada rival? Em quantos? Sinal estável?"""
    out = []
    for v, g in tabela.groupby("variante_llm"):
        g = g.dropna(subset=["p_b1"]) if "p_b1" in g else g.iloc[0:0]
        com_rival = g[~g["rival"].isin(["nenhum"])]
        out.append({
            "variante_llm": v,
            "n_regressoes": int(len(g)),
            "b1_sig_sem_rival": bool((g.loc[g["rival"] == "nenhum", "p_b1"] < alpha).all()) if (g["rival"] == "nenhum").any() else None,
            "n_rivais_testados": int(len(com_rival)),
            "n_rivais_sobrevive": int((com_rival["p_b1"] < alpha).sum()),
            "sobrevive_a_todos": bool((com_rival["p_b1"] < alpha).all()) if len(com_rival) else None,
            "sinal_b1_estavel": bool((np.sign(g["b1"]) == np.sign(g["b1"].iloc[0])).all()) if len(g) else None,
            "b1_min": float(g["b1"].min()) if len(g) else np.nan,
            "b1_max": float(g["b1"].max()) if len(g) else np.nan,
        })
    return pd.DataFrame(out)


def comparar_vmax_vmin(tabela: pd.DataFrame, alpha: float = 0.05) -> pd.DataFrame | None:
    """Lado a lado V-max × V-min (D12). ``None`` se não houver as duas variantes."""
    vs = set(tabela["variante_llm"])
    pares = [(a, a.replace("vmax", "vmin")) for a in vs if "vmax" in a and a.replace("vmax", "vmin") in vs]
    if not pares:
        return None
    linhas = []
    for a, b in pares:
        ta = tabela[tabela["variante_llm"] == a].set_index("rival")
        tb = tabela[tabela["variante_llm"] == b].set_index("rival")
        for r in ta.index.intersection(tb.index):
            linhas.append({
                "rival": r, "b1_vmax": ta.loc[r, "b1"], "p_vmax": ta.loc[r, "p_b1"],
                "b1_vmin": tb.loc[r, "b1"], "p_vmin": tb.loc[r, "p_b1"],
                "mesma_conclusao": bool((ta.loc[r, "p_b1"] < alpha) == (tb.loc[r, "p_b1"] < alpha)
                                        and np.sign(ta.loc[r, "b1"]) == np.sign(tb.loc[r, "b1"])),
            })
    return pd.DataFrame(linhas)

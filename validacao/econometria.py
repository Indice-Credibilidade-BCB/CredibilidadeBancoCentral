# -*- coding: utf-8 -*-
"""Utilitários econométricos da validação.

* ``ols_hac`` — MQO com erro-padrão Newey-West (HAC), via statsmodels.
* ``defasagem_newey_west`` — regra de bolso de Newey-West (1994) para o
  número de defasagens: ``floor(4 (T/100)^(2/9))``.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm


def defasagem_newey_west(T: int) -> int:
    """Regra de Newey-West (1994): floor(4 (T/100)^(2/9))."""
    return int(np.floor(4 * (T / 100.0) ** (2.0 / 9.0)))


@dataclass
class ResultadoRegressao:
    """Saída comum de ``ols_hac`` e ``tsls_hac``."""
    params: pd.Series
    ep: pd.Series
    t: pd.Series
    p: pd.Series
    n: int
    r2: float
    defasagens_hac: int
    residuos: pd.Series
    extras: dict

    def tabela(self) -> pd.DataFrame:
        return pd.DataFrame({"coef": self.params, "ep_hac": self.ep, "t": self.t, "p": self.p})

    def __repr__(self) -> str:  # pragma: no cover
        return (f"ResultadoRegressao(n={self.n}, r2={self.r2:.3f}, hac={self.defasagens_hac})\n"
                + self.tabela().round(4).to_string())


def _alinhar(y: pd.Series, X: pd.DataFrame, Z: pd.DataFrame | None = None):
    df = pd.concat([y.rename("__y"), X] + ([Z.add_prefix("__z_")] if Z is not None else []), axis=1).dropna()
    yy = df["__y"]
    XX = df[X.columns]
    ZZ = df[[c for c in df.columns if c.startswith("__z_")]] if Z is not None else None
    if ZZ is not None:
        ZZ.columns = [c[len("__z_"):] for c in ZZ.columns]
    return yy, XX, ZZ


def ols_hac(y: pd.Series, X: pd.DataFrame, constante: bool = True,
            defasagens: int | None = None) -> ResultadoRegressao:
    """MQO com erro-padrão Newey-West.

    ``defasagens=None`` usa a regra de Newey-West (1994). Observações com NA
    em qualquer variável são descartadas (alinhamento por índice).
    """
    yy, XX, _ = _alinhar(y, X)
    if constante:
        XX = sm.add_constant(XX, has_constant="add")
    L = defasagem_newey_west(len(yy)) if defasagens is None else int(defasagens)
    mod = sm.OLS(yy.to_numpy(float), XX.to_numpy(float))
    res = mod.fit(cov_type="HAC", cov_kwds={"maxlags": L})
    idx = list(XX.columns)
    return ResultadoRegressao(
        params=pd.Series(res.params, index=idx), ep=pd.Series(res.bse, index=idx),
        t=pd.Series(res.tvalues, index=idx), p=pd.Series(res.pvalues, index=idx),
        n=int(res.nobs), r2=float(res.rsquared), defasagens_hac=L,
        residuos=pd.Series(res.resid, index=yy.index), extras={"statsmodels": res},
    )

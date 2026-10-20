# -*- coding: utf-8 -*-
"""Estudo de eventos com o índice diário (artigo de medição, seção 8).

* Copom (registrado antes de rodar, docs/local 4.2.17 item 6): para cada
  reunião ordinária, Δ = média das notas nos dias D+1..D+k − D−k..D−1 (o dia
  D fica fora: o anúncio sai depois do fechamento e as notícias do dia
  misturam antes e depois). Δ é regredido na surpresa do swap DI×Pré 3m
  (D−1 → D+1, em bps), erro HC1.
* Eventos institucionais (item 7, EXPLORATÓRIO): Δ em ±k dias para D1, D2 e
  D3, com o placebo de todas as datas possíveis.

As notas vêm de `llm/figuras_dimensoes.itens`: D1 em média simples (a série
oficial) e D2/D3 com o peso de desenho do pré-filtro.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

from mercado.bcb import RAIZ, reunioes_copom

EVENTOS_INSTITUCIONAIS = {
    "2016-05-17": "Goldfajn anunciado e PEC da autonomia técnica",
    "2020-11-03": "Senado aprova o PLP 19/2019",
    "2021-02-10": "Câmara aprova a autonomia (LC 179/2021)",
    "2023-01-18": "Lula critica a autonomia do BC (GloboNews)",
    "2024-05-08": "Copom corta 0,25 com placar 5 a 4",
    "2024-12-11": "Copom sobe 1 ponto e sinaliza mais duas altas",
}


def itens(provider: str = "sabia") -> pd.DataFrame:
    sys.path.insert(0, str(RAIZ / "llm"))
    import figuras_dimensoes  # noqa: E402
    return figuras_dimensoes.itens(provider)


def diarios(it: pd.DataFrame, dim: str, ponderar: bool) -> pd.DataFrame:
    """Soma ponderada e peso por dia, num calendário contínuo (dias sem notícia = 0)."""
    d = it[it[dim].notna()]
    w = d["w"] if ponderar else pd.Series(1.0, index=d.index)
    g = pd.DataFrame({"sw": w * d[dim], "w": w, "n": 1.0, "dia": d["dia"]}).groupby("dia").sum()
    cal = pd.date_range(it["dia"].min(), it["dia"].max(), freq="D")
    return g.reindex(cal, fill_value=0.0)


def delta(dia_tab: pd.DataFrame, data, k: int, min_n: int = 3) -> dict:
    """Média depois (D+1..D+k) − média antes (D−k..D−1)."""
    d = pd.Timestamp(data)
    antes = dia_tab.loc[d - pd.Timedelta(days=k): d - pd.Timedelta(days=1)]
    depois = dia_tab.loc[d + pd.Timedelta(days=1): d + pd.Timedelta(days=k)]
    na, nd = antes["n"].sum(), depois["n"].sum()
    if na < min_n or nd < min_n:
        return {"antes": np.nan, "depois": np.nan, "delta": np.nan, "n_antes": na, "n_depois": nd}
    ma, md = antes["sw"].sum() / antes["w"].sum(), depois["sw"].sum() / depois["w"].sum()
    return {"antes": ma, "depois": md, "delta": md - ma, "n_antes": na, "n_depois": nd}


def taxa_diaria(caminho: Path, coluna: str, minimo: float = 0.0, maximo: float = 60.0) -> pd.Series:
    """Uma coluna de taxa (% a.a.) de um CSV com coluna ``data``, sem valores implausíveis."""
    df = pd.read_csv(caminho)
    s = pd.Series(pd.to_numeric(df[coluna], errors="coerce").to_numpy(), index=pd.to_datetime(df["data"]))
    return s[(s > minimo) & (s < maximo)].dropna().sort_index().rename(coluna)


def surpresa_di(taxa: pd.Series, data_reuniao, max_dias: int = 7) -> float:
    """Surpresa à la Kuttner (2001): taxa no 1º fechamento a partir de D+1 menos
    a taxa no último fechamento ANTES de D. O Copom anuncia depois do
    fechamento, então o próprio dia D ainda é "antes" e fica fora da diferença
    direta. Taxa de prazo constante (swap 3 meses): sem fator de dias do contrato."""
    d = pd.Timestamp(data_reuniao)
    antes = taxa[(taxa.index < d) & (taxa.index >= d - pd.Timedelta(days=max_dias))]
    depois = taxa[(taxa.index >= d + pd.Timedelta(days=1)) & (taxa.index <= d + pd.Timedelta(days=1 + max_dias))]
    return float(depois.iloc[0] - antes.iloc[-1]) if len(antes) and len(depois) else np.nan


def surpresas_copom(inicio="2011-01-01", fim=None) -> pd.DataFrame:
    """Surpresa de cada reunião ordinária do Copom desde `inicio` (bps), pelo swap DI×Pré 3m da B3."""
    reun = reunioes_copom()
    datas = pd.to_datetime(reun["data_reuniao"])
    manter = (~reun["extraordinaria"].astype(bool)) & (datas >= inicio)
    if fim is not None:
        manter &= datas < fim
    reun = reun[manter]
    taxa = taxa_diaria(RAIZ / "dados" / "mercado" / "curvas_b3_diario.csv", "pre_3m")
    return pd.DataFrame({"data_reuniao": pd.to_datetime(reun["data_reuniao"]).to_numpy(),
                         "meta_selic": reun["meta_selic"].to_numpy(),
                         "surpresa_bps": [100 * surpresa_di(taxa, d) for d in reun["data_reuniao"]]})


def estudo_copom(it: pd.DataFrame, surpresas: pd.DataFrame, k: int = 7, dim: str = "d1",
                 ponderar: bool = False) -> tuple[pd.DataFrame, dict]:
    tab_d = diarios(it, dim, ponderar)
    linhas = [{"data_reuniao": r.data_reuniao, "surpresa_bps": r.surpresa_bps, **delta(tab_d, r.data_reuniao, k)}
              for r in surpresas.itertuples()]
    t = pd.DataFrame(linhas)
    ok = t.dropna(subset=["delta", "surpresa_bps"])
    res = {}
    for nome, x in (("surpresa", ok["surpresa_bps"]), ("abs_surpresa", ok["surpresa_bps"].abs())):
        m = sm.OLS(ok["delta"], sm.add_constant(x.rename("x"))).fit(cov_type="HC1")
        res[nome] = {"n": int(m.nobs), "b_por_10bps": 10 * m.params["x"], "ep_por_10bps": 10 * m.bse["x"],
                     "p": m.pvalues["x"], "const": m.params["const"]}
    res["delta_medio"] = float(ok["delta"].mean())
    return t, res


def eventos_institucionais(it: pd.DataFrame, eventos=EVENTOS_INSTITUCIONAIS, k: int = 30) -> pd.DataFrame:
    """Δ por dimensão e a posição do Δ na distribuição placebo (todas as datas a cada 7 dias)."""
    linhas = []
    for dim, ponderar in (("d1", False), ("d2", True), ("d3", True)):
        tab_d = diarios(it, dim, ponderar)
        datas = pd.date_range(tab_d.index.min() + pd.Timedelta(days=k + 1),
                              tab_d.index.max() - pd.Timedelta(days=k + 1), freq="7D")
        placebo = np.array([delta(tab_d, d, k)["delta"] for d in datas])
        placebo = placebo[np.isfinite(placebo)]
        for data, nome in eventos.items():
            r = delta(tab_d, data, k)
            linhas.append({"data": data, "evento": nome, "dimensao": dim, **r,
                           "placebo_frac_abs_maior": float((np.abs(placebo) >= abs(r["delta"])).mean())
                           if np.isfinite(r["delta"]) else np.nan})
    return pd.DataFrame(linhas)

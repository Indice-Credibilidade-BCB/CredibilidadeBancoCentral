# -*- coding: utf-8 -*-
"""Painel mensal da validação.

Uma linha por mês (``PeriodIndex`` mensal), com as séries já nas unidades e
no timing do desenho:

===================  =====================================================
coluna               definição
===================  =====================================================
pi_focus             mediana Focus do IPCA 12 meses à frente (suavizada),
                     MÉDIA das observações diárias do mês (p.p. a.a.)
pi_focus_fim         idem, última observação do mês
disp_focus           desvio-padrão entre respondentes, média do mês
pi_12m               IPCA acumulado 12 meses do mês t
pi_lag               ``pi_12m`` defasado 1 mês = último IPCA CONHECIDO em t
                     (o IPCA de t só sai em t+1) — é o :math:`\\pi_{t-1}`
pi_star              meta para os 12 meses à frente: interpolação
                     (12−m)/12·meta(ano) + m/12·meta(ano+1), a convenção do
                     BCB; constante em 3% desde a meta contínua (2025)
banda                meia-largura da banda de tolerância (p.p.)
pi_mensal            IPCA variação mensal (%)
selic                meta Selic vigente no FIM do mês (% a.a.)
c_llm[, _vmax, _vmin, delta_t]  índice LLM mensal, se fornecido
===================  =====================================================

O painel não decide nada sobre janelas de estimação: é a matéria-prima. Cada
teste recorta o que precisa.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from mercado.bcb import BANDA_TOLERANCIA, Fontes


def _mensal_media(s: pd.Series) -> pd.Series:
    return s.resample("MS").mean()


def _mensal_ultimo(s: pd.Series) -> pd.Series:
    return s.resample("MS").last()


def _para_periodo(s: pd.Series | pd.DataFrame):
    out = s.copy()
    out.index = pd.DatetimeIndex(out.index).to_period("M")
    return out


def meta_12m_a_frente(meta_anual: pd.Series, meses: pd.PeriodIndex) -> pd.Series:
    """Meta relevante para a janela de 12 meses que começa em cada mês.

    ``meta_anual`` indexada por data (1º de janeiro de cada ano, como no SGS
    13521). No mês m do ano y a janela cobre (12−m) meses de y e m meses de
    y+1 — daí a interpolação linear, que é a mesma usada pelo BCB para a
    "meta suavizada 12 meses". Anos sem meta publicada herdam a última
    disponível (meta contínua).
    """
    por_ano = meta_anual.copy()
    por_ano.index = pd.DatetimeIndex(por_ano.index).year
    por_ano = por_ano.groupby(level=0).last().sort_index()
    ultimo_ano, ultima_meta = por_ano.index.max(), por_ano.iloc[-1]

    def meta(ano: int) -> float:
        if ano in por_ano.index:
            return float(por_ano.loc[ano])
        if ano > ultimo_ano:
            return float(ultima_meta)
        return np.nan

    vals = []
    for p in meses:
        m, y = p.month, p.year
        vals.append((12 - m) / 12.0 * meta(y) + m / 12.0 * meta(y + 1))
    return pd.Series(vals, index=meses, name="pi_star")


def banda_12m_a_frente(meses: pd.PeriodIndex) -> pd.Series:
    vals = []
    for p in meses:
        m, y = p.month, p.year
        b0 = BANDA_TOLERANCIA.get(y, 1.5)
        b1 = BANDA_TOLERANCIA.get(y + 1, b0)
        vals.append((12 - m) / 12.0 * b0 + m / 12.0 * b1)
    return pd.Series(vals, index=meses, name="banda")


def acumular_12m(var_mensal_pct: pd.Series) -> pd.Series:
    """Acumulado em 12 meses (%) a partir de variações mensais (%)."""
    fator = 1.0 + var_mensal_pct / 100.0
    return (fator.rolling(12).apply(np.prod, raw=True) - 1.0) * 100.0


def carregar_indice_llm(caminho: str | Path, sufixo: str = "") -> pd.DataFrame:
    """Lê a saída de ``llm/aggregate.py`` e devolve colunas ``c_llm*`` indexadas por mês.

    Mantém ``c_llm``, e ``c_llm_vmax``/``c_llm_vmin``/``delta_t`` quando a
    agregação foi dupla (D12). ``sufixo`` (ex.: "_gemini") distingue índices
    de provedores diferentes no mesmo painel.
    """
    df = pd.read_csv(caminho)
    df["mes"] = pd.PeriodIndex(df["mes"], freq="M")
    df = df.set_index("mes")
    cols = [c for c in ("c_llm", "c_llm_vmax", "c_llm_vmin", "delta_t", "n_itens") if c in df.columns]
    out = df[cols].copy()
    out.columns = [f"{c}{sufixo}" for c in cols]
    return out


def construir_painel(f: Fontes, indices_llm: dict[str, pd.DataFrame] | None = None,
                     inicio: str = "2001-11", fim: str | None = None) -> pd.DataFrame:
    """Monta o painel mensal a partir das fontes brutas (ver docstring do módulo).

    ``indices_llm`` mapeia sufixo -> DataFrame de ``carregar_indice_llm``
    (ex.: ``{"": sabia, "_gemini": gemini}``).
    """
    fo = f.focus_ipca_12m.set_index("Data").sort_index()
    focus_m = pd.DataFrame({
        "pi_focus": _mensal_media(fo["Mediana"]),
        "pi_focus_fim": _mensal_ultimo(fo["Mediana"]),
        "disp_focus": _mensal_media(fo["DesvioPadrao"]),
        "n_resp_focus": _mensal_media(fo["numeroRespondentes"]),
    })
    pi_12m = _mensal_ultimo(f.ipca_12m).rename("pi_12m")
    pi_mensal = _mensal_ultimo(f.ipca_mensal).rename("pi_mensal")
    selic = _mensal_ultimo(f.selic_meta).rename("selic")

    painel = _para_periodo(pd.concat([focus_m, pi_12m, pi_mensal, selic], axis=1)).sort_index()
    # Timing: pi_lag = último IPCA 12m CONHECIDO em t (o de t-1).
    painel["pi_lag"] = painel["pi_12m"].shift(1)
    painel["pi_star"] = meta_12m_a_frente(f.meta_inflacao, painel.index)
    painel["banda"] = banda_12m_a_frente(painel.index)

    if indices_llm:
        for _, df in indices_llm.items():
            painel = painel.join(df, how="left")

    painel = painel[painel.index >= pd.Period(inicio, freq="M")]
    if fim:
        painel = painel[painel.index <= pd.Period(fim, freq="M")]
    painel.index.name = "mes"
    return painel


def salvar_painel(painel: pd.DataFrame, caminho: str | Path) -> None:
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    painel.to_csv(caminho, index=True)


def carregar_painel(caminho: str | Path) -> pd.DataFrame:
    df = pd.read_csv(caminho)
    df["mes"] = pd.PeriodIndex(df["mes"], freq="M")
    return df.set_index("mes")

# -*- coding: utf-8 -*-
"""Testes sintéticos (sem rede) da bateria de construto e do estudo de eventos."""
import numpy as np
import pandas as pd

from validacao import construto, eventos


def _painel(n=180, semente=0, efeito=0.5):
    rng = np.random.default_rng(semente)
    meses = pd.period_range("2011-01", periods=n, freq="M")
    c = pd.Series(np.cumsum(rng.normal(0, 0.05, n)) + 0.5, index=meses)
    pi_lag = pd.Series(4.5 + np.cumsum(rng.normal(0, 0.2, n)), index=meses)
    foc = pd.Series(4.5 + rng.normal(0, 0.1, n), index=meses)
    # a âncora futura responde ao índice de hoje: y(t+6) − y(t) = efeito·C(t) + ruído
    y = np.zeros(n)
    for t in range(n - 6):
        y[t + 6] = y[t] + efeito * (c.iloc[t] - 0.5) + rng.normal(0, 0.02)
    painel = pd.DataFrame({"c_llm": c, "pi_lag": pi_lag, "pi_focus": foc, "pi_star": 4.5, "banda": 1.5})
    rivais = pd.DataFrame({"breakeven_neg": c + rng.normal(0, 0.02, n), "embi_neg": pd.Series(y, index=meses)},
                          index=meses)
    return construto.preparar(painel, rivais)


def test_convergente_acha_correlacao_positiva():
    df = _painel()
    t = construto.convergente(df, ["c_llm"], alvos=("breakeven_neg",))
    assert t["corr"].iloc[0] > 0.9 and t["p_hac"].iloc[0] < 0.01


def test_preditiva_recupera_efeito_positivo_em_h6():
    df = _painel(efeito=0.8)
    t = construto.preditiva(df, ["c_llm"], alvos=("embi_neg",), horizontes=(6,))
    assert t["b"].iloc[0] > 0 and t["p_hac"].iloc[0] < 0.05


def test_preditiva_sem_efeito_nao_rejeita_em_geral():
    rejeicoes = 0
    for s in range(20):
        df = _painel(semente=s, efeito=0.0)
        t = construto.preditiva(df, ["c_llm"], alvos=("embi_neg",), horizontes=(6,))
        rejeicoes += int(t["p_hac"].iloc[0] < 0.05)
    assert rejeicoes <= 5


def test_discriminante_r2_e_ancoras():
    df = _painel()
    a, b = construto.discriminante(df, ["c_llm"], ancoras=("breakeven_neg",))
    assert 0 <= a["r2_inflacao"].iloc[0] <= 1
    assert b["c"].iloc[0] > 0


def test_delta_de_janela_exclui_o_dia_e_exige_minimo():
    dias = pd.date_range("2020-01-01", "2020-01-31", freq="D")
    it = pd.DataFrame({"dia": np.repeat(dias, 2), "d1": 0.0, "w": 1.0})
    it.loc[it["dia"] > "2020-01-15", "d1"] = 1.0
    it.loc[it["dia"] == "2020-01-15", "d1"] = 0.5   # o próprio dia D não entra
    tab = eventos.diarios(it, "d1", ponderar=False)
    r = eventos.delta(tab, "2020-01-15", k=7)
    assert r["antes"] == 0.0 and r["depois"] == 1.0 and r["delta"] == 1.0
    assert np.isnan(eventos.delta(tab, "2020-01-15", k=7, min_n=100)["delta"])

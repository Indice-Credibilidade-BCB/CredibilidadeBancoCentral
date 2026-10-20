# -*- coding: utf-8 -*-
"""Testes de validacao/ (latente do Kalman, rivais, encompassing). Sem rede: tudo sintético.

Rodar da raiz: ``python -m pytest validacao/tests -q``
"""
import numpy as np
import pandas as pd
import pytest

from validacao import econometria, encompassing, kalman, painel, rivais
from mercado.bcb import Fontes


# ─── econometria ─────────────────────────────────────────────────────────

def test_ols_hac_recupera_coeficientes():
    rng = np.random.default_rng(1)
    T = 300
    x = pd.Series(rng.normal(size=T), name="x")
    e = pd.Series(np.convolve(rng.normal(size=T + 5), np.ones(5) / 5, mode="valid"))  # erro autocorrelacionado
    y = 1.0 + 2.0 * x + e
    r = econometria.ols_hac(y, x.to_frame())
    assert abs(r.params["x"] - 2.0) < 0.15
    assert abs(r.params["const"] - 1.0) < 0.15
    assert r.defasagens_hac == econometria.defasagem_newey_west(T)
    assert r.p["x"] < 1e-6


# ─── kalman ──────────────────────────────────────────────────────────────

def test_kalman_recupera_trajetoria_de_c():
    pn, c_true = kalman.simular(T=300, sigma_eta=0.3, sigma_nu=0.12, seed=7, d_escala=4.0)
    tvp = kalman.TVPCredibilidade("logistica")
    out = tvp.ajustar(pn)
    err = np.abs(out["c_kf_suavizado"].to_numpy() - c_true)
    assert err.mean() < 0.12, err.mean()
    assert np.corrcoef(out["c_kf_suavizado"], c_true)[0, 1] > 0.85
    assert 0.1 < tvp.sigma_eta < 0.8
    assert (out["c_kf_suavizado"].between(0, 1)).all()
    assert out["ep_suavizado"].mean() <= out["ep_filtrado"].mean() + 1e-9  # suavizador reduz incerteza


def test_kalman_identificacao_fraca_quando_d_pequeno():
    pn, _ = kalman.simular(T=200, seed=1, d_escala=0.05)  # meta ≈ inflação
    out = kalman.TVPCredibilidade("logistica").ajustar(pn)
    d = kalman.diagnostico_identificacao(out, limiar_pp=1.0)
    assert d["frac_meses_fracos"] > 0.9
    # sem informação, o filtro fica perto do prior (C=0,5)
    assert abs(out["c_kf_suavizado"].mean() - 0.5) < 0.2


def test_kalman_linear_e_logistico_concordam_no_meio():
    pn, c_true = kalman.simular(T=300, sigma_nu=0.05, seed=11, d_escala=4.0)
    a = kalman.TVPCredibilidade("logistica").ajustar(pn)["c_kf_suavizado"]
    b = kalman.TVPCredibilidade("identidade").ajustar(pn)["c_kf_suavizado"]
    meio = (c_true > 0.2) & (c_true < 0.8)
    assert np.abs(a[meio] - b[meio]).mean() < 0.1


def test_kalman_tolera_faltantes():
    pn, _ = kalman.simular(T=120, seed=5)
    pn.iloc[30:40, 0] = np.nan
    out = kalman.TVPCredibilidade().ajustar(pn)
    assert out["c_kf_filtrado"].notna().all()
    assert np.isnan(out["inovacao_padr"].iloc[35])


# ─── painel ──────────────────────────────────────────────────────────────

def _fontes_sinteticas(T=60) -> Fontes:
    dias = pd.date_range("2015-01-01", periods=T * 31, freq="D")
    meses = pd.date_range("2015-01-01", periods=T, freq="MS")
    anos = pd.date_range("2015-01-01", periods=8, freq="YS")
    rng = np.random.default_rng(0)
    s = lambda v, ix: pd.Series(v, index=ix)  # noqa: E731
    focus = pd.DataFrame({"Data": dias, "Mediana": 4.5 + rng.normal(0, .1, len(dias)),
                          "Media": 4.5, "DesvioPadrao": 0.3, "Minimo": 3, "Maximo": 6, "numeroRespondentes": 100})
    return Fontes(
        ipca_mensal=s(0.4, meses), ipca_12m=s(np.linspace(6, 4, T), meses),
        ipca_livres_mensal=s(0.3, meses), selic_meta=s(10.0, dias), selic_mensal=s(10.0, meses),
        ibcbr_dessaz=s(100 * np.exp(np.cumsum(rng.normal(0.001, 0.01, T))), meses),
        cambio_media_mensal=s(np.exp(np.cumsum(rng.normal(0, 0.02, T))) * 3, meses),
        meta_inflacao=s([4.5, 4.5, 4.5, 4.25, 4.0, 3.75, 3.5, 3.25], anos),
        divida_selic_pct=s(40.0, meses), focus_ipca_12m=focus,
    )


def test_meta_12m_interpolada():
    meta = pd.Series([4.5, 4.25], index=pd.to_datetime(["2018-01-01", "2019-01-01"]))
    meses = pd.period_range("2018-01", "2018-12", freq="M")
    m = painel.meta_12m_a_frente(meta, meses)
    assert np.isclose(m.iloc[0], (11 / 12) * 4.5 + (1 / 12) * 4.25)
    assert np.isclose(m.iloc[-1], 4.25)  # dezembro: 12 meses à frente = ano seguinte inteiro
    # ano sem meta publicada herda a última (meta contínua)
    m2 = painel.meta_12m_a_frente(meta, pd.period_range("2019-06", "2019-06", freq="M"))
    assert np.isclose(m2.iloc[0], 4.25)


def test_acumular_12m():
    s = pd.Series([0.5] * 24)
    acc = painel.acumular_12m(s)
    assert np.isclose(acc.iloc[-1], ((1.005 ** 12) - 1) * 100)
    assert acc.iloc[:11].isna().all()


def test_construir_painel_colunas_e_timing():
    f = _fontes_sinteticas()
    pn = painel.construir_painel(f, inicio="2015-01")
    for c in ("pi_focus", "disp_focus", "pi_12m", "pi_lag", "pi_star", "banda", "selic"):
        assert c in pn.columns, c
    # pi_lag é pi_12m de t-1
    assert np.isclose(pn["pi_lag"].iloc[5], pn["pi_12m"].iloc[4])
    assert isinstance(pn.index, pd.PeriodIndex)


def test_carregar_indice_llm(tmp_path):
    p = tmp_path / "idx.csv"
    pd.DataFrame({"mes": ["2020-01", "2020-02"], "c_llm": [0.5, 0.6], "c_llm_vmax": [0.5, 0.6],
                  "c_llm_vmin": [0.4, 0.5], "delta_t": [0.1, 0.1], "ep": [0.01, 0.01]}).to_csv(p, index=False)
    df = painel.carregar_indice_llm(p, sufixo="_x")
    assert list(df.columns) == ["c_llm_x", "c_llm_vmax_x", "c_llm_vmin_x", "delta_t_x"]
    assert isinstance(df.index, pd.PeriodIndex)


# ─── rivais ──────────────────────────────────────────────────────────────

def test_de_mendonca_2007_valores_de_referencia():
    e = pd.Series([4.5, 6.0, 20.0, 25.0, -1.0, 3.0])
    m = pd.Series([4.5] * 6)
    ic = rivais.de_mendonca_2007(e, m)
    assert np.isclose(ic[0], 1.0)
    assert np.isclose(ic[1], 1 - 1.5 / 15.5)
    assert ic[2] == 0 and ic[3] == 0 and ic[4] == 0
    assert np.isclose(ic[5], 1 - 1.5 / 15.5)  # simétrico abaixo da meta (extensão documentada)


def test_de_mendonca_2009_banda():
    e = pd.Series([4.5, 6.0, 7.0, 2.0])
    m = pd.Series([4.5] * 4); b = pd.Series([1.5] * 4)
    ic = rivais.de_mendonca_souza_2009(e, m, b)
    assert ic[0] == 1.0 and ic[1] == 1.0  # dentro da banda
    assert np.isclose(ic[2], 1 - (7 - 6) / (20 - 6))
    assert np.isclose(ic[3], 1 - (3 - 2) / 3)


def test_montar_rivais_sem_arquivos_externos(tmp_path, monkeypatch):
    monkeypatch.setattr(rivais, "DIR_MACRO", tmp_path)
    monkeypatch.setattr(rivais, "DIR_MERCADO", tmp_path)
    monkeypatch.setattr(rivais, "DIR_TERCEIROS", tmp_path)
    f = _fontes_sinteticas()
    pn = painel.construir_painel(f, inicio="2015-01")
    with pytest.warns(UserWarning):
        r = rivais.montar_rivais(pn)
    assert set(r.columns) == {"dm2007", "dm2009", "disp_focus_neg"}
    # com arquivo DEG presente, entra
    pd.DataFrame({"ano": [2015, 2016], "valor": [9.5, 10.0]}).to_csv(tmp_path / "deg_brasil.csv", index=False)
    r2 = rivais.montar_rivais(pn, incluir_mercado=False)
    assert "deg" in r2.columns and r2["deg"].iloc[0] == 9.5 and np.isnan(r2["deg"].iloc[-1])


# ─── encompassing ────────────────────────────────────────────────────────

def _dados_encompassing(T=240, b1=0.6, b2=0.3, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.period_range("2005-01", periods=T, freq="M")
    llm = pd.Series(np.clip(0.5 + 0.2 * np.sin(np.linspace(0, 8, T)) + rng.normal(0, .05, T), 0, 1), idx, name="c_llm")
    riv = pd.Series(np.clip(0.6 + 0.15 * np.cos(np.linspace(0, 5, T)) + rng.normal(0, .05, T), 0, 1), idx, name="dm2007")
    lat = 0.1 + b1 * llm + b2 * riv + rng.normal(0, .05, T)
    return lat.rename("c_kf"), llm, riv.to_frame()


def test_encompassing_detecta_b1():
    lat, llm, riv = _dados_encompassing()
    tab = encompassing.encompassing(lat, llm, riv, padronizar=False)
    assert set(tab["rival"]) == {"nenhum", "dm2007"}
    linha = tab.set_index("rival").loc["dm2007"]
    assert abs(linha["b1"] - 0.6) < 0.1 and linha["p_b1"] < 0.01
    assert abs(linha["b2"] - 0.3) < 0.1
    v = encompassing.veredito(tab)
    assert v.loc[0, "sobrevive_a_todos"] is True or v.loc[0, "sobrevive_a_todos"] == True  # noqa: E712


def test_encompassing_nao_detecta_quando_b1_zero():
    lat, llm, riv = _dados_encompassing(b1=0.0, seed=3)
    tab = encompassing.encompassing(lat, llm, riv)
    assert tab.set_index("rival").loc["dm2007", "p_b1"] > 0.05


def test_encompassing_variantes_e_vmax_vmin():
    lat, llm, riv = _dados_encompassing()
    var = pd.DataFrame({"c_llm_vmax": llm, "c_llm_vmin": llm * 0.9 + 0.05})
    tab = encompassing.encompassing_variantes(lat, var, riv)
    assert set(tab["variante_llm"]) == {"c_llm_vmax", "c_llm_vmin"}
    cmp = encompassing.comparar_vmax_vmin(tab)
    assert cmp is not None and cmp["mesma_conclusao"].all()


def test_encompassing_amostra_insuficiente():
    lat, llm, riv = _dados_encompassing(T=20)
    tab = encompassing.encompassing(lat, llm, riv)
    assert "obs" in tab.columns and tab["obs"].notna().all()

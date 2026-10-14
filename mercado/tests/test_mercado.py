# -*- coding: utf-8 -*-
"""Testes de mercado/ (calendário, ANBIMA, Tesouro Direto). Sem rede.

Rodar da raiz: ``python -m pytest mercado/tests -q``
"""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from mercado import anbima, b3_taxas as b3, calendario as cal, inflacao_implicita as ii


# ─── calendário ──────────────────────────────────────────────────────────

def test_pascoa_datas_conhecidas():
    assert cal._pascoa(2015) == date(2015, 4, 5)
    assert cal._pascoa(2024) == date(2024, 3, 31)
    assert cal._pascoa(2026) == date(2026, 4, 5)


def test_feriados_algoritmicos_incluem_moveis_e_consciencia_negra():
    f = set(cal.feriados_algoritmicos(2023, 2024))
    assert pd.Timestamp("2024-02-12") in f and pd.Timestamp("2024-02-13") in f  # carnaval
    assert pd.Timestamp("2024-05-30") in f                                       # Corpus Christi
    assert pd.Timestamp("2024-11-20") in f and pd.Timestamp("2023-11-20") not in f


def test_du_convencao_inicio_inclusive_fim_exclusive():
    # 2024-02-09 (sex) -> 2024-02-15 (qui): sex, qua (seg/ter carnaval) = 2
    assert cal.du("2024-02-09", "2024-02-15") == 2
    assert cal.du("2026-10-14", "2026-10-14") == 0


def test_vencimento_di1_primeiro_dia_util():
    assert cal.vencimento_di1(2027, 1) == pd.Timestamp("2027-01-04")  # 1º/1 feriado, 2-3 fim de semana
    assert cal.vencimento_di1(2026, 11) == pd.Timestamp("2026-11-03")  # 2/11 feriado (Finados, segunda)
    assert cal.codigo_di1(pd.Timestamp("2027-01-04")) == "DI1F27"
    assert cal.codigo_di1(pd.Timestamp("2026-10-01")) == "DI1V26"


def test_vencimentos_apos_sao_estritamente_posteriores():
    v = cal.vencimentos_di1_apos("2026-10-01", 4)  # dia do vencimento de outubro
    assert v[0] == pd.Timestamp("2026-11-03") and len(v) == 4
    v2 = cal.vencimentos_di1_apos("2026-09-30", 1)
    assert v2[0] == pd.Timestamp("2026-10-01")


def test_calendario_copom_colunas_e_kuttner():
    r = pd.DataFrame({
        "numero": [1, 2], "data_reuniao": pd.to_datetime(["2026-03-18", "2026-04-29"]),
        "extraordinaria": [False, False], "meta_selic": [14.75, 14.50],
        "inicio_vigencia": pd.to_datetime(["2026-03-19", "2026-04-30"]), "codigo_focus": ["R2/2026", "R3/2026"],
    })
    c = cal.calendario_copom(r)
    l0 = c.iloc[0]
    assert l0["pregao_d0"] == pd.Timestamp("2026-03-18") and l0["pregao_d_mais_1"] == pd.Timestamp("2026-03-19")
    assert l0["kuttner_codigo"] == "DI1J26" and l0["kuttner_fator"] == 1.0
    assert l0["kuttner_atravessa_proxima"] is False or l0["kuttner_atravessa_proxima"] == False  # noqa: E712
    assert l0["kuttner2_codigo"] == "DI1K26" and l0["kuttner2_atravessa_proxima"] == True  # noqa: E712
    l1 = c.iloc[1]
    assert l1["variacao_bps"] == -25.0
    assert l1["kuttner_codigo"] == "DI1K26" and l1["kuttner_du_vigencia_venc"] == 1 and l1["kuttner_curto_demais"]


# ─── ANBIMA ──────────────────────────────────────────────────────────────

ETTJ_TXT = """13/10/2026;Beta 1;Beta 2;Beta 3;Beta 4;Lambda 1;Lambda 2
PREFIXADOS;0,11999765354156;1,79087401287426E-02;-4,45434262532254E-02;4,34661935126561E-02;0,859502929963706;0,369942588536278
IPCA;6,45851544150928E-02;-4,27959306431925E-02;5,27665519300188E-02;7,36594477354519E-03;2,05717331732482;0,22820858434017

ETTJ Inflação Implicita (IPCA)
Vertices;ETTJ IPCA;ETTJ PREF;Inflação Implícita
252;6,2791;12,7294;6,0692
1.008;6,7656;12,6719;5,5320

PREFIXADOS (CIRCULAR 3.361)
1;2;3;4
"""

MS_TXT = """ANBIMA - Associação

Titulo@Data Referencia@Codigo SELIC@Data Base/Emissao@Data Vencimento@Tx. Compra@Tx. Venda@Tx. Indicativas@PU@Desvio padrao@Interv. Ind. Inf. (D0)@Interv. Ind. Sup. (D0)@Interv. Ind. Inf. (D+1)@Interv. Ind. Sup. (D+1)@Criterio
LTN@20261013@100000@20250110@20270401@13,1823@13,1616@13,1751@945,084902@0,0098@12,8852@13,3364@12,9682@13,4148@Calculado
LTN@20261013@100000@20250110@20270401@13,1823@13,1616@13,1751@945,084902@0,0098@12,8852@13,3364@12,9682@13,4148@Calculado
NTN-B@20261013@760199@20000715@20280815@6,7527@6,7288@6,7399@4752,09466@0,0002@6,4475@6,8929@6,5077@6,9527@Calculado
"""


def test_parse_ettj_e_svensson_reproduz_vertices():
    p, v = anbima.parse_ettj(ETTJ_TXT, pd.Timestamp("2026-10-13"))
    assert set(p["curva"]) == {"nominal", "real"} and len(v) == 2
    assert v["du"].tolist() == [252, 1008]  # milhar com ponto
    for curva in ("nominal", "real"):
        b = p.set_index("curva").loc[curva, ["beta1", "beta2", "beta3", "beta4", "lambda1", "lambda2"]]
        y = 100 * anbima.svensson(v["du"].to_numpy() / 252, *b)
        assert np.allclose(y, v[curva].to_numpy(), atol=1e-3)


def test_parse_ettj_vazio_fora_da_janela():
    p, v = anbima.parse_ettj("", pd.Timestamp("2015-03-02"))
    assert p.empty and v.empty


def test_parse_titulos_remove_duplicatas():
    t = anbima.parse_titulos(MS_TXT)
    assert len(t) == 2 and set(t["titulo"]) == {"LTN", "NTN-B"}
    assert np.isclose(t.loc[t.titulo == "NTN-B", "taxa_indicativa"].iloc[0], 6.7399)


# ─── Tesouro Direto ──────────────────────────────────────────────────────

def test_duration_zero_cupom_limite_e_cupom_menor_que_prazo():
    ref, venc = pd.Timestamp("2026-10-13"), pd.Timestamp("2035-05-15")
    d = ii.duration_macaulay(ref, venc, 6.7, 0.06)
    anos = cal.du(ref, venc) / 252
    assert 0.5 * anos < d < anos
    # cupom quase zero -> duration ≈ prazo
    assert abs(ii.duration_macaulay(ref, venc, 6.7, 1e-9) - anos) < 1e-6


def test_pontos_e_curvas_sem_extrapolacao():
    td = pd.DataFrame({
        "tipo": ["Tesouro Prefixado", "Tesouro Prefixado", "Tesouro IPCA+", "Tesouro IPCA+", "Tesouro Prefixado"],
        "data": pd.to_datetime(["2015-03-02"] * 5),
        "vencimento": pd.to_datetime(["2017-01-01", "2018-01-01", "2016-08-15", "2020-08-15", "2015-05-01"]),
        "taxa_compra": [12.80, 12.60, 6.00, 6.10, 0.05], "taxa_venda": [12.90, 12.70, 6.10, 6.20, 0.07],
    })
    pts = ii.pontos_da_curva(td)
    assert (pts["anos_venc"] >= 0.5).all()  # título a 2 meses do vencimento (taxa espúria) saiu
    cd = ii.curvas_diarias(pts, horizontes=(1, 2, 5)).iloc[0]
    assert np.isnan(cd["nominal_1a"])        # abaixo do prazo mínimo disponível
    assert 12.6 < cd["nominal_2a"] < 12.9
    assert np.isnan(cd["nominal_5a"])        # acima do máximo: sem extrapolação
    assert 6.0 < cd["real_2a"] < 6.2
    assert np.isclose(cd["implicita_2a"], 100 * ((1 + cd["nominal_2a"] / 100) / (1 + cd["real_2a"] / 100) - 1))


# ─── B3 TaxaSwap ─────────────────────────────────────────────────────────

LINHAS_TS = [
    "0000010010120261009T1PRE  DIxPRE         0000100001+00000149000000F00001",
    "0000020010120261009T1PRE  DIxPRE         0035600252+00000127350000M00356",
    "0000030010120261009T1PRE  DIxPRE         0072000504+00000124000000M00720",
    "0000040010120261009T1DIC  DI X IPCA      0035600252+00000089800000M00356",
    "0000050010120261009T1ACC  DIxDOL Aj. Cupo0035600252+00000064140000M00356",
    "0000060010120261009T1SDE  DOLx EURO      0035600252-00000017400000M00356",
]


def test_parse_ts_filtra_curvas_e_le_sinal():
    df = b3.parse(LINHAS_TS)
    assert set(df["curva"]) == {"PRE", "DIC"} and len(df) == 4
    assert df.loc[(df.curva == "PRE") & (df.du == 252), "taxa"].iloc[0] == pytest.approx(12.735)
    neg = b3.parse(LINHAS_TS, curvas=("SDE",))
    assert neg["taxa"].iloc[0] == pytest.approx(-1.74)


def test_flat_forward_reproduz_vertices_e_nao_extrapola():
    du = np.array([1, 252, 504]); tx = np.array([14.9, 12.735, 12.4])
    out = b3.flat_forward(du, tx, [252, 504, 378, 600])
    assert out[0] == pytest.approx(12.735) and out[1] == pytest.approx(12.4)
    assert 12.4 < out[2] < 12.735 and np.isnan(out[3])
    # forward constante entre 252 e 504: fator em 378 é a média geométrica
    f252, f504 = 1.12735, 1.124 ** 2
    assert (1 + out[2] / 100) ** 1.5 == pytest.approx((f252 * f504) ** 0.5, rel=1e-9)


def test_parse_ts_layout_antigo_ate_2002():
    antigo = ["0002710010120010301T1PRE  DIxPRE         0036900252+000162800000 "]
    df = b3.parse(antigo)
    assert len(df) == 1 and df["taxa"].iloc[0] == pytest.approx(16.28) and df["du"].iloc[0] == 252

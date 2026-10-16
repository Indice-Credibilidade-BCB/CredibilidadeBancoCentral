# -*- coding: utf-8 -*-
"""Testes das peças da bateria de 2026-10-15: quarentena na agregação e nível L5."""
import pandas as pd

import aggregate
import sandbox
from diagnostics.leakage import anonimizar, aplicar_anonimizacao


def test_excluir_sandbox_usa_manifesto_e_cai_para_hash():
    ids = [f"n{i:05d}" for i in range(400)]
    scores = pd.DataFrame({"item_id": ids, "d1": 3})
    manifesto = {"n00001", "n00002"}
    assert len(aggregate.excluir_sandbox(scores, manifesto)) == 398
    # sem manifesto: regra de hash (mesma que gera o manifesto)
    esperado = sum(not sandbox.em_sandbox(i) for i in ids)
    assert len(aggregate.excluir_sandbox(scores, set())) == esperado


def test_l5_mascara_numeros_termos_de_epoca_e_nomes():
    t = ("Em meio à pandemia de covid-19, o Copom cortou a Selic para 2% e Roberto Campos Neto "
         "disse que o teto de gastos segue crucial, segundo a XP Investimentos. O pixel não.")
    m = anonimizar(t, "L5")
    for vaza in ("pandemia", "covid", "2%", "Campos Neto", "teto de gastos", "XP"):
        assert vaza not in m, vaza
    assert "Copom" in m and "Selic" in m      # siglas do domínio ficam
    assert "pixel" in m                         # fronteira de palavra: não confunde com "Pix"
    assert anonimizar("O Copom manteve a taxa em 2015", "L1") == "O Copom manteve a taxa em [DATA]"


def test_l5_omite_veiculo_e_niveis_anteriores_mantem():
    df = pd.DataFrame({"veiculo": ["Money Times"], "titulo": ["Selic em 2016"], "lead": [""], "paragrafo_1": [""]})
    assert aplicar_anonimizacao(df, "L5")["veiculo"].iloc[0] == "não informado"
    assert aplicar_anonimizacao(df, "L4")["veiculo"].iloc[0] == "Money Times"

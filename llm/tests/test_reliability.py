# -*- coding: utf-8 -*-
"""Validação das métricas e smoke tests do pipeline."""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from reliability import kappa_quadratico, alpha_krippendorff_ordinal
from diagnostics.leakage import anonimizar, comparar_variantes, teste_sinteticos
import aggregate
import schema


def test_kappa():
    # concordância perfeita
    assert abs(kappa_quadratico([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) - 1.0) < 1e-9
    # caso à mão: 2 categorias efetivas, independência total => kappa 0
    k = kappa_quadratico([1, 1, 2, 2], [1, 2, 1, 2], cats=(1, 2))
    assert abs(k - 0.0) < 1e-9
    # discordância quase-total < 0
    assert kappa_quadratico([1, 1, 2, 5], [5, 5, 4, 1]) < 0
    print("kappa OK")


def test_alpha_vs_pacote():
    import krippendorff as kd
    rng = np.random.default_rng(0)
    for _ in range(5):
        a = rng.integers(1, 6, 40).astype(float)
        b = np.clip(a + rng.integers(-1, 2, 40), 1, 5).astype(float)
        b[rng.integers(0, 40, 4)] = np.nan  # faltantes
        mat = np.column_stack([a, b])
        meu = alpha_krippendorff_ordinal(mat)
        ref = kd.alpha(reliability_data=mat.T, level_of_measurement="ordinal",
                       value_domain=[1, 2, 3, 4, 5])
        assert abs(meu - ref) < 1e-9, (meu, ref)
    assert abs(alpha_krippendorff_ordinal(
        np.column_stack([[1, 2, 3, 4, 5], [1, 2, 3, 4, 5]])) - 1.0) < 1e-9
    print("alpha ordinal OK (bate com o pacote krippendorff)")


def test_agregacao_e_schema():
    corpus = pd.DataFrame({
        "item_id": ["a", "b", "c", "d"],
        "data_publicacao": ["2015-03-02", "2015-03-15", "2015-03-20", "2015-04-01"],
        "veiculo": ["Valor", "Folha", "Estadão", "Valor"],
        "tipo_veiculo": ["imprensa", "imprensa", "imprensa", "research"],
        "titulo": ["BC perde credibilidade", "Meta em risco, dizem analistas",
                   "BC perde credibilidade", "Meta será cumprida"],
        "lead": ["mercado cético", "focus sobe", "mercado cético", "confiança"],
        "paragrafo_1": ["", "", "", ""],
        "fonte_ref": ["u1", "u2", "u3", "u4"],
    })
    # itens 'a' e 'c' têm mesmo título+lead em veículos distintos => mesmo wire_cluster
    dd = schema.dedup(schema.validate(corpus))
    assert dd.loc[dd.item_id == "a", "wire_cluster"].iloc[0] == \
           dd.loc[dd.item_id == "c", "wire_cluster"].iloc[0]
    scores = pd.DataFrame({"item_id": list("abcd"), "d1": [2, 2, 4, 5],
                           "provider": "x", "model": "m", "prompt_version": "v1.0"})
    out = aggregate.agregar(scores, corpus)
    assert set(out.columns) >= {"mes", "c_llm", "c_llm_mediana", "ep", "n_itens"}
    assert (out["c_llm"].between(0, 1)).all()
    # março: cluster wire (a,c) colapsado => 2 observações, não 3
    assert out.loc[out["mes"].astype(str) == "2015-03", "n_itens"].iloc[0] == 2
    print("schema/dedup/agregação OK")


def test_leakage_utils():
    t = anonimizar("Campos Neto disse em 2022 que Lula erra", "L3")
    assert "[AUTORIDADE_BC]" in t and "[POLITICO]" in t and "[DATA]" in t
    base = pd.DataFrame({"item_id": list("abcd"), "d1": [1, 2, 3, 4]})
    alt = pd.DataFrame({"item_id": list("abcd"), "d1": [1, 3, 3, 5]})
    r = comparar_variantes(base, alt)
    assert r["pct_mudou"] == 0.5 and r["delta_abs_medio"] == 0.5
    s = pd.DataFrame({"item_id": range(8), "d1": [3, 3, 4, 3, 3, 3, 4, 3],
                      "texto_grupo": [f"g{i}" for i in range(4)] * 2,
                      "era": ["boa"] * 4 + ["ruim"] * 4})
    r5 = teste_sinteticos(s)
    assert "t_welch" in r5 and "p_pareado" in r5 and r5["n_pares"] == 4
    print("leakage utils OK")


if __name__ == "__main__":
    test_kappa()
    test_alpha_vs_pacote()
    test_agregacao_e_schema()
    test_leakage_utils()
    print("TODOS OS TESTES PASSARAM")

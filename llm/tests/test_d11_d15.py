# -*- coding: utf-8 -*-
"""Testes das pendências D11-D15 (ver docs/CONTEXTO..., Seção 4.2.9):
L4 numérico, T0 (temporal_probe), sandbox (D13), scorer duplo V-max/V-min
(D12), agregação dupla + delta_t, tendência em t (T2/T3) e T6 pós-2019.

Rodar: PYTHONPATH=. python -m pytest tests/test_d11_d15.py -q
"""
import pathlib
import tempfile

import numpy as np
import pandas as pd

import aggregate
import sandbox
from diagnostics import leakage, temporal_probe


def test_l4_mascara_numericos_preserva_direcao():
    t = ("Selic sobe para 14,25% diz BC em maio de 2015. Dólar fechou a "
         "R$ 4,10 e o IPCA acumula 10,67% no ano.")
    a = leakage.anonimizar(t, "L4")
    assert "[SELIC_NIVEL]" in a and "14,25" not in a
    assert "[CAMBIO_NIVEL]" in a and "4,10" not in a
    assert "[IPCA_NIVEL]" in a and "10,67" not in a
    assert "[DATA]" in a
    assert "sobe" in a and "fechou" in a and "acumula" in a, "direção apagada"


def test_l4_inclui_niveis_anteriores():
    t = "Campos Neto disse em 2022 que a Selic foi a 13,75%."
    a = leakage.anonimizar(t, "L4")
    assert "[AUTORIDADE_BC]" in a and "[DATA]" in a and "[SELIC_NIVEL]" in a


def test_anonimizar_aceita_nan():
    # bug pré-existente: NaN (float) é truthy; `texto or ""` não convertia.
    assert leakage.anonimizar(float("nan"), "L4") == ""
    assert leakage.anonimizar(None, "L3") == ""


def test_t0_cegueira_e_taxa_base():
    strata = [{"label": f"e{i}", "start": f"20{10+i}-01-01",
              "end": f"20{10+i}-12-31"} for i in range(6)]
    assert abs(temporal_probe.taxa_base_episodios(strata) - 1 / 6) < 1e-9

    reais = pd.to_datetime(["2012-06-01"] * 10 + ["2015-06-01"] * 10)
    # modelo cego: sempre chuta um ano fora de qualquer estrato do teste —
    # o palpite nem mapeia a um episódio (acurácia sai NaN, não 0), e isso
    # ainda conta como cegueira: não localizar sequer um episódio plausível
    # é sinal mais forte de cegueira, não uma lacuna do critério.
    cego = pd.DataFrame({"item_id": range(20), "ano_estimado": [2005] * 20,
                         "data_publicacao_real": reais})
    r_cego = temporal_probe.avaliar_t0(cego, strata)
    assert r_cego["eam"] >= temporal_probe.EAM_MIN_CEGUEIRA
    assert pd.isna(r_cego["acuracia_episodio"])
    assert r_cego["cego"] is True

    # modelo vidente: acerta o ano exato -> não é cego
    vidente = pd.DataFrame({"item_id": range(20), "ano_estimado": reais.year,
                            "data_publicacao_real": reais})
    r_vidente = temporal_probe.avaliar_t0(vidente, strata)
    assert r_vidente["eam"] == 0.0 and r_vidente["cego"] is False

    assert temporal_probe.nivel_minimo_cego(
        {"L1": r_vidente, "L2": r_vidente, "L3": r_cego, "L4": r_cego}) == "L3"
    assert temporal_probe.nivel_minimo_cego({"L1": r_vidente}) is None


def test_sandbox_determinista_e_estavel():
    df1 = pd.DataFrame({"item_id": [f"n{i:05d}" for i in range(3000)]})
    prod1, sb1 = sandbox.separar(df1)
    assert abs(len(sb1) / len(df1) - 0.10) < 0.02  # perto de 10%, hash aproxima

    # cresce o corpus: ids antigos não podem trocar de lado
    df2 = pd.concat([df1, pd.DataFrame(
        {"item_id": [f"n{i:05d}" for i in range(3000, 4000)]})], ignore_index=True)
    prod2, sb2 = sandbox.separar(df2)
    assert set(sb1["item_id"]) <= set(sb2["item_id"])
    assert set(prod1["item_id"]) <= set(prod2["item_id"])

    # manifesto: grava e é idempotente
    with tempfile.TemporaryDirectory() as d:
        caminho = pathlib.Path(d) / "sandbox_ids.csv"
        m1 = sandbox.congelar_manifesto(df1, caminho)
        m2 = sandbox.congelar_manifesto(df2, caminho)  # corpus cresceu
        assert set(m1["item_id"]) <= set(m2["item_id"])
        assert sandbox.carregar_manifesto(caminho) == set(m2["item_id"])


def test_prompt_hash_estavel_e_sensivel():
    import prompts
    assert isinstance(prompts.PROMPT_HASH, str) and len(prompts.PROMPT_HASH) == 16
    # determinístico: recalcular com o mesmo conteúdo dá o mesmo hash
    import hashlib
    esperado = hashlib.sha256("\n".join([
        prompts.PROMPT_VERSION, prompts.PROMPT_SISTEMA_PILOTO,
        prompts.PROMPT_SISTEMA_PRODUCAO, prompts.PROMPT_SISTEMA_T0,
        prompts.PROMPT_RELEVANCIA,
    ]).encode("utf-8")).hexdigest()[:16]
    assert prompts.PROMPT_HASH == esperado


def test_scorer_cache_key_sufixo_variante():
    import scorer
    k_vmax = scorer.cache_key("p", "m", "i", "piloto|real|nenhuma|vmax")
    k_vmin = scorer.cache_key("p", "m", "i", "piloto|real|L2|vmin")
    k_legado = scorer.cache_key("p", "m", "i", "piloto|real|nenhuma")
    assert len({k_vmax, k_vmin, k_legado}) == 3, "cada variante precisa de chave própria"


def test_agregar_vmax_vmin_e_delta_t():
    corpus = pd.DataFrame({
        "item_id": ["a", "b", "c", "d"],
        "data_publicacao": ["2015-03-02", "2015-03-15", "2015-03-20", "2015-04-01"],
        "veiculo": ["Valor", "Folha", "Estadão", "Valor"],
        "tipo_veiculo": ["imprensa", "imprensa", "imprensa", "research"],
        "titulo": ["BC perde credibilidade", "Meta em risco",
                   "BC ainda mais cético", "Meta cumprida"],
        "lead": ["x", "y", "z", "w"], "paragrafo_1": ["", "", "", ""],
        "fonte_ref": ["u1", "u2", "u3", "u4"],
    })
    scores = pd.DataFrame({
        "item_id": list("abcd") * 2,
        "d1": [2, 2, 4, 5, 3, 3, 4, 4],
        "variante_vazamento": ["vmax"] * 4 + ["vmin"] * 4,
    })
    out = aggregate.agregar_vmax_vmin(scores, corpus)
    assert {"c_llm_vmax", "c_llm_vmin", "c_llm", "delta_t"} <= set(out.columns)
    assert (out["c_llm"] == out["c_llm_vmax"]).all()
    assert np.allclose(out["delta_t"], out["c_llm_vmax"] - out["c_llm_vmin"])

    import pytest
    with pytest.raises(ValueError):
        aggregate.agregar(scores, corpus)  # sem filtrar variante, "d1" duplica por item -> ok
    only_vmax = scores[scores["variante_vazamento"] == "vmax"].drop(
        columns=["variante_vazamento"])
    with pytest.raises(ValueError):
        aggregate.agregar_vmax_vmin(only_vmax.assign(variante_vazamento="vmax"), corpus)


def test_comparar_variantes_tendencia_em_t():
    base = pd.DataFrame({"item_id": [f"i{i}" for i in range(20)], "d1": [3] * 20})
    # delta encolhe com o tempo: grande em itens antigos, ~0 em recentes
    datas = pd.to_datetime(["2005-01-01", "2010-01-01", "2015-01-01",
                            "2020-01-01", "2024-01-01"] * 4)
    deltas = ([2] * 4 + [2] * 4 + [1] * 4 + [0] * 4 + [0] * 4)
    alt = pd.DataFrame({"item_id": base["item_id"],
                        "d1": (base["d1"] + pd.Series(deltas)).clip(1, 5)})
    datas_idx = pd.Series(datas.values, index=base["item_id"])
    r = leakage.comparar_variantes(base, alt, datas=datas_idx)
    assert "tendencia_abs_delta_vs_t_corr" in r
    assert r["tendencia_abs_delta_vs_t_corr"] < 0, "esperada tendência negativa em t"


def test_t6_restrito_pos_2019():
    api = pd.DataFrame({"mes": ["2015-01", "2019-06", "2020-01", "2021-01"],
                        "c_llm": [0.9, 0.5, 0.5, 0.6]})
    local = pd.DataFrame({"mes": ["2015-01", "2019-06", "2020-01", "2021-01"],
                          "c_llm": [0.1, 0.5, 0.52, 0.58]})
    r = leakage.comparar_t6(api, local)
    assert r["n_meses"] == 3, "2015-01 deve ser descartado pelo corte de 2019"
    assert r["dif_abs_media"] < 0.05  # série pós-corte é quase idêntica


if __name__ == "__main__":
    test_l4_mascara_numericos_preserva_direcao(); print("L4 direção OK")
    test_l4_inclui_niveis_anteriores(); print("L4 cumulativo OK")
    test_anonimizar_aceita_nan(); print("anonimizar NaN OK")
    test_t0_cegueira_e_taxa_base(); print("T0 OK")
    test_sandbox_determinista_e_estavel(); print("sandbox OK")
    test_prompt_hash_estavel_e_sensivel(); print("prompt hash OK")
    test_scorer_cache_key_sufixo_variante(); print("cache key sufixo OK")
    test_agregar_vmax_vmin_e_delta_t(); print("agregação dupla OK")
    test_comparar_variantes_tendencia_em_t(); print("tendência em t OK")
    test_t6_restrito_pos_2019(); print("T6 pós-2019 OK")
    print("D11-D15: TODOS OS TESTES PASSARAM")

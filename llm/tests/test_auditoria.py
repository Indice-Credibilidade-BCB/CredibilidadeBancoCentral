# -*- coding: utf-8 -*-
"""Testes de regressão da auditoria de 2026-08-18.

Cada teste trava um bug encontrado: se voltar, o teste quebra.
Rodar: PYTHONPATH=. python tests/test_auditoria.py
"""
import numpy as np
import pandas as pd

import aggregate
import reliability
import scorer
from diagnostics import leakage


def test_fe_desbalanceada():
    """Painel desbalanceado (research entra tarde): gamma deve recuperar o
    efeito de tipo SEM contaminar pelo efeito-época. O demeaning de uma
    passada (versão antiga) falha aqui; o iterativo acerta."""
    rng = np.random.default_rng(0)
    meses = pd.period_range("2010-01", periods=24, freq="M")
    alpha = {m: 0.4 + 0.2 * (i >= 12) for i, m in enumerate(meses)}  # regime muda
    linhas = []
    for i, m in enumerate(meses):
        for _ in range(6):
            linhas.append({"mes": m, "tipo_veiculo": "imprensa",
                           "c": alpha[m] + 0.0 + rng.normal(0, 0.01)})
        if i >= 12:  # research SÓ na segunda metade (época de alpha alto)
            for _ in range(6):
                linhas.append({"mes": m, "tipo_veiculo": "research",
                               "c": alpha[m] - 0.10 + rng.normal(0, 0.01)})
    df = pd.DataFrame(linhas)
    gamma = aggregate._fe_tipo_iterativa(df)
    dif = gamma["research"] - gamma["imprensa"]
    assert abs(dif - (-0.10)) < 0.02, f"gamma contaminado pela época: {dif:.3f}"
    # nível preservado: média ponderada dos gammas = 0
    w = df["tipo_veiculo"].value_counts(normalize=True)
    assert abs((gamma * w).sum()) < 1e-8


def test_anonimizar_fronteira_e_caixa():
    t = ("Temer criticou o BC; há razões para temer a inflação. "
         "A fragata passou; Fraga elogiou. TEMER FALA HOJE. "
         "Ilan reforçou a meta em 12 de maio de 2016.")
    a = leakage.anonimizar(t, "L3")
    assert "[POLITICO] criticou" in a
    assert "para temer a inflação" in a, "verbo 'temer' foi mascarado"
    assert "fragata" in a, "'fragata' foi mascarada"
    assert "[AUTORIDADE_BC] elogiou" in a
    assert "[POLITICO] FALA HOJE" in a, "ALL-CAPS não coberto"
    assert "[AUTORIDADE_BC] reforçou" in a and "[DATA]" in a


def test_datas_refletidas():
    df = pd.DataFrame({
        "item_id": ["a", "b", "c"],
        # a: +5a estouraria o futuro -> deve virar -5a
        # b: -5a cairia antes do regime -> deve virar +5a (posição ímpar = -)
        # c: qualquer direção cabe
        "data_publicacao": ["2024-06-01", "2001-03-01", "2012-05-10"],
    })
    out = leakage.gerar_variantes_data(df, anos_offset=5)
    falsas = pd.to_datetime(out["data_falsa"])
    hoje = pd.Timestamp.today().normalize()
    assert (falsas >= leakage.REGIME_INICIO).all(), "data antes do regime"
    assert (falsas <= hoje).all(), "data no futuro"
    assert falsas.iloc[0] == pd.Timestamp("2019-06-01")
    assert falsas.iloc[1] == pd.Timestamp("2006-03-01")


def test_t5_pareado():
    # 12 pares; era ruim sistematicamente 1 ponto abaixo em 10 dos 12
    rows = []
    for g in range(12):
        rows.append({"item_id": f"{g}a", "texto_grupo": f"g{g}", "era": "boa",
                     "d1": 4})
        rows.append({"item_id": f"{g}b", "texto_grupo": f"g{g}", "era": "ruim",
                     "d1": 3 if g < 10 else 4})
    res = leakage.teste_sinteticos(pd.DataFrame(rows))
    assert res["n_pares"] == 12
    assert res["dif_media_pareada"] < 0
    assert res["p_pareado"] < 0.05, "pareado deveria detectar o vazamento"
    assert "p_welch" in res
    # sem diferença -> não significativo
    rows2 = [{"item_id": f"{g}{e}", "texto_grupo": f"g{g}", "era": era, "d1": 3}
             for g in range(12) for e, era in (("a", "boa"), ("b", "ruim"))]
    res2 = leakage.teste_sinteticos(pd.DataFrame(rows2))
    assert res2.get("p_pareado", 1.0) > 0.05


def test_relatorio_coercao(tmp="/tmp/anot_teste.csv"):
    df = pd.DataFrame({
        "anot1_d1": [1, 2, "3", 4, 5, ""],       # texto e vazio
        "anot2_d1": [1, 2, 3, 4, 5, 2],
        "anot1_d2": [7, 2, 3, "", 5, 1],         # 7 = fora da escala
        "anot2_d2": [1, 2, 3, 4, 5, 1],
        "contexto_insuficiente": ["", "TRUE", "", "sim", "", ""],
    })
    df.to_csv(tmp, index=False)
    out = reliability.relatorio_piloto(tmp)
    assert out["kappa_qw_d1"] > 0.9
    assert any("fora de 1–5" in a for a in out.get("avisos", []))
    assert abs(out["pct_contexto_insuficiente"] - 2 / 6) < 1e-9
    assert 0 <= out["concord_bruta_d1"] <= 1


def test_halo_regra():
    idx = ["d1", "d2", "d3"]
    llm = pd.DataFrame([[1, .9, .2], [.9, 1, .1], [.2, .1, 1]], index=idx, columns=idx)
    hum = pd.DataFrame([[1, .5, .2], [.5, 1, .1], [.2, .1, 1]], index=idx, columns=idx)
    r = reliability.checar_halo(llm, hum)
    assert r["halo_alerta"] and r["pares"][0]["par"] == "d1xd2"
    assert not reliability.checar_halo(hum, hum)["halo_alerta"]


def test_parser_float_integral():
    ok = scorer.parse_json_resposta('{"d1": 4.0, "d2": null, "d3": 2}')
    assert ok["d1"] == 4 and ok["d3"] == 2 and ok["d2"] is None
    assert scorer.parse_json_resposta('{"d1": 4.5}') is None
    assert scorer.parse_json_resposta('{"d1": true}') is None


def test_parser_d1_nulo_vira_neutro():
    """Achado real rodando o Sabiá (01/09/2026): o provedor às vezes devolve
    d1=null (em vez de 3) quando não vê menção ao BCB/meta. D1 nunca deveria
    ser nulo (D4); coagir para 3 evita perder ~40% dos itens como
    'parse_falhou' só porque o provedor não seguiu a instrução à risca."""
    ok = scorer.parse_json_resposta(
        '{"d1": null, "d2": null, "d2_sem_sinal": true, "d3": 3, "d3_sem_sinal": false}')
    assert ok["d1"] == 3
    assert ok["d3"] == 3
    # d1 ausente da resposta (não só null) tem que cair na mesma regra
    ok2 = scorer.parse_json_resposta('{"d2": 2}')
    assert ok2["d1"] == 3
    # mas d1 fora da escala (resposta de fato garbled) continua falha real
    assert scorer.parse_json_resposta('{"d1": 7}') is None


def test_scorer_variante_inclui_modo():
    k1 = scorer.cache_key("p", "m", "i", "piloto|real|nenhuma")
    k2 = scorer.cache_key("p", "m", "i", "producao|real|nenhuma")
    assert k1 != k2


def test_carregar_scores_dedup(tmp="/tmp/scores_teste.jsonl"):
    import json
    recs = [
        {"cache_key": "k1", "item_id": "a", "d1": None, "erro": "parse_falhou"},
        {"cache_key": "k1", "item_id": "a", "d1": 4, "erro": None},   # reprocessado
        {"cache_key": "k2", "item_id": "b", "d1": 2, "erro": None},
    ]
    with open(tmp, "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    df = aggregate.carregar_scores(tmp)
    assert len(df) == 2 and set(df["item_id"]) == {"a", "b"}
    assert int(df.loc[df["item_id"] == "a", "d1"].iloc[0]) == 4


if __name__ == "__main__":
    test_fe_desbalanceada(); print("FE desbalanceada OK")
    test_anonimizar_fronteira_e_caixa(); print("anonimização fronteira/caixa OK")
    test_datas_refletidas(); print("date-swap refletido OK")
    test_t5_pareado(); print("T5 pareado OK")
    test_relatorio_coercao(); print("relatório com coerção OK")
    test_halo_regra(); print("regra de halo OK")
    test_parser_float_integral(); print("parser float integral OK")
    test_parser_d1_nulo_vira_neutro(); print("parser d1 nulo -> neutro OK")
    test_scorer_variante_inclui_modo(); print("variante inclui modo OK")
    test_carregar_scores_dedup(); print("dedup de retomada OK")
    print("AUDITORIA: TODOS OS TESTES PASSARAM")

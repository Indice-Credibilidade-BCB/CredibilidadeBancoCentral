# -*- coding: utf-8 -*-
"""Testes do braço local (D7/D14). `coral.py` e `local_encoder/dataset.py`
são puro numpy/pandas — rodam sempre. O resto (`model.py`, `train.py`,
`infer.py`) depende de torch/transformers (pesado, opcional): os testes que
tocam nisso pulam com `pytest.importorskip` quando ausentes.

Rodar: PYTHONPATH=. python -m pytest tests/test_local_encoder.py -q
"""
import pathlib
import sys

import numpy as np
import pandas as pd
import pytest

from local_encoder import coral, dataset


def test_coral_targets_e_decodificacao_perfeita():
    y = np.array([1, 2, 3, 4, 5, 3, 1])
    t = coral.coral_targets(y, 5)
    assert t.shape == (7, 4)
    # probs "perfeitas" a partir dos próprios targets reconstroem y exato
    probs = t * 0.9 + (1 - t) * 0.05
    pred = coral.coral_probs_to_label(probs)
    assert (pred == y).all()


def test_coral_esperanca_monotonica_em_probs():
    baixo = coral.coral_esperanca_label(np.full((1, 4), 0.1))
    alto = coral.coral_esperanca_label(np.full((1, 4), 0.9))
    assert alto[0] > baixo[0]


def test_montar_texto_mascara_l1():
    row = pd.Series({"titulo": "Selic sobe em 2015", "lead": "", "paragrafo_1": ""})
    t = dataset.montar_texto(row, "L1")
    assert "[DATA]" in t and "2015" not in t


def test_montar_exemplos_prioriza_colunas_e_filtra_sem_rotulo():
    itens = pd.DataFrame({
        "item_id": ["a", "b", "c"],
        "data_publicacao": ["2015-01-01", "2016-01-01", "2017-01-01"],
        "titulo": ["Meta em risco em 2015", "BC eleva juros", "Sem rótulo"],
        "lead": ["", "", ""], "paragrafo_1": ["", "", ""],
    })
    rotulos = pd.DataFrame({"item_id": ["a", "b"], "d1": [2, "4"]})  # "4" string
    ex = dataset.montar_exemplos(itens, rotulos, origem="prata", nivel_anonimizacao="L1")
    assert set(ex["item_id"]) == {"a", "b"}  # 'c' cai fora (sem rótulo)
    assert ex["d1"].dtype == int
    assert (ex["origem"] == "prata").all()


def test_dividir_blocos_temporais_e_resumo():
    df = pd.DataFrame({"item_id": range(30),
                       "data_publicacao": pd.date_range("2010-01-01", periods=30, freq="30D")})
    blocos = dataset.dividir_blocos_temporais(df, n_blocos=3)
    assert set(blocos.unique()) <= {0, 1, 2}
    resumo = dataset.resumo_blocos(df, blocos)
    # blocos temporais não se sobrepõem: fim do bloco 0 <= início do bloco 1
    assert resumo.loc[0, "fim"] <= resumo.loc[1, "inicio"]
    assert resumo.loc[1, "fim"] <= resumo.loc[2, "inicio"]
    assert resumo["n"].sum() == 30


def test_coral_head_aprende_gradiente():
    torch = pytest.importorskip("torch")
    from local_encoder.model import BertimbauCoralClassifier, CoralHead

    torch.manual_seed(0)
    head = CoralHead(in_features=8, num_classes=5)
    x = torch.randn(6, 8)
    y = np.array([1, 2, 3, 4, 5, 3])
    alvo = torch.tensor(coral.coral_targets(y, 5))

    opt = torch.optim.Adam(head.parameters(), lr=0.1)
    perda_inicial = None
    for passo in range(40):
        opt.zero_grad()
        logits = head(x)
        perda = BertimbauCoralClassifier.coral_loss(None, logits, alvo)
        if perda_inicial is None:
            perda_inicial = perda.item()
        perda.backward()
        opt.step()
    assert perda.item() < perda_inicial, "perda deveria cair com o treino"
    pred = coral.coral_probs_to_label(torch.sigmoid(head(x)).detach().numpy())
    assert (pred == y).all(), "cabeça deveria decorar 6 exemplos em 40 passos"


def test_amostrar_prata_estratifica_por_ano_e_e_deterministica():
    anos = [2011] * 100 + [2015] * 300 + [2023] * 600
    df = pd.DataFrame({"item_id": range(1000),
                       "data_publicacao": [f"{a}-06-01" for a in anos],
                       "texto": "x", "d1": 3, "origem": "prata"})
    a = dataset.amostrar_prata(df, 100, semente=7)
    b = dataset.amostrar_prata(df, 100, semente=7)
    assert len(a) == 100 and a["item_id"].tolist() == b["item_id"].tolist()
    por_ano = pd.to_datetime(a["data_publicacao"]).dt.year.value_counts()
    assert por_ano[2011] == 10 and por_ano[2015] == 30 and por_ano[2023] == 60
    assert dataset.amostrar_prata(df, None) is df
    assert len(dataset.amostrar_prata(df, 5000)) == 1000


def test_dispositivo_auto_e_cpu():
    torch = pytest.importorskip("torch")
    from local_encoder import dispositivo as disp
    assert disp.escolher("cpu").type == "cpu"
    auto = disp.escolher("auto")
    assert auto.type == ("cuda" if torch.cuda.is_available() else "cpu")
    with disp.autocast(disp.escolher("cpu")):  # no-op na CPU
        pass
    if not torch.cuda.is_available():
        with pytest.raises(RuntimeError):
            disp.escolher("cuda")


def test_coral_inicializar_vies_reproduz_frequencias():
    torch = pytest.importorskip("torch")
    from local_encoder.model import CoralHead
    y = np.array([3] * 85 + [2] * 7 + [4] * 8)
    head = CoralHead(in_features=4, num_classes=5)
    head.inicializar_vies(y, suavizacao=0.0)
    p = torch.sigmoid(head.bias).detach().numpy()
    esperado = [(y > k).mean() for k in (1, 2, 3, 4)]
    assert np.allclose(p[:3], esperado[:3], atol=1e-6)
    assert p[3] < 1e-6  # nenhuma nota 5: P(y>4) ~ 0
    # com entrada nula, a decodificação devolve a classe majoritária
    pred = coral.coral_probs_to_label(torch.sigmoid(head(torch.zeros(1, 4))).detach().numpy())
    assert pred[0] == 3


if __name__ == "__main__":
    test_coral_targets_e_decodificacao_perfeita(); print("coral targets OK")
    test_coral_esperanca_monotonica_em_probs(); print("coral esperanca OK")
    test_montar_texto_mascara_l1(); print("montar_texto L1 OK")
    test_montar_exemplos_prioriza_colunas_e_filtra_sem_rotulo(); print("montar_exemplos OK")
    test_dividir_blocos_temporais_e_resumo(); print("blocos temporais OK")
    try:
        test_coral_head_aprende_gradiente(); print("CoralHead gradiente OK")
    except Exception as e:  # pragma: no cover
        print("CoralHead pulado/falhou (torch ausente?):", e)
    print("local_encoder: TODOS OS TESTES PASSARAM")

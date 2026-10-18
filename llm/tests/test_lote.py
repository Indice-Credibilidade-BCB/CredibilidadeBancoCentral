# -*- coding: utf-8 -*-
"""Pontuação em lote: formação dos lotes, parser da saída compacta, mensagem."""
import pandas as pd

import lote
import prompts


def test_formar_lotes_tamanho_e_cobertura():
    df = pd.DataFrame({"item_id": [f"i{k}" for k in range(25)]})
    ls = lote.formar_lotes(df, 10)
    assert [len(x) for x in ls] == [10, 10, 5]
    assert sorted(pd.concat(ls)["item_id"]) == sorted(df["item_id"])


def test_formar_lotes_separa_pares():
    df = pd.DataFrame({"item_id": [f"s{k}{e}" for k in range(12) for e in "ab"],
                       "texto_grupo": [f"g{k}" for k in range(12) for _ in "ab"]})
    for l in lote.formar_lotes(df, 10, separar_por="texto_grupo"):
        assert l["texto_grupo"].is_unique  # os dois textos de um par nunca no mesmo lote


def test_parse_lote_formatos_e_faltantes():
    txt = "1|4|3|-\n2|S|-|-\n[3] | 2 | 2 | 1\n4|7|-|-\nlixo\n2|5|5|5"
    r = lote.parse_lote(txt, 5)
    assert r[1] == {"d1": 4, "d1_sem_sinal": False, "d2": 3, "d3": None}
    assert r[2]["d1"] is None and r[2]["d1_sem_sinal"] is True   # primeira ocorrência vale
    assert r[3]["d1"] == 2 and r[3]["d3"] == 1
    assert 4 not in r and 5 not in r                              # fora da escala / ausente
    assert lote.parse_lote("1|4|-|-", 0) == {}


def test_mensagem_lote_numera_e_prompt_mantem_corpo():
    itens = [{"data_publicacao": "2015-03-02", "veiculo": "Valor", "titulo": "A", "lead": "", "paragrafo_1": ""},
             {"data_publicacao": "2018-03-02", "veiculo": "Valor", "titulo": "B", "lead": "", "paragrafo_1": ""}]
    m = prompts.build_user_msg_lote(itens)
    assert "### TRECHO 1" in m and "### TRECHO 2" in m and m.index("TÍTULO: A") < m.index("TÍTULO: B")
    corpo = prompts.PROMPT_SISTEMA_PRODUCAO_V11.split("Responda SOMENTE")[0]
    assert prompts.PROMPT_SISTEMA_LOTE_V11.startswith(corpo)


def test_limiar_do_filtro_garante_sensibilidade():
    import numpy as np
    from local_encoder.filtro_sinal import escolher_limiar
    rng = np.random.default_rng(0)
    y = rng.random(1000) < 0.25
    p = np.clip(np.where(y, 0.7, 0.2) + rng.normal(0, 0.15, 1000), 0, 1)
    t = escolher_limiar(p, y, 0.95)
    assert (p[y] >= t).mean() >= 0.95          # perde no máximo 5% do sinal
    assert (p[~y] < t).mean() > 0.5            # e ainda descarta a maioria dos sem sinal


def test_parse_lote_aceita_S_e_traco_trocados():
    r = lote.parse_lote("1|-|-|2\n2|4|S|S\n3|S|3|-", 3)
    assert r[1]["d1"] is None and r[1]["d1_sem_sinal"] is True and r[1]["d3"] == 2
    assert r[2] == {"d1": 4, "d1_sem_sinal": False, "d2": None, "d3": None}
    assert r[3]["d2"] == 3

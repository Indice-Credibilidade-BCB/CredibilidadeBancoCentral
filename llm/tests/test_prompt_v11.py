# -*- coding: utf-8 -*-
"""Prompt v1.1 (2026-10-18): D1 com "sem sinal"; v1.0 preservada para o apêndice."""
import json

import pandas as pd

import aggregate
import prompts
import scorer


def test_v10_preservada_com_hash_congelado():
    assert prompts.PROMPT_HASH_V10 == "9515662efc0dbc2e"
    assert prompts.PROMPT_VERSION == "v1.1" and prompts.PROMPT_HASH == prompts.PROMPT_HASH_V11
    assert prompts.PROMPT_HASH_V11 != prompts.PROMPT_HASH_V10
    v10, v11 = prompts.PROMPT_SISTEMA_PRODUCAO_V10, prompts.PROMPT_SISTEMA_PRODUCAO_V11
    # só a D1 e o formato de saída mudam; D2, D3 e regras ficam idênticas
    assert v10[v10.index("D2 —"):v10.index("Responda")] == v11[v11.index("D2 —"):v11.index("Responda")]
    assert "d1_sem_sinal = true" in v11 and "d1_sem_sinal" not in v10


def test_parse_v11_aceita_sem_sinal_e_v10_mantem_regra_antiga():
    r = scorer.parse_json_resposta('{"d1": null, "d1_sem_sinal": true, "d2": null, "d3": null}', "v1.1")
    assert r["d1"] is None and r["d1_sem_sinal"] is True
    r = scorer.parse_json_resposta('{"d1": 4, "d1_sem_sinal": false, "d2": 3, "d3": null}', "v1.1")
    assert r["d1"] == 4 and r["d1_sem_sinal"] is False
    assert scorer.parse_json_resposta('{"d1": 9}', "v1.1") is None
    assert scorer.parse_json_resposta('{"d1": null}', "v1.0")["d1"] == 3  # v1.0: nulo vira 3


def test_cache_key_separa_versoes():
    a = scorer.cache_key("gemini", "m", "x1", "producao|real|nenhuma", "v1.0")
    b = scorer.cache_key("gemini", "m", "x1", "producao|real|nenhuma", "v1.1")
    assert a != b


def test_retomada_trata_sem_sinal_como_feito(tmp_path):
    p = tmp_path / "s.jsonl"
    recs = [{"cache_key": "k1", "erro": None, "d1": None, "d1_sem_sinal": True},
            {"cache_key": "k2", "erro": None, "d1": 3, "d1_sem_sinal": False},
            {"cache_key": "k3", "erro": "parse_falhou", "d1": None}]
    p.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    assert scorer._carregar_ja_feitos(p) == {"k1", "k2"}


def test_carregar_scores_mantem_sem_sinal(tmp_path):
    p = tmp_path / "s.jsonl"
    recs = [{"cache_key": "k1", "item_id": "a", "d1": None, "d1_sem_sinal": True, "erro": None},
            {"cache_key": "k2", "item_id": "b", "d1": 4, "d1_sem_sinal": False, "erro": None},
            {"cache_key": "k3", "item_id": "c", "d1": None, "d1_sem_sinal": None, "erro": "x"}]
    p.write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    s = aggregate.carregar_scores(str(p))
    assert set(s["item_id"]) == {"a", "b"}


def test_parse_recupera_json_com_aspas_duplicadas():
    for raw in ('{\n  "d1": null,\n  ""d1_sem_sinal": true,\n  "d2": null,\n  "d3": null\n}',
                '{\n  "d1": null,\n  " "d1_sem_sinal": true,\n  "d2": 3,\n  "d3": null\n}'):
        r = scorer.parse_json_resposta(raw, "v1.1")
        assert r is not None and r["d1"] is None and r["d1_sem_sinal"] is True
    r = scorer.parse_json_resposta('{"d1": 4,, "d1_sem_sinal": false}', "v1.1")
    assert r["d1"] == 4 and r["d1_sem_sinal"] is False
    assert scorer.parse_json_resposta('{"x": oops}', "v1.1") is None

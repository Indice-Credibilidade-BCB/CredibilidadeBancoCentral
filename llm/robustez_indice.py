# -*- coding: utf-8 -*-
"""Robustez da construção do índice v1.1 (artigo, seções 5 e 7.5).

Tudo é reagregação das notas já existentes: nenhuma chamada nova ao LLM.

- Composição de veículos (seção 5): o corpus muda muito no tempo (até 2015
  só InfoMoney e Valor). Três versões contra a principal:
    * constante: só os veículos presentes em toda a série (calculado do corpus);
    * so_originais: só os 5 veículos do corpus antes das fontes novas;
    * sem_<fonte>: o índice sem cada fonte nova, uma de cada vez;
    * fe_veiculo: efeito fixo por VEÍCULO (a principal ajusta só por tipo,
      e hoje todo o corpus é "imprensa", então o ajuste é nulo). Como o
      veículo passa a fazer o papel do tipo, o colapso de wire entre
      veículos diferentes também muda: a diferença não é só o efeito fixo;
    * um veículo por vez (InfoMoney, Valor).
- Tempo real (seção 7.5): o pré-filtro foi treinado com rótulos do período
  inteiro, então a triagem de uma notícia de 2015 usou exemplos de 2024. A
  amostra aleatória de rotulagem (~15% da produção) foi pontuada INTEIRA,
  sem passar pelo filtro: o índice feito só com ela não depende do filtro.

Registro prévio: docs/local, seção 4.2.17, itens 1 e 5.
Uso (de dentro de llm/):  python robustez_indice.py
"""
from __future__ import annotations

import json
import pathlib

import pandas as pd

import aggregate
import schema

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DERIV = RAIZ / "dados" / "derivados"
PRODUCAO = RAIZ / "dados" / "llm" / "producao_v11"
ORIGINAIS = ("Valor", "O Globo", "InfoMoney", "Money Times", "Poder360")   # corpus antes de 4.2.20


def constantes(corpus: pd.DataFrame) -> list[str]:
    """Veículos com notícia em todos os anos da janela (antes: InfoMoney e Valor)."""
    anos = pd.to_datetime(corpus["data_publicacao"], format="mixed").dt.year
    por = corpus.assign(ano=anos).groupby("veiculo")["ano"].nunique()
    return sorted(por[por == anos.nunique()].index)


def _scores_e_corpus() -> tuple[pd.DataFrame, pd.DataFrame]:
    sc = aggregate.excluir_sandbox(aggregate.carregar_scores(str(PRODUCAO / "consolidado_vmax.jsonl")))
    corpus = pd.read_parquet(RAIZ / "dados" / "llm" / "corpus.parquet")
    return sc, corpus


def _serie(sc: pd.DataFrame, corpus: pd.DataFrame, janela: int) -> pd.DataFrame:
    # Para o efeito fixo por veículo, o nome do veículo ocupa a coluna de tipo;
    # a validação do esquema só aceita os tipos oficiais, então os nomes são
    # aceitos SÓ durante esta chamada.
    tipos_originais = schema.TIPOS_VALIDOS
    schema.TIPOS_VALIDOS = tipos_originais | set(corpus["tipo_veiculo"].unique())
    try:
        out = aggregate._agregar_core(sc, corpus, janela=janela)
    finally:
        schema.TIPOS_VALIDOS = tipos_originais
    out["mes"] = out["mes"].astype(str)
    return out


def ids_rotulagem() -> set[str]:
    """Notícias da amostra aleatória de rotulagem (pontuadas sem passar pelo filtro)."""
    ids = set()
    with open(PRODUCAO / "consolidado_vmax.jsonl", encoding="utf-8") as f:
        for linha in f:
            r = json.loads(linha)
            if r.get("origem") == "api_rotulagem":
                ids.add(str(r["item_id"]))
    return ids


def versoes() -> dict[str, dict[int, pd.DataFrame]]:
    """{nome: {janela: série}} para janela 1 (mensal) e 3 (jm3)."""
    sc, corpus = _scores_e_corpus()
    corpus_fe = corpus.assign(tipo_veiculo=corpus["veiculo"])
    rot = ids_rotulagem()
    receitas = {
        "constante": (sc, corpus[corpus["veiculo"].isin(constantes(corpus))]),
        "so_originais": (sc, corpus[corpus["veiculo"].isin(ORIGINAIS)]),
        "fe_veiculo": (sc, corpus_fe),
        "so_infomoney": (sc, corpus[corpus["veiculo"] == "InfoMoney"]),
        "so_valor": (sc, corpus[corpus["veiculo"] == "Valor"]),
        "amostra_aleatoria": (sc[sc["item_id"].astype(str).isin(rot)], corpus),
    }
    for v in sorted(set(corpus["veiculo"]) - set(ORIGINAIS)):   # robustez "sem a fonte" (4.2.20)
        receitas["sem_" + v.lower().replace(" ", "_")] = (sc, corpus[corpus["veiculo"] != v])
    return {nome: {j: _serie(s, c, j) for j in (1, 3)} for nome, (s, c) in receitas.items()}


def comparar(series: dict[str, dict[int, pd.DataFrame]]) -> pd.DataFrame:
    """Correlação e diferença média de cada versão contra a principal."""
    principal = {1: pd.read_csv(DERIV / "indice_mensal_v11_sabia.csv"),
                 3: pd.read_csv(DERIV / "indice_mensal_v11_sabia_jm3.csv")}
    linhas = []
    for nome, por_j in series.items():
        for j, s in por_j.items():
            m = principal[j][["mes", "c_llm"]].merge(s[["mes", "c_llm", "n_itens"]], on="mes", suffixes=("_principal", "_versao"))
            m = m.dropna(subset=["c_llm_principal", "c_llm_versao"])
            linhas.append({"versao": nome, "agregacao": "mensal" if j == 1 else "jm3", "n_meses": len(m),
                           "corr": m["c_llm_principal"].corr(m["c_llm_versao"]),
                           "dif_media": (m["c_llm_versao"] - m["c_llm_principal"]).mean(),
                           "dif_abs_media": (m["c_llm_versao"] - m["c_llm_principal"]).abs().mean(),
                           "noticias_por_mes_mediana": m["n_itens"].median()})
    return pd.DataFrame(linhas)


def main() -> pd.DataFrame:
    series = versoes()
    for nome, por_j in series.items():
        for j, s in por_j.items():
            s.to_csv(DERIV / f"indice_mensal_v11_sabia_{nome}{'' if j == 1 else '_jm3'}.csv", index=False)
    tab = comparar(series)
    tab.to_csv(DERIV / "robustez_indice_v11.csv", index=False)
    return tab


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(main().round(3).to_string(index=False))

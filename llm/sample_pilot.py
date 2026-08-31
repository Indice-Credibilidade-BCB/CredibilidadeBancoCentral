# -*- coding: utf-8 -*-
"""Amostragem do piloto (Etapa 2).

- Estratificada por episódio (config.pilot.strata): tensão + calmaria, para
  garantir variação de credibilidade na amostra (κ despenca artificialmente
  se todo item for "3 — neutro").
- Só itens relevantes (relevance.prefiltro) entram no sorteio principal.
- Gera duas planilhas idênticas (uma por anotador) com colunas em branco:
  anotação independente e cega — cada anotador NÃO vê as notas do outro.
- Anexa n_validacao_filtro itens limítrofes/procedurais para validar o filtro.

Uso: python sample_pilot.py  (lê paths do config.yaml)
"""
from __future__ import annotations

import pathlib

import pandas as pd
import yaml

import relevance
import schema

ROOT = pathlib.Path(__file__).parent


def amostrar() -> None:
    cfg = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    seed = cfg["pilot"]["seed"]
    corpus_path = ROOT / cfg["paths"]["corpus"]
    df = (pd.read_parquet(corpus_path) if corpus_path.suffix == ".parquet"
          else pd.read_csv(corpus_path))
    df = schema.dedup(schema.validate(df))
    df = relevance.prefiltro(df)
    rel = df[df["relevante_regex"]].copy()
    rel["data_dt"] = pd.to_datetime(rel["data_publicacao"])

    partes = []
    for estrato in cfg["pilot"]["strata"]:
        janelas = estrato.get("windows") or [[estrato["start"], estrato["end"]]]
        mask = False
        for ini, fim in janelas:
            mask = mask | ((rel["data_dt"] >= ini) & (rel["data_dt"] <= fim))
        pool = rel[mask]
        n = min(estrato["n"], len(pool))
        if n < estrato["n"]:
            print(f"AVISO: estrato '{estrato['label']}' tem só {len(pool)} itens.")
        amostra = pool.sample(n=n, random_state=seed)
        amostra["estrato"] = estrato["label"]
        partes.append(amostra)

    piloto = pd.concat(partes).sample(frac=1, random_state=seed)  # embaralha ordem

    # Itens de validação do filtro: REJEITADOS pelo regex, priorizando os
    # verdadeiramente limítrofes (mencionam economia sem os termos do INCLUIR).
    # Rejeitado aleatório tende a ser esporte/polícia — não testa nada.
    rej = df[~df["relevante_regex"]].copy()
    vizinhos = rej["titulo"].fillna("").str.cat(
        [rej["lead"].fillna(""), rej["paragrafo_1"].fillna("")], sep=" "
    ).str.contains(r"juros|infla[çc][ãa]o|d[óo]lar|c[âa]mbio|\bpib\b|fazenda",
                   case=False, regex=True)
    n_borda = min(cfg["pilot"]["n_validacao_filtro"], len(rej))
    n_viz = min(int(vizinhos.sum()), n_borda)
    borda = pd.concat([
        rej[vizinhos].sample(n=n_viz, random_state=seed),
        rej[~vizinhos].sample(n=n_borda - n_viz, random_state=seed),
    ])
    borda["estrato"] = "validacao_filtro"

    out_dir = ROOT / cfg["paths"]["pilot_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    base_cols = ["item_id", "data_publicacao", "veiculo", "tipo_veiculo",
                 "titulo", "lead", "paragrafo_1", "estrato"]
    piloto[base_cols].to_csv(out_dir / "pilot_items.csv", index=False)
    borda[base_cols].to_csv(out_dir / "pilot_validacao_filtro.csv", index=False)

    # Planilhas de anotação: SEM a coluna estrato (o rótulo "crise 2008"
    # revelaria a era e contaminaria a anotação e o T2-H) e com ORDEM
    # EMBARALHADA INDEPENDENTEMENTE por anotador (ordem idêntica correlaciona
    # fadiga/ancoragem sequencial entre anotadores e infla o kappa).
    anot_cols = [c for c in base_cols if c != "estrato"]
    for i, anot in enumerate(("anotador1", "anotador2"), start=1):
        planilha = piloto[anot_cols].sample(frac=1, random_state=seed + i).copy()
        for c in ("d1", "d2", "d2_sem_sinal", "d3", "d3_sem_sinal",
                  "contexto_insuficiente", "obs"):
            planilha[c] = ""
        planilha.to_csv(out_dir / f"anotacao_{anot}.csv", index=False)

    # T2-H (look-ahead humano): 15 itens re-anotados com data omitida e
    # nomes mascarados (L2). Gerada AGORA, junto com o piloto, para que a
    # subamostra fique pré-registrada antes de qualquer anotação.
    from diagnostics.leakage import aplicar_anonimizacao
    n_t2h = min(15, len(piloto))
    t2h = piloto[anot_cols].sample(n=n_t2h, random_state=seed + 99).copy()
    t2h = aplicar_anonimizacao(t2h, "L2")
    t2h["data_publicacao"] = "nao informada"
    t2h = t2h.sample(frac=1, random_state=seed + 100)
    for c in ("d1", "d2", "d2_sem_sinal", "d3", "d3_sem_sinal",
              "contexto_insuficiente", "obs"):
        t2h[c] = ""
    t2h.to_csv(out_dir / "anotacao_T2H.csv", index=False)

    print(f"Piloto: {len(piloto)} itens + {len(borda)} de validação do filtro "
          f"+ {n_t2h} do T2-H em {out_dir}")


if __name__ == "__main__":
    amostrar()

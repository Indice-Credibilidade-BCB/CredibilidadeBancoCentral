# -*- coding: utf-8 -*-
"""Fine-tuning do braço local (D7): destilação prata (API aprovada) + ouro
(consenso humano) -> BERTimbau + CoralHead, com validação por BLOCOS
TEMPORAIS (não CV aleatória — ver dataset.dividir_blocos_temporais).

Uso:
  python -m local_encoder.train \
      --corpus ../dados/llm/corpus.parquet \
      --rotulos-prata ../dados/llm/scores/producao.jsonl \
      --rotulos-ouro ../dados/llm/piloto/gabarito_consenso.csv \
      --out-checkpoint ../dados/llm/checkpoints/bertimbau_coral_v1

`--rotulos-ouro` é opcional (dá para treinar só com prata cedo no projeto);
quando presente, ouro tem PRIORIDADE sobre prata no mesmo item_id (rótulo de
maior qualidade) e o relatório final separa a métrica por origem.

Papel no projeto (D7): instrumento do T6 desde já; produção se a bateria
D6 reprovar a API ou houver instabilidade de provedor; robustez do Paper 1.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import schema  # noqa: E402
from reliability import kappa_quadratico  # noqa: E402

from .coral import coral_probs_to_label, coral_targets  # noqa: E402
from .dataset import dividir_blocos_temporais, montar_exemplos  # noqa: E402


def _carregar_rotulos_prata(jsonl_path: str) -> pd.DataFrame:
    recs = [json.loads(l) for l in
            pathlib.Path(jsonl_path).read_text(encoding="utf-8").splitlines()]
    df = pd.DataFrame(recs)
    df = df[df["d1"].notna()]
    if "cache_key" in df.columns:
        df = df.drop_duplicates(subset="cache_key", keep="last")
    return df[["item_id", "d1"]].drop_duplicates(subset="item_id", keep="last")


def montar_dataset(corpus_path: str, rotulos_prata_path: str,
                   rotulos_ouro_path: str | None) -> pd.DataFrame:
    itens = (pd.read_parquet(corpus_path) if corpus_path.endswith(".parquet")
            else pd.read_csv(corpus_path))
    itens = schema.dedup(schema.validate(itens))

    prata = _carregar_rotulos_prata(rotulos_prata_path)
    ex_prata = montar_exemplos(itens, prata, origem="prata")

    if rotulos_ouro_path:
        ouro = pd.read_csv(rotulos_ouro_path)[["item_id", "d1"]]
        ex_ouro = montar_exemplos(itens, ouro, origem="ouro")
        # ouro tem prioridade: remove do prata os item_id que também têm ouro
        ex_prata = ex_prata[~ex_prata["item_id"].isin(ex_ouro["item_id"])]
        todos = pd.concat([ex_prata, ex_ouro], ignore_index=True)
    else:
        todos = ex_prata

    return todos.sort_values("data_publicacao").reset_index(drop=True)


def treinar(todos: pd.DataFrame, modelo_base: str, n_blocos: int, bloco_teste: int,
           epocas: int, batch_size: int, lr: float, out_checkpoint: pathlib.Path):
    import torch
    from torch.optim import AdamW
    from transformers import AutoTokenizer

    from .model import BertimbauCoralClassifier

    blocos = dividir_blocos_temporais(todos, n_blocos=n_blocos)
    treino = todos[blocos != bloco_teste].reset_index(drop=True)
    val = todos[blocos == bloco_teste].reset_index(drop=True)
    print(f"treino: {len(treino)} | validação (bloco temporal {bloco_teste} "
          f"de {n_blocos}): {len(val)}")

    tokenizer = AutoTokenizer.from_pretrained(modelo_base)
    modelo = BertimbauCoralClassifier(modelo_base)
    opt = AdamW(modelo.parameters(), lr=lr)

    def _tokenizar(textos):
        return tokenizer(list(textos), padding=True, truncation=True,
                         max_length=256, return_tensors="pt")

    def _avaliar(df):
        if df.empty:
            return float("nan")
        modelo.eval()
        with torch.no_grad():
            enc = _tokenizar(df["texto"])
            logits = modelo(enc["input_ids"], enc["attention_mask"])
            pred = coral_probs_to_label(torch.sigmoid(logits).numpy())
        modelo.train()
        return kappa_quadratico(pred, df["d1"].to_numpy())

    modelo.train()
    for epoca in range(epocas):
        treino = treino.sample(frac=1).reset_index(drop=True)  # embaralha só o treino
        perda_epoca = []
        for i in range(0, len(treino), batch_size):
            lote = treino.iloc[i:i + batch_size]
            enc = _tokenizar(lote["texto"])
            alvo = torch.tensor(coral_targets(lote["d1"].to_numpy(), 5))
            opt.zero_grad()
            logits = modelo(enc["input_ids"], enc["attention_mask"])
            perda = modelo.coral_loss(logits, alvo)
            perda.backward()
            opt.step()
            perda_epoca.append(perda.item())
        kqw_val = _avaliar(val)
        # kappa_qw (não "κ_qw") no print: console Windows em cp1252 (comum em
        # pt-BR/en-US) não representa o grego e derruba o job no meio do
        # treino — os outros scripts do projeto evitam imprimir o símbolo
        # pelo mesmo motivo (só aparece em docstring/comentário).
        print(f"época {epoca + 1}/{epocas}: perda média={np.mean(perda_epoca):.4f} "
              f"| kappa_qw(validação, bloco futuro)={kqw_val:.3f}")

    out_checkpoint.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": modelo.state_dict(), "modelo_base": modelo_base,
               "num_classes": 5}, out_checkpoint / "bertimbau_coral.pt")
    tokenizer.save_pretrained(out_checkpoint)
    print(f"checkpoint salvo em {out_checkpoint}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--rotulos-prata", required=True)
    ap.add_argument("--rotulos-ouro", default=None)
    ap.add_argument("--out-checkpoint", required=True)
    ap.add_argument("--modelo-base", default="neuralmind/bert-base-portuguese-cased")
    ap.add_argument("--n-blocos", type=int, default=5)
    ap.add_argument("--bloco-teste", type=int, default=4,
                    help="bloco temporal (0-indexado) usado só p/ validação; "
                         "default = o MAIS RECENTE, para medir generalização "
                         "para o futuro, o caso de uso real do índice")
    ap.add_argument("--epocas", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-5)
    a = ap.parse_args()

    dados = montar_dataset(a.corpus, a.rotulos_prata, a.rotulos_ouro)
    print(f"{len(dados)} exemplo(s) de treino "
          f"({int((dados['origem'] == 'ouro').sum())} ouro, "
          f"{int((dados['origem'] == 'prata').sum())} prata)")
    treinar(dados, a.modelo_base, a.n_blocos, a.bloco_teste, a.epocas,
           a.batch_size, a.lr, pathlib.Path(a.out_checkpoint))

# -*- coding: utf-8 -*-
"""Pontua um corpus com o braço local treinado (D7). Saída no MESMO schema
JSONL de `scorer.py` (item_id, d1, provider, model, variante, ...) — plaga
direto em `aggregate.py` e em `diagnostics.leakage.comparar_t6`.

Uso:
  python -m local_encoder.infer \
      --checkpoint ../dados/llm/checkpoints/bertimbau_coral_v1 \
      --input ../dados/llm/corpus.parquet \
      --out ../dados/llm/scores/bertimbau_local.jsonl

O nível de anonimização da inferência deve ser o MESMO usado no treino
(default L1) — descasar os dois é uma forma silenciosa de distribution
shift, não um teste de robustez.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import schema  # noqa: E402

from .coral import coral_probs_to_label  # noqa: E402
from .dataset import montar_texto  # noqa: E402


def carregar_modelo(checkpoint_dir: pathlib.Path):
    import torch
    from transformers import AutoTokenizer

    from .model import BertimbauCoralClassifier

    # weights_only=True: nosso checkpoint só tem tensores + primitivos
    # (modelo_base, num_classes) — evita o vetor de execução de código
    # arbitrário do unpickling irrestrito (torch >= 2.4 recomenda por padrão).
    ckpt = torch.load(checkpoint_dir / "bertimbau_coral.pt", map_location="cpu",
                      weights_only=True)
    modelo = BertimbauCoralClassifier(ckpt["modelo_base"], ckpt["num_classes"])
    modelo.load_state_dict(ckpt["state_dict"])
    modelo.eval()
    tokenizer = AutoTokenizer.from_pretrained(checkpoint_dir)
    return modelo, tokenizer


def pontuar(checkpoint_dir: str, input_path: str, out_path: str,
           nivel_anonimizacao: str = "L1", batch_size: int = 16) -> None:
    import torch

    checkpoint_dir = pathlib.Path(checkpoint_dir)
    modelo, tokenizer = carregar_modelo(checkpoint_dir)

    itens = (pd.read_parquet(input_path) if input_path.endswith(".parquet")
            else pd.read_csv(input_path))
    itens = schema.dedup(schema.validate(itens))

    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    variante = f"local_encoder|{nivel_anonimizacao}"
    nome_modelo = f"bertimbau_coral@{checkpoint_dir.name}"

    with out.open("w", encoding="utf-8") as f, torch.no_grad():
        for i in range(0, len(itens), batch_size):
            lote = itens.iloc[i:i + batch_size]
            textos = lote.apply(lambda r: montar_texto(r, nivel_anonimizacao), axis=1)
            enc = tokenizer(list(textos), padding=True, truncation=True,
                            max_length=256, return_tensors="pt")
            logits = modelo(enc["input_ids"], enc["attention_mask"])
            pred = coral_probs_to_label(torch.sigmoid(logits).numpy())
            for item_id, d1 in zip(lote["item_id"], pred):
                rec = {
                    "item_id": item_id, "d1": int(d1), "d2": None, "d3": None,
                    "provider": "bertimbau_local", "model": nome_modelo,
                    "prompt_version": "n/a",  # braço local não usa prompt
                    "variante": variante, "variante_vazamento": None,
                    "ts": dt.datetime.now().isoformat(timespec="seconds"),
                    "erro": None,
                }
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Concluído: {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--nivel-anonimizacao", default="L1",
                    choices=["L1", "L2", "L3", "L4"])
    ap.add_argument("--batch-size", type=int, default=16)
    a = ap.parse_args()
    pontuar(a.checkpoint, a.input, a.out, a.nivel_anonimizacao, a.batch_size)

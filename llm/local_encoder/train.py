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

  # validação cruzada completa: treina uma vez por bloco temporal de teste
  python -m local_encoder.train ... --todos-blocos

`--rotulos-ouro` é opcional (dá para treinar só com prata cedo no projeto);
quando presente, ouro tem PRIORIDADE sobre prata no mesmo item_id (rótulo de
maior qualidade) e o relatório final separa a métrica por origem.

Desempenho (medido em 2026-10-14): na CPU (12 threads) o treino roda a ~4,5
itens/s e a inferência a ~15 itens/s; com a GPU (``--dispositivo auto`` e
PyTorch com CUDA) e float16 automático, ver ``metricas.json`` de cada
execução — o script registra itens/s por época.

Papel no projeto (D7): instrumento do T6 desde já; produção se a bateria
D6 reprovar a API ou houver instabilidade de provedor; robustez do Paper 1.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import schema  # noqa: E402
from reliability import kappa_quadratico  # noqa: E402

from . import dispositivo as disp  # noqa: E402
from .coral import coral_probs_to_label, coral_targets  # noqa: E402
from .dataset import amostrar_prata, dividir_blocos_temporais, montar_exemplos  # noqa: E402

# D7 previa 2–5 mil rótulos-prata; emenda de 2026-10-14: 20 mil e 4 épocas.
# Medido só com prata do Sabiá, validando no bloco temporal mais recente:
# 5 mil/3 épocas -> kappa_qw 0,32; 20 mil/3 -> 0,55; 20 mil/4 -> 0,59.
MAX_PRATA_PADRAO = 20000
EPOCAS_PADRAO = 4


def _carregar_rotulos_prata(jsonl_path: str) -> pd.DataFrame:
    recs = [json.loads(l) for l in
            pathlib.Path(jsonl_path).read_text(encoding="utf-8").splitlines()]
    df = pd.DataFrame(recs)
    df = df[df["d1"].notna()]
    if "cache_key" in df.columns:
        df = df.drop_duplicates(subset="cache_key", keep="last")
    return df[["item_id", "d1"]].drop_duplicates(subset="item_id", keep="last")


def montar_dataset(corpus_path: str, rotulos_prata_path: str,
                   rotulos_ouro_path: str | None, max_prata: int | None = MAX_PRATA_PADRAO,
                   semente: int = 42) -> pd.DataFrame:
    itens = (pd.read_parquet(corpus_path) if corpus_path.endswith(".parquet")
            else pd.read_csv(corpus_path))
    itens = schema.dedup(schema.validate(itens))

    prata = _carregar_rotulos_prata(rotulos_prata_path)
    ex_ouro = None
    if rotulos_ouro_path:
        ouro = pd.read_csv(rotulos_ouro_path)[["item_id", "d1"]]
        ex_ouro = montar_exemplos(itens, ouro, origem="ouro")
        # ouro tem prioridade: remove do prata os item_id que também têm ouro
        prata = prata[~prata["item_id"].isin(ex_ouro["item_id"])]

    # Amostra ANTES de montar os textos: a anonimização é a parte cara da
    # preparação, e só os itens amostrados precisam dela. O ouro entra inteiro.
    base = itens[["item_id", "data_publicacao"]].merge(prata, on="item_id", how="inner")
    base = base[pd.to_numeric(base["d1"], errors="coerce").notna()]
    escolhidos = amostrar_prata(base, max_prata, semente)["item_id"]
    ex_prata = montar_exemplos(itens, prata[prata["item_id"].isin(escolhidos)], origem="prata")
    todos = pd.concat([ex_prata, ex_ouro], ignore_index=True) if ex_ouro is not None else ex_prata

    return todos.sort_values("data_publicacao").reset_index(drop=True)


def treinar(todos: pd.DataFrame, modelo_base: str, n_blocos: int, bloco_teste: int,
           epocas: int, batch_size: int, lr: float, out_checkpoint: pathlib.Path,
           dispositivo: str = "auto", fp16: bool = True, batch_avaliacao: int = 64,
           semente: int = 42, lr_cabeca: float = 1e-3) -> dict:
    """Treina um modelo com ``bloco_teste`` fora do treino. Devolve as métricas
    (também gravadas em ``out_checkpoint/metricas.json``)."""
    import torch
    from torch.optim import AdamW
    from transformers import AutoTokenizer

    from .model import BertimbauCoralClassifier

    torch.manual_seed(semente)
    dev = disp.escolher(dispositivo)
    usar_fp16 = fp16 and dev.type == "cuda"
    print(f"dispositivo: {disp.descrever(dev)}{' | float16 automático' if usar_fp16 else ''}")

    blocos = dividir_blocos_temporais(todos, n_blocos=n_blocos)
    treino = todos[blocos != bloco_teste].reset_index(drop=True)
    val = todos[blocos == bloco_teste].reset_index(drop=True)
    print(f"treino: {len(treino)} | validação (bloco temporal {bloco_teste} "
          f"de {n_blocos}): {len(val)}")

    tokenizer = AutoTokenizer.from_pretrained(modelo_base)
    modelo = BertimbauCoralClassifier(modelo_base)
    modelo.head.inicializar_vies(treino["d1"].to_numpy())  # limiares partem das frequências do treino
    modelo = modelo.to(dev)
    # Taxas separadas: o encoder pré-treinado ajusta devagar (lr); a cabeça
    # CORAL, criada do zero, precisa de uma taxa bem maior (lr_cabeca).
    opt = AdamW([{"params": modelo.encoder.parameters(), "lr": lr},
                 {"params": modelo.head.parameters(), "lr": lr_cabeca}])
    moda = int(treino["d1"].mode().iloc[0])
    scaler = torch.amp.GradScaler("cuda", enabled=usar_fp16)

    def _tokenizar(textos):
        enc = tokenizer(list(textos), padding=True, truncation=True,
                        max_length=256, return_tensors="pt")
        return {k: v.to(dev, non_blocking=True) for k, v in enc.items()}

    def _prever(df) -> np.ndarray:
        """Predição em LOTES (o bloco de validação pode ter milhares de itens:
        passar tudo de uma vez estoura a memória da GPU)."""
        modelo.eval()
        preds = []
        with torch.no_grad(), disp.autocast(dev, usar_fp16):
            for i in range(0, len(df), batch_avaliacao):
                enc = _tokenizar(df["texto"].iloc[i:i + batch_avaliacao])
                logits = modelo(enc["input_ids"], enc["attention_mask"])
                preds.append(coral_probs_to_label(torch.sigmoid(logits.float()).cpu().numpy()))
        modelo.train()
        return np.concatenate(preds) if preds else np.array([], dtype=int)

    def _avaliar(df) -> dict:
        if df.empty:
            return {"kappa_qw": float("nan")}
        pred = _prever(df)
        y = df["d1"].to_numpy()
        out = {"kappa_qw": float(kappa_quadratico(pred, y)),
               "acuracia": float((pred == y).mean()),
               # linha de base: prever sempre a classe mais comum do treino
               "acuracia_base_moda": float((y == moda).mean()),
               "dist_predita": {int(c): int((pred == c).sum()) for c in np.unique(pred)}}
        for origem in ("ouro", "prata"):
            m = (df["origem"] == origem).to_numpy()
            if m.sum() >= 10:
                out[f"kappa_qw_{origem}"] = float(kappa_quadratico(pred[m], df["d1"].to_numpy()[m]))
        return out

    historico = []
    modelo.train()
    rng = np.random.default_rng(semente)
    for epoca in range(epocas):
        t0 = time.time()
        treino = treino.iloc[rng.permutation(len(treino))].reset_index(drop=True)  # embaralha só o treino
        perda_epoca = []
        for i in range(0, len(treino), batch_size):
            lote = treino.iloc[i:i + batch_size]
            enc = _tokenizar(lote["texto"])
            alvo = torch.tensor(coral_targets(lote["d1"].to_numpy(), 5), device=dev)
            opt.zero_grad(set_to_none=True)
            with disp.autocast(dev, usar_fp16):
                logits = modelo(enc["input_ids"], enc["attention_mask"])
            perda = modelo.coral_loss(logits.float(), alvo.float())
            scaler.scale(perda).backward()
            scaler.step(opt)
            scaler.update()
            perda_epoca.append(perda.item())
        seg_treino = time.time() - t0
        t1 = time.time()
        aval = _avaliar(val)
        seg_val = time.time() - t1
        reg = {"epoca": epoca + 1, "perda_media": float(np.mean(perda_epoca)),
               "itens_por_s_treino": len(treino) / seg_treino,
               "itens_por_s_validacao": (len(val) / seg_val) if seg_val > 0 else None,
               "segundos": seg_treino + seg_val, **aval}
        historico.append(reg)
        # kappa_qw (não "κ_qw") no print: console Windows em cp1252 não
        # representa o grego e derruba o job no meio do treino.
        print(f"época {epoca + 1}/{epocas}: perda média={reg['perda_media']:.4f} "
              f"| kappa_qw(validação, bloco temporal)={aval['kappa_qw']:.3f} "
              f"| acurácia={aval.get('acuracia', float('nan')):.3f} (moda: {aval.get('acuracia_base_moda', float('nan')):.3f}) "
              f"| {reg['itens_por_s_treino']:.1f} itens/s | {reg['segundos'] / 60:.1f} min", flush=True)

    out_checkpoint.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": {k: v.detach().cpu() for k, v in modelo.state_dict().items()},
                "modelo_base": modelo_base, "num_classes": 5}, out_checkpoint / "bertimbau_coral.pt")
    tokenizer.save_pretrained(out_checkpoint)
    metricas = {"bloco_teste": bloco_teste, "n_blocos": n_blocos, "n_treino": len(treino),
                "n_validacao": len(val), "dispositivo": disp.descrever(dev), "fp16": usar_fp16,
                "epocas": historico, "final": historico[-1] if historico else None}
    (out_checkpoint / "metricas.json").write_text(json.dumps(metricas, indent=2, ensure_ascii=False),
                                                  encoding="utf-8")
    print(f"checkpoint salvo em {out_checkpoint}")
    return metricas


def treinar_todos_blocos(todos: pd.DataFrame, out_base: pathlib.Path, n_blocos: int, **kw) -> pd.DataFrame:
    """Validação cruzada temporal completa: um modelo por bloco de teste.

    Cada fold grava em ``out_base/bloco_<k>``. O resumo (kappa por bloco)
    vai para ``out_base/cv_temporal.csv``. O checkpoint de produção continua
    sendo o do bloco mais recente (``--bloco-teste`` padrão), que mede a
    generalização para o futuro.
    """
    linhas = []
    for b in range(n_blocos):
        print(f"\n=== bloco de teste {b} de {n_blocos} ===")
        m = treinar(todos, n_blocos=n_blocos, bloco_teste=b, out_checkpoint=out_base / f"bloco_{b}", **kw)
        f = m["final"] or {}
        linhas.append({"bloco_teste": b, "n_treino": m["n_treino"], "n_validacao": m["n_validacao"],
                       **{k: v for k, v in f.items() if k.startswith(("kappa", "acuracia"))}})
    res = pd.DataFrame(linhas)
    out_base.mkdir(parents=True, exist_ok=True)
    res.to_csv(out_base / "cv_temporal.csv", index=False)
    print(res.round(3).to_string(index=False))
    return res


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
    ap.add_argument("--todos-blocos", action="store_true",
                    help="validação cruzada temporal completa (um treino por bloco; ~n_blocos× o tempo)")
    ap.add_argument("--max-prata", type=int, default=MAX_PRATA_PADRAO,
                    help="nº máximo de rótulos-prata, amostrados por ano (D7 emendada: 20 mil); 0 = todos")
    ap.add_argument("--semente", type=int, default=42)
    ap.add_argument("--epocas", type=int, default=EPOCAS_PADRAO)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--batch-avaliacao", type=int, default=64)
    ap.add_argument("--lr", type=float, default=2e-5, help="taxa do encoder BERTimbau")
    ap.add_argument("--lr-cabeca", type=float, default=1e-3, help="taxa da cabeça CORAL (criada do zero)")
    ap.add_argument("--dispositivo", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--sem-fp16", action="store_true", help="desliga float16 automático na GPU")
    a = ap.parse_args()

    dados = montar_dataset(a.corpus, a.rotulos_prata, a.rotulos_ouro,
                           max_prata=a.max_prata or None, semente=a.semente)
    print(f"{len(dados)} exemplo(s) de treino "
          f"({int((dados['origem'] == 'ouro').sum())} ouro, "
          f"{int((dados['origem'] == 'prata').sum())} prata)")
    kw = dict(modelo_base=a.modelo_base, epocas=a.epocas, batch_size=a.batch_size, lr=a.lr,
              lr_cabeca=a.lr_cabeca,
              dispositivo=a.dispositivo, fp16=not a.sem_fp16, batch_avaliacao=a.batch_avaliacao,
              semente=a.semente)
    if a.todos_blocos:
        treinar_todos_blocos(dados, pathlib.Path(a.out_checkpoint), a.n_blocos, **kw)
    else:
        treinar(dados, n_blocos=a.n_blocos, bloco_teste=a.bloco_teste,
                out_checkpoint=pathlib.Path(a.out_checkpoint), **kw)

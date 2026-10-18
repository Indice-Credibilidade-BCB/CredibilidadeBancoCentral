# -*- coding: utf-8 -*-
"""Pré-filtro de sinal (economia de tokens): o BERTimbau decide, de graça na GPU,
quais notícias quase certamente NÃO falam do cumprimento da meta, e só as
demais vão para a API.

Rótulos: a marcação ``d1_sem_sinal`` do prompt v1.1 (API) numa amostra
aleatória de produção. Modelo: o mesmo ``BertimbauCoralClassifier`` do braço
local com 2 classes (1 = sem sinal, 2 = com sinal) — CORAL com duas classes é
uma regressão logística binária sobre o [CLS]. Entrada em anonimização L1
(sem datas), como no braço local (D7).

O limiar é escolhido na validação para manter a SENSIBILIDADE para notícias
com sinal ≥ ``sens_min`` (padrão 95%): o filtro pode deixar passar notícias
sem sinal (custo: chamadas a mais), mas deve perder pouco sinal (custo:
viés). A perda real é medida em produção pela auditoria aleatória das
notícias descartadas (``producao_v11.py``).
"""
from __future__ import annotations

import json
import pathlib
import time

import numpy as np
import pandas as pd

from . import dispositivo as disp
from .dataset import montar_texto


def textos(df: pd.DataFrame, nivel: str = "L1") -> list[str]:
    return [montar_texto(r, nivel) for r in df.to_dict("records")]


def treinar(df_rot: pd.DataFrame, out_dir: pathlib.Path, epocas: int = 3, batch_size: int = 16,
            lr: float = 2e-5, lr_cabeca: float = 1e-3, sens_min: float = 0.95, frac_val: float = 0.2,
            semente: int = 42, dispositivo: str = "auto") -> dict:
    """``df_rot``: colunas do corpus + ``tem_sinal`` (bool). Grava checkpoint e
    ``metricas_filtro.json`` (AUC, limiar, sensibilidade, fração descartada)."""
    import torch
    from torch.optim import AdamW
    from transformers import AutoTokenizer

    from .model import MODELO_PADRAO, BertimbauCoralClassifier

    torch.manual_seed(semente)
    dev = disp.escolher(dispositivo)
    fp16 = dev.type == "cuda"
    rng = np.random.default_rng(semente)
    df = df_rot.reset_index(drop=True)
    y = df["tem_sinal"].astype(int).to_numpy() + 1          # 1 = sem sinal, 2 = com sinal
    idx = rng.permutation(len(df))
    n_val = int(len(df) * frac_val)
    iv, it = idx[:n_val], idx[n_val:]
    X = textos(df)

    tok = AutoTokenizer.from_pretrained(MODELO_PADRAO)
    modelo = BertimbauCoralClassifier(MODELO_PADRAO, num_classes=2)
    modelo.head.inicializar_vies(y[it])
    modelo = modelo.to(dev)
    opt = AdamW([{"params": modelo.encoder.parameters(), "lr": lr},
                 {"params": modelo.head.parameters(), "lr": lr_cabeca}])
    scaler = torch.amp.GradScaler("cuda", enabled=fp16)

    def enc(lista):
        e = tok(lista, padding=True, truncation=True, max_length=256, return_tensors="pt")
        return {k: v.to(dev) for k, v in e.items()}

    t0 = time.time()
    modelo.train()
    for _ in range(epocas):
        ordem = rng.permutation(it)
        for i in range(0, len(ordem), batch_size):
            b = ordem[i:i + batch_size]
            e = enc([X[j] for j in b])
            alvo = torch.tensor((y[b] > 1).astype(np.float32)[:, None], device=dev)
            opt.zero_grad(set_to_none=True)
            with disp.autocast(dev, fp16):
                logits = modelo(e["input_ids"], e["attention_mask"])
            perda = modelo.coral_loss(logits.float(), alvo)
            scaler.scale(perda).backward(); scaler.step(opt); scaler.update()

    p_val = _prob(modelo, tok, [X[j] for j in iv], dev, fp16)
    y_val = (y[iv] > 1)
    limiar = escolher_limiar(p_val, y_val, sens_min)
    descarta = p_val < limiar
    from sklearn.metrics import roc_auc_score
    met = {"n_treino": int(len(it)), "n_validacao": int(len(iv)), "taxa_sinal_rotulos": float((y > 1).mean()),
           "auc_validacao": float(roc_auc_score(y_val, p_val)) if y_val.any() and (~y_val).any() else None,
           "limiar": float(limiar), "sens_min_alvo": sens_min,
           "sensibilidade_validacao": float((~descarta[y_val]).mean()) if y_val.any() else None,
           "fracao_descartada_validacao": float(descarta.mean()),
           "sinal_perdido_validacao": int((descarta & y_val).sum()),
           "minutos_treino": (time.time() - t0) / 60, "dispositivo": disp.descrever(dev)}
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": {k: v.detach().cpu() for k, v in modelo.state_dict().items()},
                "modelo_base": MODELO_PADRAO, "num_classes": 2, "limiar": float(limiar)},
               out_dir / "filtro_sinal.pt")
    (out_dir / "metricas_filtro.json").write_text(json.dumps(met, indent=2, ensure_ascii=False), encoding="utf-8")
    return met


def escolher_limiar(p: np.ndarray, y: np.ndarray, sens_min: float) -> float:
    """Maior limiar que mantém sensibilidade ≥ sens_min para y=True."""
    pos = np.sort(p[y])
    if len(pos) == 0:
        return 0.0
    k = int(np.floor((1 - sens_min) * len(pos)))   # quantos positivos podem ficar abaixo
    return float(pos[k]) if k < len(pos) else float(pos[-1])


def _prob(modelo, tok, lista: list[str], dev, fp16: bool, lote: int = 64) -> np.ndarray:
    import torch
    modelo.eval()
    out = []
    with torch.no_grad(), disp.autocast(dev, fp16):
        for i in range(0, len(lista), lote):
            e = tok(lista[i:i + lote], padding=True, truncation=True, max_length=256, return_tensors="pt").to(dev)
            out.append(torch.sigmoid(modelo(e["input_ids"], e["attention_mask"]).float()).cpu().numpy()[:, 0])
    modelo.train()
    return np.concatenate(out) if out else np.array([])


def prever(df: pd.DataFrame, ckpt_dir: pathlib.Path, dispositivo: str = "auto") -> tuple[np.ndarray, float]:
    """P(com sinal) para cada linha de ``df`` e o limiar salvo no checkpoint."""
    import torch
    from transformers import AutoTokenizer

    from .model import BertimbauCoralClassifier
    dev = disp.escolher(dispositivo)
    ck = torch.load(ckpt_dir / "filtro_sinal.pt", map_location="cpu", weights_only=True)
    modelo = BertimbauCoralClassifier(ck["modelo_base"], ck["num_classes"])
    modelo.load_state_dict(ck["state_dict"])
    modelo = modelo.to(dev)
    tok = AutoTokenizer.from_pretrained(ck["modelo_base"])
    return _prob(modelo, tok, textos(df), dev, dev.type == "cuda"), float(ck["limiar"])

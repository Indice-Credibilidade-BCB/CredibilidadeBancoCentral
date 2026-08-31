# -*- coding: utf-8 -*-
"""Bateria anti-vazamento (look-ahead) — testes T2 a T5.

T2 (date-swap): re-pontuar subamostra com data OMITIDA e com data TROCADA
    (±5 anos, refletido para dentro do regime de metas). Vazamento se |Δ|
    for grande E o Δ correlacionar com o desfecho futuro realizado.
T3 (anonimização): mascarar datas do corpo (L1), autoridades do BC (L2) e
    políticos (L3). Se o escore muda sistematicamente por era ao esconder
    QUEM é a autoridade, o modelo usa prior sobre pessoas/eras, não o texto.
T4 (resíduo preditivo): resíduo do escore LLM (controlando o escore humano)
    não deve prever a surpresa inflacionária FUTURA. Regressão com Newey-West
    na etapa econométrica; aqui, correlação de triagem.
T5 (itens sintéticos): textos fabricados idênticos, "datados" em eras boas e
    ruins. Como cada grupo (texto_grupo) tem o MESMO texto nas duas eras, o
    teste primário é PAREADO por grupo (mais poder que Welch); Welch fica
    como robustez.

Critérios de reprovação (pré-registrados no doc de decisões):
    T2/T3: corr(Δ, desfecho futuro) significativa a 5% com |ρ| >= 0,25;
    T5: diferença média entre eras significativa a 5% (teste pareado).
Reprovou => produção migra para o braço local (encoder de cutoff conhecido).

Notas da auditoria (2026-08-18):
  - Datas trocadas são refletidas para [1999-07-01, hoje−30d]: evita datar
    item no FUTURO ou antes do regime de metas (ambos dariam ao modelo um
    sinal espúrio de "data estranha").
  - Máscara de nomes usa fronteira de palavra e é case-sensitive (aceitando
    ALL-CAPS de títulos): evita transformar o verbo "temer" em [POLITICO]
    ou "fragata" em [AUTORIDADE_BC]ta. Limitação residual documentada:
    sobrenome idêntico a palavra capitalizada no início de frase.
"""
from __future__ import annotations

import pathlib
import re

import numpy as np
import pandas as pd
import yaml

ROOT = pathlib.Path(__file__).parent.parent

REGIME_INICIO = pd.Timestamp("1999-07-01")  # decreto do regime de metas


def _cfg() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# T2 — variantes de data
# ---------------------------------------------------------------------------

def gerar_variantes_data(itens: pd.DataFrame, anos_offset: int = 5) -> pd.DataFrame:
    """Cria coluna data_falsa deslocando ±anos_offset (alternando o sinal).

    A data falsa é mantida DENTRO do regime de metas e do passado:
    se o deslocamento estourar [1999-07-01, hoje−30d], usa o sinal oposto.
    """
    df = itens.copy()
    d = pd.to_datetime(df["data_publicacao"])
    teto = pd.Timestamp.today().normalize() - pd.Timedelta(days=30)
    off = pd.DateOffset(years=anos_offset)

    sinais = np.where(np.arange(len(df)) % 2 == 0, 1, -1)
    falsas = []
    for data, s in zip(d, sinais):
        cand = data + off if s > 0 else data - off
        if not (REGIME_INICIO <= cand <= teto):
            cand = data - off if s > 0 else data + off
        if not (REGIME_INICIO <= cand <= teto):  # janela curta demais p/ ±5a
            cand = min(max(cand, REGIME_INICIO), teto)
        falsas.append(cand)
    df["data_falsa"] = pd.to_datetime(falsas).strftime("%Y-%m-%d")
    return df


# ---------------------------------------------------------------------------
# T3 — anonimização em níveis
# L1 = sem datas no corpo; L2 = L1 + autoridades do BC; L3 = L2 + políticos
# ---------------------------------------------------------------------------

_RE_DATAS = re.compile(
    r"\b(19|20)\d{2}\b|\b\d{1,2} de (janeiro|fevereiro|março|abril|maio|junho|"
    r"julho|agosto|setembro|outubro|novembro|dezembro)\b", re.IGNORECASE)


def _padrao_nome(nome: str) -> re.Pattern:
    """Fronteira de palavra; casa o nome como escrito OU em ALL-CAPS.

    Case-sensitive de propósito: 'Temer' (sobrenome) casa; 'temer' (verbo) não.
    """
    esc = re.escape(nome)
    return re.compile(rf"\b({esc}|{esc.upper()})\b")


def anonimizar(texto: str, nivel: str) -> str:
    cfg = _cfg()["anonimizacao"]
    t = texto or ""
    if nivel in ("L1", "L2", "L3"):
        t = _RE_DATAS.sub("[DATA]", t)
    if nivel in ("L2", "L3"):
        for nome in sorted(cfg["autoridades_bc"], key=len, reverse=True):
            t = _padrao_nome(nome).sub("[AUTORIDADE_BC]", t)
    if nivel == "L3":
        for nome in sorted(cfg["politicos"], key=len, reverse=True):
            t = _padrao_nome(nome).sub("[POLITICO]", t)
    return t


def aplicar_anonimizacao(itens: pd.DataFrame, nivel: str) -> pd.DataFrame:
    df = itens.copy()
    for col in ("titulo", "lead", "paragrafo_1"):
        if col in df.columns:
            df[col] = df[col].map(lambda s: anonimizar(s, nivel))
    return df


# ---------------------------------------------------------------------------
# Comparação de variantes (T2/T3) e triagem do T4
# ---------------------------------------------------------------------------

def comparar_variantes(base: pd.DataFrame, alt: pd.DataFrame,
                       desfecho_futuro: pd.Series | None = None) -> dict:
    """base/alt: colunas item_id, d1 (mesmos itens, variantes distintas).
    desfecho_futuro: opcional, indexada por item_id (ex.: surpresa de inflação
    12m à frente da data de publicação)."""
    m = base.merge(alt, on="item_id", suffixes=("_base", "_alt"))
    delta = (m["d1_alt"] - m["d1_base"]).astype(float)
    out = {
        "n": int(len(m)),
        "delta_medio": float(delta.mean()),
        "delta_abs_medio": float(delta.abs().mean()),
        "pct_mudou": float((delta != 0).mean()),
    }
    if desfecho_futuro is not None:
        y = m["item_id"].map(desfecho_futuro)
        ok = y.notna() & delta.notna()
        n = int(ok.sum())
        if n >= 10:
            if delta[ok].std(ddof=1) == 0 or y[ok].std(ddof=1) == 0:
                out.update({"corr_delta_desfecho": 0.0, "t_aprox": 0.0,
                            "obs": "sem variação em delta ou desfecho"})
            else:
                rho = float(np.corrcoef(delta[ok], y[ok])[0, 1])
                t = rho * np.sqrt((n - 2) / max(1e-12, 1 - rho ** 2))
                out.update({"corr_delta_desfecho": rho, "t_aprox": float(t)})
    return out


# ---------------------------------------------------------------------------
# T5 — sintéticos: pareado (primário) + Welch (robustez)
# ---------------------------------------------------------------------------

def _p_bicaudal_t(t: float, gl: float) -> float:
    """p-valor bicaudal da t de Student; usa scipy se houver, senão normal."""
    try:
        from scipy import stats
        return float(2 * stats.t.sf(abs(t), gl))
    except ImportError:  # aproximação normal (conservadora só p/ gl grande)
        from math import erf, sqrt
        return float(2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2)))))


def teste_sinteticos(scores: pd.DataFrame) -> dict:
    """scores: colunas item_id, texto_grupo, era ('boa'/'ruim'), d1.

    Primário: t PAREADO nas diferenças d1(ruim) − d1(boa) por texto_grupo —
    o desenho do T5 é pareado por construção (texto idêntico, era trocada).
    Robustez: Welch entre eras (ignora o pareamento).
    """
    s = scores.copy()
    s["d1"] = pd.to_numeric(s["d1"], errors="coerce")
    piv = s.pivot_table(index="texto_grupo", columns="era", values="d1",
                        aggfunc="mean")
    piv = piv.dropna(subset=["boa", "ruim"])
    dif = (piv["ruim"] - piv["boa"]).astype(float)
    npar = int(len(dif))
    out = {"n_pares": npar,
           "media_era_boa": float(piv["boa"].mean()),
           "media_era_ruim": float(piv["ruim"].mean()),
           "dif_media_pareada": float(dif.mean())}
    if npar >= 2 and dif.std(ddof=1) > 0:
        t_par = dif.mean() / (dif.std(ddof=1) / np.sqrt(npar))
        out["t_pareado"] = float(t_par)
        out["p_pareado"] = _p_bicaudal_t(t_par, npar - 1)
    elif npar >= 2:
        out.update({"t_pareado": 0.0, "p_pareado": 1.0,
                    "obs": "diferenças idênticas em todos os pares"})
    # Welch (robustez)
    g = {era: s.loc[s["era"] == era, "d1"].dropna() for era in ("boa", "ruim")}
    n1, n2 = len(g["boa"]), len(g["ruim"])
    if min(n1, n2) >= 2:
        m1, m2 = g["boa"].mean(), g["ruim"].mean()
        v1, v2 = g["boa"].var(ddof=1), g["ruim"].var(ddof=1)
        se2 = v1 / n1 + v2 / n2
        if se2 > 0:
            t_w = (m2 - m1) / np.sqrt(se2)
            gl = se2 ** 2 / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1))
            out.update({"t_welch": float(t_w), "gl_welch": float(gl),
                        "p_welch": _p_bicaudal_t(t_w, gl)})
    return out

# -*- coding: utf-8 -*-
r"""Curvas nominal e real e inflação implícita históricas, a partir do Tesouro Direto (2004–hoje).

Por que Tesouro Direto
----------------------
A ETTJ da ANBIMA só é pública para o último mês (``mercado.anbima``) e a
página de taxas referenciais da B3 não responde para datas antigas
(Cloudflare 524, verificado em 2026-10-14). O Tesouro Transparente publica o
histórico diário completo de taxas de compra e venda de todos os títulos do
Tesouro Direto desde 31/12/2004 — LTN, NTN-F, NTN-B Principal e NTN-B.

Construção
----------
1. Taxa média = (compra + venda)/2 de cada título-dia. Títulos com menos de
   6 meses para o vencimento saem: o Tesouro Direto para de vendê-los e a
   taxa publicada vira ~0 (artefato, não mercado).
2. Prazo em anos úteis = DU/252 (calendário ANBIMA). Títulos zero-cupom
   (Prefixado = LTN; IPCA+ = NTN-B Principal) entram no próprio prazo.
   Títulos com cupom semestral (NTN-F 10% a.a.; NTN-B 6% a.a.) entram na
   **duration de Macaulay** calculada à própria taxa — aproximação padrão
   da taxa zero pela taxa ao vencimento na duration.
3. Interpolação linear da taxa no prazo, nos horizontes fixos (1, 2, 3, 5 e
   10 anos), **sem extrapolação**: fora do intervalo coberto pelos títulos
   do dia, NaN.
4. Inflação implícita de Fisher: :math:`(1+i^{nom})/(1+i^{real}) - 1`.

Leitura (``mercado/README.md``): a implícita é expectativa + prêmio de
risco de inflação + prêmio de liquidez, não expectativa pura; e o Tesouro
Direto é varejo — as taxas embutem o spread de compra/venda do Tesouro,
que em boa parte se cancela na diferença nominal − real. A validação contra
a ETTJ oficial da ANBIMA na janela de sobreposição está em
``validar_contra_anbima``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import requests

from mercado.bcb import DIR_MACRO, RAIZ

from .calendario import du_vetor

DIR_MERCADO = RAIZ / "dados" / "mercado"
URL_TD = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
          "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv")
HORIZONTES = (1, 2, 3, 5, 10)

# tipo no arquivo -> (curva, cupom anual ou None para zero-cupom, mês-dia dos cupons)
TITULOS = {
    "Tesouro Prefixado": ("nominal", None),
    "Tesouro Prefixado com Juros Semestrais": ("nominal", 0.10),
    "Tesouro IPCA+": ("real", None),
    "Tesouro IPCA+ com Juros Semestrais": ("real", 0.06),
}


def baixar_tesouro_direto(atualizar: bool = False) -> pd.DataFrame:
    """Histórico de taxas do Tesouro Direto (cache em ``dados/macro/tesouro_direto_taxas.csv``)."""
    cache = DIR_MACRO / "tesouro_direto_taxas.csv"
    if atualizar or not cache.exists():
        r = requests.get(URL_TD, timeout=600, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        DIR_MACRO.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(r.content)
    df = pd.read_csv(cache, sep=";", decimal=",")
    df["data"] = pd.to_datetime(df["Data Base"], dayfirst=True)
    df["vencimento"] = pd.to_datetime(df["Data Vencimento"], dayfirst=True)
    return df.rename(columns={"Tipo Titulo": "tipo", "Taxa Compra Manha": "taxa_compra", "Taxa Venda Manha": "taxa_venda"})


def _datas_cupom(venc: pd.Timestamp, ref: pd.Timestamp) -> list[pd.Timestamp]:
    """Datas de cupom semestral de ``ref`` (exclusive) até ``venc`` (inclusive), contadas do vencimento para trás."""
    out = [venc]
    k = 1
    while True:
        d = venc - pd.DateOffset(months=6 * k)
        if d <= ref:
            break
        out.append(d)
        k += 1
    return sorted(out)


def duration_macaulay(ref: pd.Timestamp, venc: pd.Timestamp, taxa_pct: float, cupom_anual: float) -> float:
    """Duration de Macaulay (anos úteis, base 252) de um título com cupom semestral, à própria taxa."""
    datas = _datas_cupom(venc, ref)
    t = du_vetor(pd.Series([ref] * len(datas)), pd.Series(datas)) / 252.0
    c = (1 + cupom_anual) ** 0.5 - 1
    fluxos = np.full(len(datas), c); fluxos[-1] += 1.0
    vp = fluxos / (1 + taxa_pct / 100.0) ** t
    return float((t * vp).sum() / vp.sum())


def pontos_da_curva(td: pd.DataFrame, prazo_min_anos: float = 0.5) -> pd.DataFrame:
    """Um ponto (data, curva, prazo, taxa) por título-dia, já filtrado e com duration nos de cupom."""
    df = td[td["tipo"].isin(TITULOS)].copy()
    tc, tv = df["taxa_compra"].where(df["taxa_compra"] > 0), df["taxa_venda"].where(df["taxa_venda"] > 0)
    df["taxa"] = pd.concat([tc, tv], axis=1).mean(axis=1)
    df = df.dropna(subset=["taxa"])
    df["anos_venc"] = du_vetor(df["data"], df["vencimento"]) / 252.0
    df = df[df["anos_venc"] >= prazo_min_anos]
    df["curva"] = df["tipo"].map(lambda t: TITULOS[t][0])
    df["cupom"] = df["tipo"].map(lambda t: TITULOS[t][1])
    df["prazo"] = df["anos_venc"]
    com_cupom = df["cupom"].notna()
    df.loc[com_cupom, "prazo"] = [duration_macaulay(r, v, x, c) for r, v, x, c in
                                  df.loc[com_cupom, ["data", "vencimento", "taxa", "cupom"]].itertuples(index=False)]
    return df[["data", "curva", "tipo", "vencimento", "anos_venc", "prazo", "taxa"]].reset_index(drop=True)


def _interp(prazos: np.ndarray, taxas: np.ndarray, alvo: float) -> float:
    if len(prazos) == 0 or alvo < prazos.min() or alvo > prazos.max():
        return np.nan
    o = np.argsort(prazos)
    return float(np.interp(alvo, prazos[o], taxas[o]))


def curvas_diarias(pontos: pd.DataFrame, horizontes=HORIZONTES) -> pd.DataFrame:
    """Nominal, real e implícita (% a.a.) por dia nos horizontes fixos + nº de pontos de cada curva."""
    linhas = []
    for d, g in pontos.groupby("data"):
        linha = {"data": d}
        for curva in ("nominal", "real"):
            gc = g[g["curva"] == curva].groupby("prazo", as_index=False)["taxa"].mean()
            linha[f"n_pontos_{curva}"] = len(gc)
            linha[f"prazo_max_{curva}"] = gc["prazo"].max() if len(gc) else np.nan
            for h in horizontes:
                linha[f"{curva}_{h}a"] = _interp(gc["prazo"].to_numpy(), gc["taxa"].to_numpy(), h)
        for h in horizontes:
            n, r = linha[f"nominal_{h}a"], linha[f"real_{h}a"]
            linha[f"implicita_{h}a"] = 100 * ((1 + n / 100) / (1 + r / 100) - 1) if np.isfinite(n) and np.isfinite(r) else np.nan
        linhas.append(linha)
    return pd.DataFrame(linhas)


def mensal(diario: pd.DataFrame) -> pd.DataFrame:
    m = diario.set_index("data").resample("MS").mean(numeric_only=True)
    m.index = m.index.to_period("M")
    m.index.name = "mes"
    return m


def validar_contra_anbima(diario: pd.DataFrame, horizontes=(1, 2, 3, 5)) -> pd.DataFrame | None:
    """Diferença média e máxima (p.p.) entre a curva do Tesouro Direto e a ETTJ ANBIMA na sobreposição."""
    from .anbima import DIR_ANBIMA, curva_em_prazos
    p = DIR_ANBIMA / "ettj_parametros.csv"
    if not p.exists():
        return None
    anb = curva_em_prazos(pd.read_csv(p, parse_dates=["data"]), anos=horizontes)
    j = diario.merge(anb, on="data", suffixes=("_td", "_anbima"))
    if j.empty:
        return None
    linhas = []
    for h in horizontes:
        for c in ("nominal", "real", "implicita"):
            dif = j[f"{c}_{h}a_td"] - j[f"{c}_{h}a_anbima"]
            linhas.append({"horizonte_anos": h, "curva": c, "n_dias": int(dif.notna().sum()),
                           "dif_media_pp": dif.mean(), "dif_abs_max_pp": dif.abs().max(),
                           "corr_diaria": j[f"{c}_{h}a_td"].corr(j[f"{c}_{h}a_anbima"])})
    return pd.DataFrame(linhas)


def construir(atualizar: bool = False, horizonte_rival: int = 5) -> dict:
    """Baixa, monta e salva tudo. ``horizonte_rival`` define a série ``rival`` devolvida.

    Não grava ``breakeven.csv``: o rival oficial é a implícita de títulos da
    B3, com o Tesouro Direto só nos buracos (``lista2.salvar_breakeven``).

    Padrão 5 anos: é o horizonte de ancoragem de médio prazo (menos ciclo, mais
    credibilidade) e o de melhor cobertura no Tesouro Direto — 100% dos dias
    desde 2010; o de 2 anos tem buracos em 2020–2022 (sem NTN-B curta).
    """
    td = baixar_tesouro_direto(atualizar=atualizar)
    pts = pontos_da_curva(td)
    dia = curvas_diarias(pts)
    m = mensal(dia)
    DIR_MERCADO.mkdir(parents=True, exist_ok=True)
    dia.to_csv(DIR_MERCADO / "curvas_tesouro_direto_diario.csv", index=False, date_format="%Y-%m-%d")
    m.to_csv(DIR_MERCADO / "inflacao_implicita_mensal.csv")
    col = f"implicita_{horizonte_rival}a"
    rival = dia[["data", col]].dropna().rename(columns={col: "valor"})
    val = validar_contra_anbima(dia)
    if val is not None:
        val.to_csv(DIR_MERCADO / "validacao_td_vs_anbima.csv", index=False)
    cobertura = {f"{c}_{h}a": float(dia[f"{c}_{h}a"].notna().mean()) for c in ("nominal", "real", "implicita") for h in HORIZONTES}
    return {"diario": dia, "mensal": m, "validacao": val, "cobertura": cobertura, "pontos": pts, "rival": rival}

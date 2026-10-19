# -*- coding: utf-8 -*-
r"""Curvas de referência da B3 (arquivo diário "Taxas de Mercado para Swaps", TaxaSwap.txt).

Fonte e alcance (verificado em 2026-10-14)
------------------------------------------
``https://www.b3.com.br/pesquisapregao/download?filelist=TSAAMMDD.ex_,`` devolve
um zip com outro zip dentro (``.ex_``, executável autoextraível) que contém
``TaxaSwap.txt`` — as curvas que a B3 usa para precificar swaps e margens,
uma linha por vértice. Dias sem pregão devolvem zip vazio. Curvas usadas:

=====  =================================  ===============  ==================
código descrição                          tipo             disponível desde
=====  =================================  ===============  ==================
PRE    DI × Pré                           nominal (swap)   2001-01
DIC    DI × IPCA (cupom de IPCA)          real (swap)      2005
TPR    LTN                                nominal (Tesouro) 2004-01
TIC    NTN-B                              real (Tesouro)   2004-01
=====  =================================  ===============  ==================

Inflação implícita em duas versões: **de títulos** (TPR × TIC — mesmo
emissor, cancela risco de crédito; é a recomendada em ``mercado/README.md``)
e **de swaps** (PRE × DIC). Fisher: (1+nominal)/(1+real) − 1.

Layout de ``TaxaSwap.txt`` (posições base 0, largura fixa): data AAAAMMDD
[11:19]; código da curva [21:26]; descrição [26:41]; dias corridos [41:46];
dias úteis [46:51]; sinal [51]; taxa com 7 decimais [52:66].

Interpolação: *flat forward* base 252 (convenção do DI) entre vértices,
sem extrapolação. Guardamos só os vértices-padrão ``DU_PADRAO`` por curva e
dia (o arquivo bruto tem ~30 mil linhas/dia; não é guardado).
"""
from __future__ import annotations

import io
import re
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pandas as pd
import requests

from mercado.bcb import DIR_MACRO, RAIZ

from .calendario import feriados

DIR_CACHE = DIR_MACRO / "b3_taxaswap"
DIR_MERCADO = RAIZ / "dados" / "mercado"
URL = "https://www.b3.com.br/pesquisapregao/download?filelist=TS{d:%y%m%d}.ex_,"
CURVAS = ("PRE", "DIC", "TPR", "TIC")
DU_PADRAO = (21, 42, 63, 126, 189, 252, 378, 504, 630, 756, 1008, 1260, 1512, 1764, 2016, 2520)
HORIZONTES = {"3m": 63, "6m": 126, "1a": 252, "2a": 504, "3a": 756, "5a": 1260, "10a": 2520}
_H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
_DIGITOS = re.compile(r"\d+")


# ─── download e parsing ──────────────────────────────────────────────────

def baixar_dia(d, tentativas: int = 4) -> list[str] | None:
    """Linhas do TaxaSwap.txt de ``d``; ``None`` se a B3 não tiver arquivo (dia sem pregão)."""
    d = pd.Timestamp(d)
    ultimo = None
    for k in range(tentativas):
        try:
            r = requests.get(URL.format(d=d), headers=_H, timeout=90)
            if r.content[:2] != b"PK":
                raise RuntimeError(f"resposta não-zip ({r.status_code}, {len(r.content)} bytes)")
            z = zipfile.ZipFile(io.BytesIO(r.content))
            if not z.namelist():
                return None
            interno = zipfile.ZipFile(io.BytesIO(z.read(z.namelist()[0])))
            return interno.read(interno.namelist()[0]).decode("latin-1").splitlines()
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(2 * (k + 1))
    raise RuntimeError(f"B3 TS {d.date()}: {ultimo}")


def parse(linhas: list[str], curvas=CURVAS) -> pd.DataFrame:
    """Vértices brutos (data, curva, dc, du, taxa % a.a.) das curvas pedidas."""
    regs = []
    for l in linhas:
        cod = l[21:26].strip()
        if cod not in curvas or len(l) < 64:
            continue
        # Até out/2002 o campo da taxa tinha 12 dígitos (linha de 65 posições); depois, 14.
        # Nos dois casos a escala é de 7 casas decimais.
        m = _DIGITOS.match(l, 52)
        if not m:
            continue
        sinal = -1.0 if l[51] == "-" else 1.0
        regs.append((l[11:19], cod, int(l[41:46]), int(l[46:51]), sinal * int(m.group(0)[:14]) / 1e7))
    df = pd.DataFrame(regs, columns=["data", "curva", "dc", "du", "taxa"])
    if len(df):
        df["data"] = pd.to_datetime(df["data"], format="%Y%m%d")
    return df


def flat_forward(du: np.ndarray, taxa: np.ndarray, alvo) -> np.ndarray:
    """Interpolação flat forward base 252 (sem extrapolação: fora de [min, max] -> NaN)."""
    o = np.argsort(du)
    du, taxa = np.asarray(du, float)[o], np.asarray(taxa, float)[o]
    du, idx = np.unique(du, return_index=True)
    taxa = taxa[idx]
    fator = (1 + taxa / 100.0) ** (du / 252.0)
    alvo = np.atleast_1d(np.asarray(alvo, float))
    out = np.full(alvo.shape, np.nan)
    if len(du) == 0:
        return out
    dentro = (alvo >= du[0]) & (alvo <= du[-1])
    if len(du) == 1:
        out[dentro] = taxa[0]
        return out
    lnf = np.interp(alvo[dentro], du, np.log(fator))  # log-linear no fator = forward constante
    out[dentro] = (np.exp(lnf) ** (252.0 / alvo[dentro]) - 1) * 100.0
    return out


def vertices_padrao(bruto: pd.DataFrame, du_padrao=DU_PADRAO) -> pd.DataFrame:
    """Reduz os vértices brutos aos ``du_padrao`` por curva-dia; guarda também o DU máximo da curva."""
    linhas = []
    for (d, c), g in bruto.groupby(["data", "curva"]):
        g = g[g["du"] > 0]
        tx = flat_forward(g["du"].to_numpy(), g["taxa"].to_numpy(), du_padrao)
        for du, t in zip(du_padrao, tx):
            linhas.append((d, c, du, t))
        linhas.append((d, c, -1, float(g["du"].max()) if len(g) else np.nan))  # du=-1: DU máximo
    return pd.DataFrame(linhas, columns=["data", "curva", "du", "taxa"])


# ─── coleta cumulativa ───────────────────────────────────────────────────

def _ledger() -> pd.DataFrame:
    p = DIR_CACHE / "_ledger.csv"
    return pd.read_csv(p, parse_dates=["data"]) if p.exists() else pd.DataFrame(columns=["data", "status"])


def _processar(d: pd.Timestamp) -> tuple[pd.Timestamp, str, pd.DataFrame | None]:
    try:
        linhas = baixar_dia(d)
    except Exception as e:  # noqa: BLE001
        return d, f"erro: {str(e)[:80]}", None
    if linhas is None:
        return d, "sem_arquivo", None
    bruto = parse(linhas)
    if bruto.empty:  # arquivo existe mas sem nenhuma das curvas: não marca como ok
        return d, "erro: nenhuma curva reconhecida", None
    return d, "ok", vertices_padrao(bruto)


def coletar(inicio: str = "2001-01-02", fim: str | None = None, threads: int = 4, verbose: bool = True) -> dict:
    """Baixa todos os dias úteis de [inicio, fim] ainda não processados (retomável, por ano)."""
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    fim = fim or date.today().isoformat()
    led = _ledger()
    feitos = set(led.loc[led["status"].isin(["ok", "sem_arquivo"]), "data"])
    dias = [d for d in pd.bdate_range(inicio, fim, freq="C", holidays=list(pd.DatetimeIndex(feriados())))
            if d not in feitos]
    resumo = {"pendentes": len(dias), "ok": 0, "sem_arquivo": 0, "erro": 0}
    if not dias:
        return resumo
    serie = pd.Series(pd.DatetimeIndex(dias))
    for ano, grupo in serie.groupby(serie.dt.year):
        with ThreadPoolExecutor(threads) as ex:
            res = list(ex.map(_processar, grupo))
        novos = [df for _, s, df in res if s == "ok" and df is not None and len(df)]
        if novos:
            p = DIR_CACHE / f"{ano}.csv.gz"
            base = [pd.read_csv(p, parse_dates=["data"])] if p.exists() else []
            tudo = pd.concat(base + novos, ignore_index=True).drop_duplicates(["data", "curva", "du"], keep="last")
            tudo.sort_values(["data", "curva", "du"]).to_csv(p, index=False, date_format="%Y-%m-%d")
        reg = pd.DataFrame([{"data": d, "status": s if s in ("ok", "sem_arquivo") else "erro"} for d, s, _ in res])
        led = (pd.concat([led, reg], ignore_index=True) if len(led) else reg).drop_duplicates("data", keep="last")
        led.sort_values("data").to_csv(DIR_CACHE / "_ledger.csv", index=False, date_format="%Y-%m-%d")
        for _, s, _ in res:
            resumo["ok" if s == "ok" else "sem_arquivo" if s == "sem_arquivo" else "erro"] += 1
        if verbose:
            print(f"  B3 {ano}: {sum(s == 'ok' for _, s, _ in res)} ok, "
                  f"{sum(s == 'sem_arquivo' for _, s, _ in res)} sem arquivo, "
                  f"{sum(s.startswith('erro') for _, s, _ in res)} erro", flush=True)
    return resumo


# ─── séries ──────────────────────────────────────────────────────────────

def carregar_vertices() -> pd.DataFrame:
    partes = [pd.read_csv(p, parse_dates=["data"]) for p in sorted(DIR_CACHE.glob("*.csv.gz"))]
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=["data", "curva", "du", "taxa"])


def curvas_diarias(vertices: pd.DataFrame | None = None) -> pd.DataFrame:
    """Tabela larga por dia: taxas por curva e horizonte, implícitas (títulos e swaps), inclinação."""
    v = carregar_vertices() if vertices is None else vertices
    v = v[v["du"].isin(list(HORIZONTES.values()))]
    w = v.pivot_table(index="data", columns=["curva", "du"], values="taxa")
    out = pd.DataFrame(index=w.index)
    for c in CURVAS:
        for nome, du in HORIZONTES.items():
            out[f"{c.lower()}_{nome}"] = w[(c, du)] if (c, du) in w.columns else np.nan
    for nome in HORIZONTES:
        out[f"implicita_titulos_{nome}"] = 100 * ((1 + out[f"tpr_{nome}"] / 100) / (1 + out[f"tic_{nome}"] / 100) - 1)
        out[f"implicita_swap_{nome}"] = 100 * ((1 + out[f"pre_{nome}"] / 100) / (1 + out[f"dic_{nome}"] / 100) - 1)
    out["inclinacao_pre_5a_3m"] = out["pre_5a"] - out["pre_3m"]
    out["inclinacao_pre_2a_3m"] = out["pre_2a"] - out["pre_3m"]
    out.index.name = "data"
    return out.reset_index()


def validar_contra_anbima(diario: pd.DataFrame, horizontes=("1a", "2a", "3a", "5a", "10a")) -> pd.DataFrame | None:
    """B3 (títulos e swaps) × ETTJ ANBIMA na janela de sobreposição."""
    from .anbima import DIR_ANBIMA, curva_em_prazos
    p = DIR_ANBIMA / "ettj_parametros.csv"
    if not p.exists():
        return None
    anos = tuple(float(h[:-1]) for h in horizontes)
    anb = curva_em_prazos(pd.read_csv(p, parse_dates=["data"]), anos=anos)
    j = diario.merge(anb, on="data")
    if j.empty:
        return None
    linhas = []
    for h, a in zip(horizontes, anos):
        pares = {("titulos", "nominal"): f"tpr_{h}", ("titulos", "real"): f"tic_{h}",
                 ("titulos", "implicita"): f"implicita_titulos_{h}", ("swap", "nominal"): f"pre_{h}",
                 ("swap", "real"): f"dic_{h}", ("swap", "implicita"): f"implicita_swap_{h}"}
        for (fonte, curva), col in pares.items():
            ref = f"{curva}_{a:g}a"
            dif = j[col] - j[ref]
            linhas.append({"horizonte": h, "fonte_b3": fonte, "curva": curva, "n_dias": int(dif.notna().sum()),
                           "dif_media_pp": dif.mean(), "dif_abs_max_pp": dif.abs().max(), "corr_diaria": j[col].corr(j[ref])})
    return pd.DataFrame(linhas)


def construir(coletar_antes: bool = True, threads: int = 4) -> dict:
    if coletar_antes:
        coletar(threads=threads)
    dia = curvas_diarias()
    DIR_MERCADO.mkdir(parents=True, exist_ok=True)
    dia.to_csv(DIR_MERCADO / "curvas_b3_diario.csv", index=False, date_format="%Y-%m-%d")
    m = dia.set_index("data").resample("MS").mean()
    m.index = m.index.to_period("M"); m.index.name = "mes"
    m.to_csv(DIR_MERCADO / "curvas_b3_mensal.csv")
    val = validar_contra_anbima(dia)
    if val is not None:
        val.to_csv(DIR_MERCADO / "validacao_b3_vs_anbima.csv", index=False)
    cob = {c: float(dia[c].notna().mean()) for c in dia.columns if c != "data"}
    return {"diario": dia, "mensal": m, "validacao": val, "cobertura": cob}

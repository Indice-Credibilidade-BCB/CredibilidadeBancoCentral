# -*- coding: utf-8 -*-
"""ANBIMA: ETTJ (curvas nominal, real e inflação implícita) e taxas indicativas de títulos públicos.

Limitação de acesso (verificada em 2026-10-14)
----------------------------------------------
O site público da ANBIMA só serve **cerca de um mês** para trás:

* ETTJ (``est-termo/CZ-down.asp``): parâmetros Svensson + vértices, desde
  ~21 dias úteis antes de hoje;
* mercado secundário de títulos (``merc-sec/arqs/msAAMMDD.txt``): LTN, NTN-B,
  NTN-F etc. com taxa indicativa, mesma janela.

Fora dessa janela a resposta é vazia (ETTJ) ou 404 (títulos). O histórico
completo exige o ANBIMA Data (cadastro) ou um feed pago. Por isso este
módulo é um **coletor cumulativo**: cada execução baixa os dias da janela que
ainda não estão salvos e acrescenta aos CSVs em ``dados/mercado/anbima/``.
Rodando ao menos uma vez a cada ~3 semanas, a série cresce sem buracos a
partir de 2026-09-14. O histórico anterior vem do Tesouro Direto
(``mercado.inflacao_implicita``), validado contra esta fonte na sobreposição.

Svensson (convenção ANBIMA): taxa em t anos (DU/252), em decimal,

    y(t) = β1 + β2·g(λ1 t) + β3·[g(λ1 t) − e^{−λ1 t}] + β4·[g(λ2 t) − e^{−λ2 t}],
    g(x) = (1 − e^{−x}) / x.
"""
from __future__ import annotations

import io
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from mercado.bcb import RAIZ

from .calendario import feriados

DIR_ANBIMA = RAIZ / "dados" / "mercado" / "anbima"
URL_CZ = "https://www.anbima.com.br/informacoes/est-termo/CZ.asp"
URL_CZ_DOWN = "https://www.anbima.com.br/informacoes/est-termo/CZ-down.asp"
URL_MS = "https://www.anbima.com.br/informacoes/merc-sec/arqs/ms{d:%y%m%d}.txt"
_H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def _num(s: str) -> float:
    """'1.008' -> 1008 ; '6,2791' -> 6.2791 ; '3,58E-02' -> 0.0358 (formato pt-BR)."""
    s = s.strip()
    if not s:
        return np.nan
    return float(s.replace(".", "").replace(",", ".")) if "E" not in s.upper() else float(s.replace(",", "."))


def svensson(t_anos: np.ndarray | float, b1: float, b2: float, b3: float, b4: float,
             l1: float, l2: float) -> np.ndarray:
    """Taxa (decimal) da curva Svensson da ANBIMA no prazo t (anos, base 252)."""
    t = np.maximum(np.asarray(t_anos, float), 1e-6)
    g1 = (1 - np.exp(-l1 * t)) / (l1 * t)
    g2 = (1 - np.exp(-l2 * t)) / (l2 * t)
    return b1 + b2 * g1 + b3 * (g1 - np.exp(-l1 * t)) + b4 * (g2 - np.exp(-l2 * t))


# ─── parsing ─────────────────────────────────────────────────────────────

def parse_ettj(texto: str, data: pd.Timestamp) -> tuple[pd.DataFrame, pd.DataFrame]:
    """CSV da ETTJ -> (parâmetros, vértices). Vazio se a data estiver fora da janela."""
    linhas = [l for l in texto.splitlines()]
    params, vertices = [], []
    secao = None
    for l in linhas:
        cel = l.split(";")
        if len(cel) >= 7 and cel[1].strip() == "Beta 1":
            secao = "params"; continue
        if cel[0].strip().startswith("Vertices"):
            secao = "vertices"; continue
        if not l.strip():
            secao = None if secao == "vertices" else secao
            continue
        if secao == "params" and cel[0].strip() in ("PREFIXADOS", "IPCA"):
            b = [_num(x) for x in cel[1:7]]
            params.append({"data": data, "curva": "nominal" if cel[0].strip() == "PREFIXADOS" else "real",
                           "beta1": b[0], "beta2": b[1], "beta3": b[2], "beta4": b[3], "lambda1": b[4], "lambda2": b[5]})
        elif secao == "vertices" and len(cel) >= 4:
            vertices.append({"data": data, "du": int(_num(cel[0])), "real": _num(cel[1]),
                             "nominal": _num(cel[2]), "implicita": _num(cel[3])})
    return pd.DataFrame(params), pd.DataFrame(vertices)


def parse_titulos(texto: str) -> pd.DataFrame:
    """Arquivo ``msAAMMDD.txt`` (separador '@') -> DataFrame de títulos, sem duplicatas."""
    linhas = texto.splitlines()
    ini = next((i for i, l in enumerate(linhas) if l.startswith("Titulo@")), None)
    if ini is None:
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO("\n".join(linhas[ini:])), sep="@", dtype=str)
    out = pd.DataFrame({
        "data": pd.to_datetime(df["Data Referencia"], format="%Y%m%d"),
        "titulo": df["Titulo"].str.strip(),
        "codigo_selic": df["Codigo SELIC"].str.strip(),
        "emissao": pd.to_datetime(df["Data Base/Emissao"], format="%Y%m%d", errors="coerce"),
        "vencimento": pd.to_datetime(df["Data Vencimento"], format="%Y%m%d"),
        "taxa_compra": df["Tx. Compra"].map(_num_simples),
        "taxa_venda": df["Tx. Venda"].map(_num_simples),
        "taxa_indicativa": df["Tx. Indicativas"].map(_num_simples),
        "pu": df["PU"].map(_num_simples),
    })
    return out.drop_duplicates(["data", "titulo", "vencimento"]).reset_index(drop=True)


def _num_simples(s) -> float:
    """Números do ms*.txt: vírgula decimal, sem separador de milhar."""
    try:
        return float(str(s).replace(",", "."))
    except ValueError:
        return np.nan


# ─── coleta ──────────────────────────────────────────────────────────────

def _dias_uteis(inicio: date, fim: date) -> list[pd.Timestamp]:
    return list(pd.bdate_range(inicio, fim, freq="C", holidays=list(pd.DatetimeIndex(feriados()))))


def _anexar(novo: pd.DataFrame, caminho: Path, chave: list[str]) -> pd.DataFrame:
    if caminho.exists():
        velho = pd.read_csv(caminho, parse_dates=[c for c in ("data", "emissao", "vencimento") if c in novo.columns])
        novo = pd.concat([velho, novo], ignore_index=True)
    novo = novo.drop_duplicates(chave, keep="last").sort_values(chave).reset_index(drop=True)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    novo.to_csv(caminho, index=False, date_format="%Y-%m-%d")
    return novo


def coletar(dias_atras: int = 45, hoje: date | None = None, pausa: float = 0.5) -> dict:
    """Baixa ETTJ e títulos de todos os dias úteis da janela ainda não salvos.

    Idempotente: dias já presentes nos CSVs são pulados. Devolve contagens.
    """
    hoje = hoje or date.today()
    p_par, p_ver, p_tit = DIR_ANBIMA / "ettj_parametros.csv", DIR_ANBIMA / "ettj_vertices.csv", DIR_ANBIMA / "titulos_publicos.csv"
    ja_ettj = set(pd.read_csv(p_par, parse_dates=["data"])["data"]) if p_par.exists() else set()
    ja_tit = set(pd.read_csv(p_tit, parse_dates=["data"])["data"]) if p_tit.exists() else set()
    s = requests.Session(); s.headers.update(_H)
    s.get(URL_CZ, timeout=60)
    pars, vers, tits = [], [], []
    vazios_ettj, vazios_tit = [], []
    for d in _dias_uteis(hoje - timedelta(days=dias_atras), hoje):
        if d not in ja_ettj:
            r = s.post(URL_CZ_DOWN, data={"Idioma": "PT", "Dt_Ref": d.strftime("%d/%m/%Y"), "saida": "csv"},
                       timeout=60, headers={"Referer": URL_CZ})
            p, v = parse_ettj(r.content.decode("latin-1"), d)
            (pars.append(p), vers.append(v)) if len(p) else vazios_ettj.append(str(d.date()))
            time.sleep(pausa)
        if d not in ja_tit:
            r = requests.get(URL_MS.format(d=d), timeout=60, headers=_H)
            t = parse_titulos(r.content.decode("latin-1")) if r.status_code == 200 else pd.DataFrame()
            tits.append(t) if len(t) else vazios_tit.append(str(d.date()))
            time.sleep(pausa)
    out = {"novos_dias_ettj": len(pars), "novos_dias_titulos": len(tits),
           "fora_da_janela_ettj": vazios_ettj, "fora_da_janela_titulos": vazios_tit}
    if pars:
        _anexar(pd.concat(pars), p_par, ["data", "curva"])
        _anexar(pd.concat(vers), p_ver, ["data", "du"])
    if tits:
        _anexar(pd.concat(tits), p_tit, ["data", "titulo", "vencimento"])
    for nome, p in (("parametros", p_par), ("vertices", p_ver), ("titulos", p_tit)):
        if p.exists():
            d = pd.read_csv(p, parse_dates=["data"])["data"]
            out[f"{nome}_cobertura"] = (str(d.min().date()), str(d.max().date()), int(d.nunique()))
    return out


def curva_em_prazos(parametros: pd.DataFrame, anos: tuple[float, ...] = (1, 2, 3, 5, 10)) -> pd.DataFrame:
    """Nominal, real e implícita (% a.a.) em prazos fixos, a partir dos parâmetros Svensson."""
    linhas = []
    for d, g in parametros.groupby("data"):
        g = g.set_index("curva")
        if not {"nominal", "real"} <= set(g.index):
            continue
        linha = {"data": d}
        for a in anos:
            n = svensson(a, *g.loc["nominal", ["beta1", "beta2", "beta3", "beta4", "lambda1", "lambda2"]])
            r = svensson(a, *g.loc["real", ["beta1", "beta2", "beta3", "beta4", "lambda1", "lambda2"]])
            linha[f"nominal_{a:g}a"] = 100 * float(n)
            linha[f"real_{a:g}a"] = 100 * float(r)
            linha[f"implicita_{a:g}a"] = 100 * float((1 + n) / (1 + r) - 1)
        linhas.append(linha)
    return pd.DataFrame(linhas)

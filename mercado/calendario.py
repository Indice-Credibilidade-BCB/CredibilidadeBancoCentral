# -*- coding: utf-8 -*-
"""Calendário de dias úteis (ANBIMA/B3), vencimentos do DI1 e calendário estruturado do Copom.

Dias úteis
----------
A B3 e a ANBIMA usam o mesmo calendário de feriados nacionais. Fonte primária:
a planilha oficial da ANBIMA (``feriados_nacionais.xls``, 2001–2099), baixada
para ``dados/macro/``. Fallback sem rede: regra algorítmica (fixos + móveis
derivados da Páscoa + Consciência Negra desde 2024). ``validar_feriados``
compara as duas fontes.

Vencimentos DI1
---------------
Contrato futuro de DI de um dia (DI1) vence no **primeiro dia útil do mês de
vencimento**. A B3 lista sempre os **quatro meses subsequentes** e, depois,
os inícios de trimestre — por isso o "1º ao 4º vencimento" numa data D são os
primeiros dias úteis dos quatro meses seguintes cujo vencimento é > D. Código:
``DI1`` + letra do mês + ano com 2 dígitos (F G H J K M N Q U V X Z).

A taxa de um DI1 em D é a taxa efetiva (base 252) do CDI acumulado de D
(inclusive) até o vencimento (exclusive). O número de dias úteis desse
intervalo é o ``DU`` do contrato.

Calendário estruturado do Copom
-------------------------------
Uma linha por reunião, com tudo o que o Bloco 5 (Kuttner) e o Bloco 6
precisam: datas de pregão em torno do anúncio (D−1, D, D+1 — o Copom anuncia
**após** o fechamento da B3, então o fechamento de D ainda é "antes"), os
quatro DI1 vivos em D com seus DU, o contrato curto que captura a decisão,
quantas outras reuniões ele atravessa (contaminação por expectativas da
reunião seguinte) e os DU necessários para o ajuste de Kuttner:

    surpresa ≈ Δtaxa(DI1) × DU[D+1, venc) / DU[vigência, venc)

(com vigência = D+1 o fator é 1; o ajuste importa quando a vigência é
posterior ao primeiro pregão pós-anúncio).
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from validacao.dados_bcb import DIR_MACRO, RAIZ, reunioes_copom

DIR_MERCADO = RAIZ / "dados" / "mercado"
URL_FERIADOS = "https://www.anbima.com.br/feriados/arqs/feriados_nacionais.xls"
LETRAS_DI1 = "FGHJKMNQUVXZ"  # jan..dez


# ─── Feriados ────────────────────────────────────────────────────────────

def _pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher)."""
    a = ano % 19; b, c = divmod(ano, 100); d, e = divmod(b, 4)
    f = (b + 8) // 25; g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def feriados_algoritmicos(ano_ini: int = 2000, ano_fim: int = 2035) -> pd.DatetimeIndex:
    """Feriados nacionais pela regra (mesmo conjunto da ANBIMA)."""
    out = []
    for a in range(ano_ini, ano_fim + 1):
        p = _pascoa(a)
        out += [date(a, 1, 1), p - timedelta(days=48), p - timedelta(days=47),  # carnaval seg/ter
                p - timedelta(days=2), date(a, 4, 21), date(a, 5, 1),            # sexta santa, Tiradentes, trabalho
                p + timedelta(days=60), date(a, 9, 7), date(a, 10, 12),          # Corpus Christi, independência, N. Sra.
                date(a, 11, 2), date(a, 11, 15), date(a, 12, 25)]
        if a >= 2024:
            out.append(date(a, 11, 20))  # Consciência Negra: feriado nacional desde a Lei 14.759/2023
    return pd.DatetimeIndex(sorted(set(out)))


def feriados_anbima(atualizar: bool = False) -> pd.DatetimeIndex:
    """Feriados da planilha oficial da ANBIMA (cache em ``dados/macro/feriados_anbima.csv``)."""
    cache = DIR_MACRO / "feriados_anbima.csv"
    if cache.exists() and not atualizar:
        return pd.DatetimeIndex(pd.read_csv(cache, parse_dates=["data"])["data"])
    r = requests.get(URL_FERIADOS, timeout=120, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    xls = DIR_MACRO / "feriados_anbima.xls"
    DIR_MACRO.mkdir(parents=True, exist_ok=True)
    xls.write_bytes(r.content)
    df = pd.read_excel(xls, engine="xlrd")
    datas = pd.to_datetime(df.iloc[:, 0], errors="coerce").dropna()
    datas = pd.DatetimeIndex(sorted(set(datas.dt.normalize())))
    pd.DataFrame({"data": datas}).to_csv(cache, index=False)
    return datas


@lru_cache(maxsize=1)
def feriados() -> np.ndarray:
    """Feriados como ``datetime64[D]`` para ``np.busday_*``.

    ANBIMA (2001–2099) quando disponível; a regra algorítmica cobre os anos
    anteriores a 2001 (Copom desde 1996) e serve de fallback sem rede. As
    duas fontes coincidem em 2001–2030 (``validar_feriados``).
    """
    regra = feriados_algoritmicos(1994, 2100)
    try:
        anb = feriados_anbima()
        f = pd.DatetimeIndex(sorted(set(anb) | set(regra[regra.year < anb.min().year])))
    except Exception:  # noqa: BLE001 — sem rede e sem cache
        f = regra
    return np.array(f.values.astype("datetime64[D]"))


def validar_feriados(ano_ini: int = 2001, ano_fim: int = 2030) -> dict:
    """Diferenças entre a planilha ANBIMA e a regra algorítmica (só dias úteis da semana importam)."""
    a = set(d for d in feriados_anbima() if ano_ini <= d.year <= ano_fim and d.weekday() < 5)
    b = set(d for d in feriados_algoritmicos(ano_ini, ano_fim) if d.weekday() < 5)
    return {"so_anbima": sorted(str(x.date()) for x in a - b), "so_regra": sorted(str(x.date()) for x in b - a)}


def eh_dia_util(d) -> bool:
    return bool(np.is_busday(np.datetime64(pd.Timestamp(d).date(), "D"), holidays=feriados()))


def du(inicio, fim) -> int:
    """Dias úteis em [inicio, fim) — convenção B3/ANBIMA."""
    return int(np.busday_count(np.datetime64(pd.Timestamp(inicio).date(), "D"),
                               np.datetime64(pd.Timestamp(fim).date(), "D"), holidays=feriados()))


def du_vetor(inicio: pd.Series, fim: pd.Series) -> np.ndarray:
    a = pd.to_datetime(inicio).values.astype("datetime64[D]")
    b = pd.to_datetime(fim).values.astype("datetime64[D]")
    return np.busday_count(a, b, holidays=feriados())


def dia_util_anterior(d) -> pd.Timestamp:
    """Último dia útil estritamente anterior a d."""
    x = np.busday_offset(np.datetime64(pd.Timestamp(d).date(), "D"), -1, roll="forward", holidays=feriados())
    return pd.Timestamp(x)


def dia_util_seguinte(d) -> pd.Timestamp:
    """Primeiro dia útil estritamente posterior a d."""
    x = np.busday_offset(np.datetime64(pd.Timestamp(d).date(), "D"), 1, roll="backward", holidays=feriados())
    return pd.Timestamp(x)


def ajustar_para_util(d) -> pd.Timestamp:
    """d se for útil, senão o próximo dia útil."""
    x = np.busday_offset(np.datetime64(pd.Timestamp(d).date(), "D"), 0, roll="forward", holidays=feriados())
    return pd.Timestamp(x)


# ─── DI1 ─────────────────────────────────────────────────────────────────

def vencimento_di1(ano: int, mes: int) -> pd.Timestamp:
    """Primeiro dia útil do mês."""
    return ajustar_para_util(date(ano, mes, 1))


def codigo_di1(venc: pd.Timestamp) -> str:
    return f"DI1{LETRAS_DI1[venc.month - 1]}{venc.year % 100:02d}"


def vencimentos_di1_apos(d, n: int = 4) -> list[pd.Timestamp]:
    """Os ``n`` primeiros vencimentos mensais estritamente posteriores a d (1º..nº vencimento)."""
    d = pd.Timestamp(d)
    out = []
    ano, mes = d.year, d.month
    while len(out) < n:
        v = vencimento_di1(ano, mes)
        if v > d:
            out.append(v)
        mes += 1
        if mes == 13:
            ano, mes = ano + 1, 1
    return out


def tabela_vencimentos_genericos(inicio: str, fim: str, n: int = 4) -> pd.DataFrame:
    """Para cada dia útil em [inicio, fim]: códigos, vencimentos e DU do 1º..nº vencimento.

    É a chave para casar séries "1º ao 4º vencimento" (contrato genérico) com
    o contrato específico vivo em cada data.
    """
    dias = pd.bdate_range(inicio, fim, freq="C", holidays=list(pd.DatetimeIndex(feriados())))
    linhas = []
    for d in dias:
        linha = {"data": d}
        for k, v in enumerate(vencimentos_di1_apos(d, n), start=1):
            linha[f"di1_{k}_codigo"] = codigo_di1(v)
            linha[f"di1_{k}_venc"] = v
            linha[f"di1_{k}_du"] = du(d, v)
        linhas.append(linha)
    return pd.DataFrame(linhas)


# ─── Copom ───────────────────────────────────────────────────────────────

def _agenda_futura() -> pd.Series:
    """Reuniões futuras (opcional): ``dados/mercado/copom_agenda_futura.csv`` com coluna ``data_reuniao``.

    O BCB não expõe o calendário futuro por API. Sem o arquivo, a última
    reunião fica com ``proxima_reuniao`` vazia e a contaminação do contrato
    curto não é avaliada para ela.
    """
    p = DIR_MERCADO / "copom_agenda_futura.csv"
    if not p.exists():
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(pd.read_csv(p)["data_reuniao"])


def calendario_copom(reunioes: pd.DataFrame | None = None, n_venc: int = 4) -> pd.DataFrame:
    """Calendário estruturado do Copom × DI1 (ver docstring do módulo)."""
    r = (reunioes_copom() if reunioes is None else reunioes).copy()
    r = r.sort_values("data_reuniao").reset_index(drop=True)
    datas = pd.concat([r["data_reuniao"], _agenda_futura()]).drop_duplicates().sort_values().reset_index(drop=True)
    linhas = []
    for i, row in r.iterrows():
        D = pd.Timestamp(row["data_reuniao"])
        d_util = eh_dia_util(D)
        dm1 = dia_util_anterior(D)
        d0 = D if d_util else dia_util_anterior(D)  # último fechamento antes do anúncio
        dp1 = dia_util_seguinte(D)
        vig = pd.Timestamp(row["inicio_vigencia"]) if pd.notna(row.get("inicio_vigencia")) else dp1
        prox = datas[datas > D]
        prox = pd.Timestamp(prox.iloc[0]) if len(prox) else pd.NaT
        anterior = r.loc[i - 1, "meta_selic"] if i > 0 else np.nan
        linha = {
            "numero": int(row["numero"]), "codigo_focus": row.get("codigo_focus", ""),
            "data_reuniao": D, "dia_semana": D.day_name(), "extraordinaria": bool(row["extraordinaria"]),
            "reuniao_em_dia_util": d_util, "anuncio_pos_fechamento": True,
            "meta_selic": float(row["meta_selic"]), "meta_anterior": anterior,
            "variacao_bps": round(100 * (float(row["meta_selic"]) - anterior), 1) if np.isfinite(anterior) else np.nan,
            "inicio_vigencia": vig, "pregao_d_menos_1": dm1, "pregao_d0": d0, "pregao_d_mais_1": dp1,
            "proxima_reuniao": prox,
        }
        vencs = vencimentos_di1_apos(d0, n_venc)
        for k, v in enumerate(vencs, start=1):
            linha[f"di1_{k}_codigo"] = codigo_di1(v)
            linha[f"di1_{k}_venc"] = v
            linha[f"di1_{k}_du_em_d0"] = du(d0, v)
        # contrato curto: 1º vencimento posterior à vigência (é o que precifica a decisão);
        # contrato 2: o seguinte, para quando o curto está perto demais do vencimento.
        curto, seguinte = [v for v in vencimentos_di1_apos(vig, 2)]
        for pref, v in (("kuttner", curto), ("kuttner2", seguinte)):
            linha[f"{pref}_codigo"] = codigo_di1(v)
            linha[f"{pref}_venc"] = v
            linha[f"{pref}_du_dmais1_venc"] = du(dp1, v)
            linha[f"{pref}_du_vigencia_venc"] = du(vig, v)
            linha[f"{pref}_fator"] = (linha[f"{pref}_du_dmais1_venc"] / linha[f"{pref}_du_vigencia_venc"]
                                      if linha[f"{pref}_du_vigencia_venc"] > 0 else np.nan)
            linha[f"{pref}_atravessa_proxima"] = (bool(prox < v) if pd.notna(prox) else np.nan)
            linha[f"{pref}_n_reunioes_ate_venc"] = (int(((datas > D) & (datas < v)).sum()) if pd.notna(prox) else np.nan)
        linha["kuttner_du_dmenos1_vigencia"] = du(dm1, vig)
        # contrato curto com < 5 DU entre vigência e vencimento: taxa dominada por ruído de fim de contrato
        linha["kuttner_curto_demais"] = linha["kuttner_du_vigencia_venc"] < 5
        linhas.append(linha)
    return pd.DataFrame(linhas)


def salvar_calendario(caminho: Path | None = None) -> pd.DataFrame:
    caminho = caminho or (DIR_MERCADO / "calendario_copom_di1.csv")
    cal = calendario_copom()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    cal.to_csv(caminho, index=False, date_format="%Y-%m-%d")
    return cal

# -*- coding: utf-8 -*-
"""Acesso às fontes públicas do BCB, com cache em ``dados/macro/``.

(Movido de ``validacao/dados_bcb.py`` em 2026-10-19: é infraestrutura de
dados usada por ``mercado/`` e ``llm/``; ``validacao/`` continua o importando.)

Três APIs, todas sem chave:

* **SGS** (``api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}``) — séries
  temporais: IPCA, Selic, IBC-Br, câmbio, meta de inflação, composição da
  dívida.
* **Olinda / Expectativas** (``olinda.bcb.gov.br``) — pesquisa Focus:
  inflação 12 meses à frente (mediana e dispersão), Selic por reunião.
* **Histórico de taxas de juros** (``bcb.gov.br/api/servico/sitebcb``) —
  datas e decisões de cada reunião do Copom.

Cache = checkpoint, como no ``llm/``: cada série vira um CSV em
``dados/macro/`` (versionada: séries públicas do BCB, sem texto de terceiros).
Com ``atualizar=False`` (padrão) o CSV local é usado se existir; com
``atualizar=True`` baixa de novo e sobrescreve. Nenhuma função aqui exige
rede se o cache já estiver populado — os testes rodam sem rede.

Códigos SGS verificados em 2026-09-05 contra os últimos valores publicados
(ver ``SGS``). O 11428 é o IPCA de preços livres (variação mensal) — batido
contra o 433 (cheio) no mesmo mês. O 4177 é a participação (%) dos títulos
indexados à Selic na DPMFi — o insumo do controle-Fiocca (Bloco 6).
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parents[1]
DIR_MACRO = RAIZ / "dados" / "macro"

# Códigos SGS. Nome curto -> (código, descrição, frequência).
SGS: dict[str, tuple[int, str, str]] = {
    "ipca_mensal": (433, "IPCA - variação mensal (%)", "M"),
    "ipca_12m": (13522, "IPCA - acumulado 12 meses (%)", "M"),
    "ipca_livres_mensal": (11428, "IPCA - preços livres - variação mensal (%)", "M"),
    "selic_meta": (432, "Meta Selic definida pelo Copom (% a.a.)", "D"),
    "selic_diaria": (1178, "Selic diária anualizada (% a.a.)", "D"),
    "selic_mensal": (4189, "Selic acumulada no mês anualizada (% a.a.)", "M"),
    "cdi_diario": (12, "CDI diário (% a.d.)", "D"),
    "ibcbr": (24363, "IBC-Br (índice)", "M"),
    "ibcbr_dessaz": (24364, "IBC-Br dessazonalizado (índice)", "M"),
    "cambio_media_mensal": (3695, "Câmbio R$/US$ - média mensal - venda", "M"),
    "cambio_fim_mes": (3698, "Câmbio R$/US$ - fim de período - venda", "M"),
    "cambio_diario": (1, "Câmbio R$/US$ - diário - venda", "D"),
    "meta_inflacao": (13521, "Meta para a inflação (% a.a.)", "A"),
    "divida_selic_pct": (4177, "DPMFi - participação por indexador - Selic (%)", "M"),
    "divida_prefixado_pct": (4178, "DPMFi - participação por indexador - prefixado (%)", "M"),
}

# Bandas de tolerância da meta (p.p.), por ano-calendário. Fonte: Resoluções do
# CMN. Meta contínua de 3% com banda ±1,5 desde 2025.
BANDA_TOLERANCIA: dict[int, float] = {
    **{a: 2.0 for a in range(1999, 2003)},
    **{a: 2.5 for a in range(2003, 2006)},
    **{a: 2.0 for a in range(2006, 2017)},
    **{a: 1.5 for a in range(2017, 2040)},
}

_URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
_URL_OLINDA = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
_URL_COPOM = "https://www.bcb.gov.br/api/servico/sitebcb/historicotaxasjuros"
_HEADERS = {"User-Agent": "Mozilla/5.0 (pesquisa academica; CredibilidadeBCB)"}
_OLINDA_SAFE = "',/:"  # caracteres que ficam literais na query OData


def _get(url: str, params: dict | None = None, tentativas: int = 5, timeout: int = 90) -> requests.Response:
    """GET com retry exponencial.

    A API do BCB devolve 5xx esporádicos E, às vezes, uma página HTML de erro
    com status 200 — por isso o corpo é validado como JSON antes de aceitar.
    """
    ultimo: Exception | None = None
    for k in range(tentativas):
        try:
            r = requests.get(url, params=params, timeout=timeout, headers=_HEADERS)
            if r.status_code >= 500:
                raise requests.HTTPError(f"{r.status_code} em {url}")
            r.raise_for_status()
            r.json()  # levanta se o corpo não for JSON (página de erro com 200)
            return r
        except Exception as e:  # noqa: BLE001
            ultimo = e
            time.sleep(1.5 * (2 ** k))
    raise RuntimeError(f"falha após {tentativas} tentativas: {ultimo}")


# ─── SGS ─────────────────────────────────────────────────────────────────

def _caminho_cache(nome: str) -> Path:
    DIR_MACRO.mkdir(parents=True, exist_ok=True)
    return DIR_MACRO / f"{nome}.csv"


def sgs(nome: str, inicio: str = "1999-01-01", fim: str | None = None,
        atualizar: bool = False) -> pd.Series:
    """Série SGS pelo nome curto de ``SGS``, indexada por data (Timestamp).

    A API limita séries DIÁRIAS a janelas de 10 anos por chamada; por isso a
    busca é feita em blocos anuais e concatenada.
    """
    if nome not in SGS:
        raise KeyError(f"série desconhecida: {nome}. Conhecidas: {sorted(SGS)}")
    codigo, _, freq = SGS[nome]
    cache = _caminho_cache(nome)
    if cache.exists() and not atualizar:
        s = pd.read_csv(cache, parse_dates=["data"]).set_index("data")["valor"]
        return s.sort_index()

    fim_ts = pd.Timestamp(fim) if fim else pd.Timestamp.today().normalize()
    ini_ts = pd.Timestamp(inicio)
    partes: list[pd.DataFrame] = []
    passo = pd.DateOffset(years=9) if freq == "D" else pd.DateOffset(years=30)
    a = ini_ts
    while a <= fim_ts:
        b = min(a + passo - pd.Timedelta(days=1), fim_ts)
        r = _get(_URL_SGS.format(codigo=codigo), params={
            "formato": "json",
            "dataInicial": a.strftime("%d/%m/%Y"),
            "dataFinal": b.strftime("%d/%m/%Y"),
        })
        dados = r.json()
        if dados:
            partes.append(pd.DataFrame(dados))
        a = b + pd.Timedelta(days=1)
    if not partes:
        raise RuntimeError(f"SGS {codigo} ({nome}) sem dados em [{inicio}, {fim}]")
    df = pd.concat(partes, ignore_index=True)
    df["data"] = pd.to_datetime(df["data"], dayfirst=True)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["valor"]).drop_duplicates("data").sort_values("data")
    df[["data", "valor"]].to_csv(cache, index=False)
    return df.set_index("data")["valor"]


# ─── Olinda / Focus ──────────────────────────────────────────────────────

def _olinda(entidade: str, filtro: str, colunas: Iterable[str], pagina: int = 10000) -> pd.DataFrame:
    """Percorre a paginação OData ($top/$skip) até esgotar."""
    partes: list[pd.DataFrame] = []
    skip = 0
    sel = ",".join(colunas)
    while True:
        params = {"$format": "json", "$filter": filtro, "$select": sel,
                  "$orderby": "Data asc", "$top": pagina, "$skip": skip}
        # O servidor OData do BCB rejeita espaço codificado como '+' (que é o
        # que requests faz com params=); monta a query à mão com %20.
        url = _URL_OLINDA + entidade + "?" + "&".join(
            f"{quote(k, safe='$')}={quote(str(v), safe=_OLINDA_SAFE)}" for k, v in params.items())
        r = _get(url, timeout=180)
        valores = r.json().get("value", [])
        if not valores:
            break
        partes.append(pd.DataFrame(valores))
        if len(valores) < pagina:
            break
        skip += pagina
    if not partes:
        return pd.DataFrame(columns=list(colunas))
    import warnings
    with warnings.catch_warnings():
        # páginas antigas têm colunas inteiramente nulas (ex.: numeroRespondentes)
        warnings.simplefilter("ignore", FutureWarning)
        df = pd.concat(partes, ignore_index=True)
    df["Data"] = pd.to_datetime(df["Data"])
    return df


def focus_ipca_12m(inicio: str = "2001-11-01", atualizar: bool = False,
                   suavizada: bool = True) -> pd.DataFrame:
    """Focus diário: IPCA 12 meses à frente, todos os respondentes (baseCalculo 0).

    Colunas: Data, Mediana, Media, DesvioPadrao, Minimo, Maximo,
    numeroRespondentes. ``suavizada=True`` é a série "suavizada" do BCB
    (interpolação entre os dois anos-calendário), que é a que corresponde à
    janela fixa de 12 meses do Bloco 1.
    """
    nome = "focus_ipca_12m_suav" if suavizada else "focus_ipca_12m"
    cache = _caminho_cache(nome)
    if cache.exists() and not atualizar:
        return pd.read_csv(cache, parse_dates=["Data"])
    filtro = (f"Indicador eq 'IPCA' and Suavizada eq '{'S' if suavizada else 'N'}' "
              f"and baseCalculo eq 0 and Data ge '{inicio}'")
    df = _olinda("ExpectativasMercadoInflacao12Meses", filtro,
                 ["Data", "Mediana", "Media", "DesvioPadrao", "Minimo", "Maximo", "numeroRespondentes"])
    df = df.sort_values("Data").reset_index(drop=True)
    df.to_csv(cache, index=False)
    return df


def focus_selic_reunioes(inicio: str = "2001-01-01", atualizar: bool = False) -> pd.DataFrame:
    """Focus diário: Selic esperada por reunião do Copom (baseCalculo 0).

    Colunas: Data, Reuniao ("R5/2028"), Mediana, Media, DesvioPadrao,
    numeroRespondentes. Insumo de uma surpresa alternativa via survey (Selic
    esperada na véspera menos decidida); o artigo usa o swap DI×Pré 3m.
    """
    cache = _caminho_cache("focus_selic_reunioes")
    if cache.exists() and not atualizar:
        return pd.read_csv(cache, parse_dates=["Data"])
    filtro = f"baseCalculo eq 0 and Data ge '{inicio}'"
    df = _olinda("ExpectativasMercadoSelic", filtro,
                 ["Data", "Reuniao", "Mediana", "Media", "DesvioPadrao", "numeroRespondentes"])
    df = df.sort_values(["Data", "Reuniao"]).reset_index(drop=True)
    df.to_csv(cache, index=False)
    return df


# ─── Copom ───────────────────────────────────────────────────────────────

def reunioes_copom(atualizar: bool = False) -> pd.DataFrame:
    """Histórico de decisões do Copom.

    Colunas: numero, data_reuniao, extraordinaria, meta_selic, inicio_vigencia,
    fim_vigencia, codigo_focus ("R3/2015": ordem da reunião REGULAR no ano —
    o mesmo código usado pelo Focus em ``focus_selic_reunioes``).
    """
    cache = _caminho_cache("reunioes_copom")
    if cache.exists() and not atualizar:
        return pd.read_csv(cache, parse_dates=["data_reuniao", "inicio_vigencia", "fim_vigencia"])
    r = _get(_URL_COPOM, timeout=120)
    conteudo = r.json()["conteudo"]
    df = pd.DataFrame(conteudo).rename(columns={
        "NumeroReuniaoCopom": "numero", "DataReuniaoCopom": "data_reuniao",
        "ReuniaoExtraordinaria": "extraordinaria", "MetaSelic": "meta_selic",
        "DataInicioVigencia": "inicio_vigencia", "DataFimVigencia": "fim_vigencia",
    })
    for c in ("data_reuniao", "inicio_vigencia", "fim_vigencia"):
        df[c] = pd.to_datetime(df[c], utc=True, errors="coerce").dt.tz_convert(None).dt.normalize()
    df = df[["numero", "data_reuniao", "extraordinaria", "meta_selic", "inicio_vigencia", "fim_vigencia"]]
    df = df.dropna(subset=["data_reuniao"]).sort_values("data_reuniao").reset_index(drop=True)
    df["extraordinaria"] = df["extraordinaria"].fillna(False).astype(bool)
    df["codigo_focus"] = codigo_focus_reunioes(df)
    df.to_csv(cache, index=False)
    return df


def codigo_focus_reunioes(reunioes: pd.DataFrame) -> pd.Series:
    """"R{k}/{ano}" para cada reunião: k = ordem entre as REGULARES do ano.

    Reuniões extraordinárias recebem código vazio (o Focus não as pesquisa).
    """
    reg = reunioes[~reunioes["extraordinaria"]].copy()
    ano = reg["data_reuniao"].dt.year
    ordem = reg.groupby(ano).cumcount() + 1
    cod = pd.Series("", index=reunioes.index, dtype=object)
    cod.loc[reg.index] = "R" + ordem.astype(str) + "/" + ano.astype(str)
    return cod


# ─── Conveniência ────────────────────────────────────────────────────────

@dataclass
class Fontes:
    """Conjunto de séries brutas necessárias aos Blocos 2–6, já carregadas."""
    ipca_mensal: pd.Series
    ipca_12m: pd.Series
    ipca_livres_mensal: pd.Series
    selic_meta: pd.Series
    selic_mensal: pd.Series
    ibcbr_dessaz: pd.Series
    cambio_media_mensal: pd.Series
    meta_inflacao: pd.Series
    divida_selic_pct: pd.Series
    focus_ipca_12m: pd.DataFrame


def baixar_tudo(atualizar: bool = False, inicio: str = "1999-01-01") -> Fontes:
    """Baixa (ou lê do cache) tudo o que o painel mensal precisa."""
    return Fontes(
        ipca_mensal=sgs("ipca_mensal", inicio, atualizar=atualizar),
        ipca_12m=sgs("ipca_12m", inicio, atualizar=atualizar),
        ipca_livres_mensal=sgs("ipca_livres_mensal", inicio, atualizar=atualizar),
        selic_meta=sgs("selic_meta", inicio, atualizar=atualizar),
        selic_mensal=sgs("selic_mensal", inicio, atualizar=atualizar),
        ibcbr_dessaz=sgs("ibcbr_dessaz", inicio, atualizar=atualizar),
        cambio_media_mensal=sgs("cambio_media_mensal", inicio, atualizar=atualizar),
        meta_inflacao=sgs("meta_inflacao", inicio, atualizar=atualizar),
        divida_selic_pct=sgs("divida_selic_pct", inicio, atualizar=atualizar),
        focus_ipca_12m=focus_ipca_12m(atualizar=atualizar),
    )


if __name__ == "__main__":  # pragma: no cover
    import argparse
    ap = argparse.ArgumentParser(description="Baixa as séries do BCB para dados/macro/")
    ap.add_argument("--atualizar", action="store_true", help="ignora o cache e baixa de novo")
    args = ap.parse_args()
    f = baixar_tudo(atualizar=args.atualizar)
    for campo, valor in f.__dict__.items():
        n = len(valor)
        ult = valor.index.max() if isinstance(valor, pd.Series) else valor["Data"].max()
        print(f"{campo:24s} {n:6d} obs  até {ult.date()}")
    r = reunioes_copom(atualizar=args.atualizar)
    print(f"{'reunioes_copom':24s} {len(r):6d} obs  até {r['data_reuniao'].max().date()}")
    print(json.dumps({"dir": str(DIR_MACRO)}, ensure_ascii=False))

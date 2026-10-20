# -*- coding: utf-8 -*-
r"""Bloco 3 — índices rivais de credibilidade.

Quatro famílias, na ordem de independência em relação ao Focus (nota
metodológica 3: como o latente do Bloco 2 também vem do Focus, as âncoras
decisivas são a institucional e a de mercado):

1. **de Mendonça (2007)** — fórmula fechada sobre a expectativa 12 meses:

   .. math::

      IC_t = \begin{cases}
        1 & E_t\pi = \pi^* \\
        1 - \dfrac{E_t\pi - \pi^*}{0{,}20 - \pi^*} & \pi^* < E_t\pi < 20\% \\
        0 & E_t\pi \ge 20\% \text{ ou } E_t\pi < 0
      \end{cases}

   Para :math:`0 \le E_t\pi < \pi^*` o original é omisso; adotamos o desvio
   absoluto (simétrico), e registramos. **de Mendonça & Souza (2009)**
   usam a banda de tolerância: IC=1 dentro da banda, decaimento linear até
   20% acima e até 0% abaixo.

2. **Dispersão do Focus** — desvio-padrão entre respondentes (sinal
   invertido: mais dispersão = menos ancoragem). Derivado do Focus, como o
   latente: rival "fraco" por construção.

3. **Dincer-Eichengreen-Geraats** — índice de transparência, anual,
   institucional. Não há API: o arquivo ``dados/macro/deg_brasil.csv`` (colunas
   ``ano,valor``) deve ser preenchido à mão a partir de Dincer, Eichengreen &
   Geraats (2022) e das atualizações do sítio dos autores. Se ausente, o
   rival é pulado com aviso — **não inventamos valores**.

4. **Mercado** — breakeven de inflação (NTN-B vs. prefixados), CDS soberano,
   inclinação da estrutura a termo. Carregados de CSVs em ``dados/mercado/``
   (colunas ``data,valor``, frequência qualquer; agregados para mensal por
   média). Ver ``mercado/README.md`` para a construção recomendada.

Todos os rivais saem em frequência mensal, alinhados ao painel, com
orientação "maior = mais credibilidade" (a dispersão e o CDS entram com
sinal trocado) para que :math:`b_2` tenha leitura direta.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from mercado.bcb import DIR_MACRO, RAIZ

DIR_MERCADO = RAIZ / "dados" / "mercado"
DIR_TERCEIROS = RAIZ / "dados" / "terceiros" / "lista1"


def _rel(caminho: Path) -> str:
    """Caminho relativo à raiz do repositório (avisos e relatórios sem caminho pessoal)."""
    try:
        return Path(caminho).relative_to(RAIZ).as_posix()
    except ValueError:
        return str(caminho)


def de_mendonca_2007(esperada: pd.Series, meta: pd.Series, teto: float = 20.0) -> pd.Series:
    """Índice de de Mendonça (2007), em p.p. (esperada e meta em % a.a.).

    Abaixo da meta usa o desvio absoluto (extensão simétrica; ver docstring
    do módulo). Devolve valores em [0,1].
    """
    e, m = esperada.astype(float), meta.astype(float)
    desvio = (e - m).abs()
    ic = 1.0 - desvio / (teto - m)
    ic = ic.where(~((e >= teto) | (e < 0)), 0.0)
    return ic.clip(lower=0.0, upper=1.0).rename("dm2007")


def de_mendonca_souza_2009(esperada: pd.Series, meta: pd.Series, banda: pd.Series,
                           teto: float = 20.0) -> pd.Series:
    """Variante com banda de tolerância (de Mendonça & Guimarães e Souza, 2009).

    IC = 1 se |E−π*| ≤ banda; acima: 1 − (E − π*_max)/(teto − π*_max);
    abaixo: 1 − (π*_min − E)/π*_min; 0 fora de [0, teto).
    """
    e, m, b = esperada.astype(float), meta.astype(float), banda.astype(float)
    sup, inf = m + b, m - b
    ic = pd.Series(1.0, index=e.index)
    acima = e > sup
    abaixo = e < inf
    ic = ic.where(~acima, 1.0 - (e - sup) / (teto - sup))
    ic = ic.where(~abaixo, 1.0 - (inf - e) / inf.where(inf > 0, np.nan))
    ic = ic.where(~((e >= teto) | (e < 0)), 0.0)
    # Mês sem expectativa, meta ou banda fica sem nota: as comparações acima
    # são falsas com NaN e deixariam o IC inicial de 1 (credibilidade plena).
    ic = ic.where(e.notna() & m.notna() & b.notna())
    return ic.clip(lower=0.0, upper=1.0).rename("dm2009")


def dispersao_focus(disp: pd.Series) -> pd.Series:
    """Dispersão do Focus com sinal trocado (maior = mais ancorado)."""
    return (-disp.astype(float)).rename("disp_focus_neg")


def _ler_serie_csv(caminho: Path) -> pd.Series | None:
    if not caminho.exists():
        return None
    df = pd.read_csv(caminho)
    cols = {c.lower(): c for c in df.columns}
    if "data" not in cols or "valor" not in cols:
        raise ValueError(f"{caminho}: esperado colunas 'data,valor'; achado {list(df.columns)}")
    s = pd.Series(pd.to_numeric(df[cols["valor"]], errors="coerce").to_numpy(),
                  index=pd.to_datetime(df[cols["data"]]))
    return s.dropna().sort_index()


def _mensal(s: pd.Series, nome: str) -> pd.Series:
    m = s.resample("MS").mean()
    m.index = m.index.to_period("M")
    return m.rename(nome)


def deg_transparencia(meses: pd.PeriodIndex, caminho: Path | None = None) -> pd.Series | None:
    """Dincer-Eichengreen-Geraats (anual -> mensal por repetição). ``None`` se o CSV não existir."""
    caminho = caminho or (DIR_MACRO / "deg_brasil.csv")
    if not caminho.exists():
        warnings.warn(f"rival institucional (DEG) pulado: {_rel(caminho)} não existe. "
                      "Preencher com 'ano,valor' a partir de Dincer-Eichengreen-Geraats (2022).")
        return None
    df = pd.read_csv(caminho)
    por_ano = df.set_index("ano")["valor"].astype(float)
    vals = [por_ano.get(p.year, np.nan) for p in meses]
    return pd.Series(vals, index=meses, name="deg")


def serie_mercado(nome: str, meses: pd.PeriodIndex, inverter: bool = False,
                  caminho: Path | None = None) -> pd.Series | None:
    """Rival de mercado em CSV ``data,valor``.

    Séries públicas (breakeven) vêm de ``dados/mercado/`` (versionada); séries
    de fornecedor (CDS, EMBI+) SÓ de ``dados/terceiros/lista1/``, fora do Git,
    para não serem publicadas por engano. A inclinação (DI×Pré 5 anos − 3
    meses) é lida direto das curvas da B3. ``inverter=True`` troca o sinal
    (CDS: mais spread = menos credibilidade). ``None`` (com aviso) se faltar.
    """
    if nome == "inclinacao" and caminho is None:
        return _inclinacao_b3(meses)
    if caminho is None:
        caminho = (DIR_TERCEIROS if nome in SERIES_DE_FORNECEDOR else DIR_MERCADO) / f"{nome}.csv"
    s = _ler_serie_csv(caminho)
    if s is None:
        warnings.warn(f"rival de mercado '{nome}' pulado: {_rel(caminho)} não existe.")
        return None
    m = _mensal(s, nome).reindex(meses)
    return (-m if inverter else m)


SERIES_DE_FORNECEDOR = {"cds", "embi"}


def _inclinacao_b3(meses: pd.PeriodIndex) -> pd.Series | None:
    """Inclinação da curva DI×Pré da B3 (5 anos − 3 meses, p.p.), média mensal.

    Sem sinal esperado a priori: inclinação maior pode ser prêmio de risco
    inflacionário (menos credibilidade) ou expectativa de normalização dos
    juros. Entra como rival não orientado."""
    caminho = DIR_MERCADO / "curvas_b3_diario.csv"
    if not caminho.exists():
        warnings.warn(f"rival 'inclinacao' pulado: {_rel(caminho)} não existe.")
        return None
    d = pd.read_csv(caminho, usecols=["data", "inclinacao_pre_5a_3m"], parse_dates=["data"]).dropna()
    s = pd.Series(d["inclinacao_pre_5a_3m"].to_numpy(), index=d["data"]).sort_index()
    return _mensal(s, "inclinacao").reindex(meses)


def montar_rivais(painel: pd.DataFrame, incluir_mercado: bool = True) -> pd.DataFrame:
    """Todos os rivais disponíveis, alinhados ao índice do painel.

    Colunas sempre presentes: dm2007, dm2009, disp_focus_neg. Condicionais:
    deg, breakeven, cds_neg, inclinacao (só se os arquivos existirem).
    """
    out = pd.DataFrame(index=painel.index)
    out["dm2007"] = de_mendonca_2007(painel["pi_focus"], painel["pi_star"])
    out["dm2009"] = de_mendonca_souza_2009(painel["pi_focus"], painel["pi_star"], painel["banda"])
    out["disp_focus_neg"] = dispersao_focus(painel["disp_focus"])
    deg = deg_transparencia(painel.index)
    if deg is not None:
        out["deg"] = deg
    if incluir_mercado:
        for nome, inverter in (("breakeven", True), ("cds", True), ("embi", True), ("inclinacao", False)):
            s = serie_mercado(nome, painel.index, inverter=inverter)
            if s is not None:
                out[nome + ("_neg" if inverter else "")] = s
    return out


FAMILIA = {
    "dm2007": "Focus (fórmula)", "dm2009": "Focus (fórmula c/ banda)",
    "disp_focus_neg": "Focus (dispersão)", "deg": "institucional",
    "breakeven_neg": "mercado", "cds_neg": "mercado", "embi_neg": "mercado", "inclinacao": "mercado",
}

# -*- coding: utf-8 -*-
"""Bateria anti-vazamento (look-ahead) — testes T2 a T6, mais a escada de
anonimização usada por T0 (`temporal_probe.py`) e T3.

T2 (date-swap): re-pontuar subamostra com data OMITIDA e com data TROCADA
    (±5 anos, refletido para dentro do regime de metas). Vazamento se |Δ|
    for grande E o Δ correlacionar com o desfecho futuro realizado.
T3 (anonimização): mascarar datas do corpo (L1), autoridades do BC (L2),
    políticos (L3) e impressões digitais numéricas — Selic/IPCA/câmbio/PIB
    (L4). Se o escore muda sistematicamente por era ao esconder QUEM é a
    autoridade (ou QUANTO valia o indicador), o modelo usa prior de
    pessoas/eras/níveis, não o texto.
T4 (resíduo preditivo): resíduo do escore LLM (controlando o escore humano)
    não deve prever a surpresa inflacionária FUTURA. Regressão com Newey-West
    na etapa econométrica; aqui, correlação de triagem.
T5 (itens sintéticos): textos fabricados idênticos, "datados" em eras boas e
    ruins. Como cada grupo (texto_grupo) tem o MESMO texto nas duas eras, o
    teste primário é PAREADO por grupo (mais poder que Welch); Welch fica
    como robustez.
T6 (benchmark de cutoff conhecido): série do braço local (BERTimbau, D7)
    vs. série da API. RESTRITO ao pós-2019 (D14): o pré-treino do BERTimbau
    cobre até ~2019, então um item de 2015 tem 2016-2019 como FUTURO em
    relação a ele — o braço local está contaminado nesse recorte tanto
    quanto a API. Concordância entre provedores de API (Sabiá/Gemini/Groq)
    também NÃO valida ausência de vazamento: eles compartilham o mesmo
    conhecimento histórico; testa robustez à troca de modelo, não cegueira
    temporal (ver `comparar_t6`).

Critérios de reprovação (pré-registrados no doc de decisões):
    T2/T3: corr(Δ, desfecho futuro) significativa a 5% com |ρ| >= 0,25;
    T5: diferença média entre eras significativa a 5% (teste pareado).
Reprovou => produção migra para o braço local (encoder de cutoff conhecido).
A regressão de tendência em t (D11/4.2.2) que acompanha T2/T3 NÃO é critério
de reprovação — é diagnóstico auxiliar: se o teste captura vazamento de
verdade, o efeito deve encolher em itens mais recentes (menos futuro
conhecido sob o cutoff do modelo).

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


# ---------------------------------------------------------------------------
# L4 — impressões digitais NUMÉRICAS (D11/4.2.4). "Selic a 14,25%", "dólar a
# R$ 4,10", "IPCA de 10,67%" datam o texto tão bem quanto uma data explícita,
# e L1-L3 não os removia. Mascara só o NÚMERO junto ao indicador — preserva
# palavras de direção ("subiu", "recuou", "em alta"), que são conteúdo de
# percepção, não identificador de época.
# ---------------------------------------------------------------------------

_NUM = r"(?:R\$\s*)?\d{1,3}(?:\.\d{3})*(?:,\d+)?(?:\s*%|\s*pontos?(?:\s*percentuais)?)?"

_RE_NUMERICOS = {
    re.compile(rf"\bselic\b\D{{0,20}}?({_NUM})", re.IGNORECASE): "[SELIC_NIVEL]",
    re.compile(rf"\bipca\b\D{{0,20}}?({_NUM})", re.IGNORECASE): "[IPCA_NIVEL]",
    re.compile(rf"\b(?:d[óo]lar|c[âa]mbio)\b\D{{0,20}}?({_NUM})",
              re.IGNORECASE): "[CAMBIO_NIVEL]",
    re.compile(rf"\b(?:pib|produto interno bruto)\b\D{{0,20}}?({_NUM})",
              re.IGNORECASE): "[PIB_NIVEL]",
}


def _mascarar_numericos(texto: str) -> str:
    """Substitui só o número casado pelo grupo 1, mantendo o indicador e as
    palavras entre ele e o número (ex.: 'Selic subiu para 14,25%' ->
    'Selic subiu para [SELIC_NIVEL]'). Limitação: só cobre número que vem
    DEPOIS do indicador dentro de uma janela curta; "14,25% de alta da
    Selic" escapa (indicador depois do número) — aceito e documentado."""
    t = texto
    for rx, token in _RE_NUMERICOS.items():
        def _sub(m, token=token):
            offset = m.start(1) - m.start(0)
            return m.group(0)[:offset] + token
        t = rx.sub(_sub, t)
    return t


def anonimizar(texto: str, nivel: str) -> str:
    """Escada de anonimização (D11/4.2.4): L1 datas; L2 +autoridades do BC;
    L3 +políticos; L4 +numéricos (Selic/IPCA/câmbio/PIB). Cada nível inclui
    os anteriores. T0 (temporal_probe.py) decide o nível mínimo que cega o
    modelo; esse nível vira o V-min de produção (D12)."""
    cfg = _cfg()["anonimizacao"]
    # NaN (float) é "truthy" em Python — `texto or ""` NÃO pega esse caso e
    # `.sub()` quebra com TypeError. pd.isna cobre None, NaN e NaT.
    t = "" if pd.isna(texto) else str(texto)
    if nivel in ("L1", "L2", "L3", "L4"):
        t = _RE_DATAS.sub("[DATA]", t)
    if nivel in ("L2", "L3", "L4"):
        for nome in sorted(cfg["autoridades_bc"], key=len, reverse=True):
            t = _padrao_nome(nome).sub("[AUTORIDADE_BC]", t)
    if nivel in ("L3", "L4"):
        for nome in sorted(cfg["politicos"], key=len, reverse=True):
            t = _padrao_nome(nome).sub("[POLITICO]", t)
    if nivel == "L4":
        t = _mascarar_numericos(t)
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

def _corr_t_p(x: np.ndarray, y: np.ndarray) -> dict:
    """Correlação de Pearson + t aproximado + p-valor bicaudal. n>=3 exigido
    pelo chamador; graus de liberdade = n-2."""
    n = len(x)
    if x.std(ddof=1) == 0 or y.std(ddof=1) == 0:
        return {"corr": 0.0, "t": 0.0, "p": 1.0, "n": int(n),
                "obs": "sem variação em x ou y"}
    rho = float(np.corrcoef(x, y)[0, 1])
    t = rho * np.sqrt((n - 2) / max(1e-12, 1 - rho ** 2))
    return {"corr": rho, "t": float(t), "p": _p_bicaudal_t(t, n - 2), "n": int(n)}


def comparar_variantes(base: pd.DataFrame, alt: pd.DataFrame,
                       desfecho_futuro: pd.Series | None = None,
                       datas: pd.Series | None = None) -> dict:
    """base/alt: colunas item_id, d1 (mesmos itens, variantes distintas).
    desfecho_futuro: opcional, indexada por item_id (ex.: surpresa de inflação
    12m à frente da data de publicação).
    datas: opcional, indexada por item_id (data_publicacao) — regressão
    auxiliar de tendência em t (D11/4.2.2): o horizonte de vazamento
    h_leak_t = cutoff(modelo) - t é DECRESCENTE em t (item recente tem menos
    futuro conhecido que item antigo). Se o teste está de fato detectando
    look-ahead, o efeito (|delta|) deve encolher com o tempo — reportado
    aqui como diagnóstico auxiliar, não como critério de reprovação."""
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
        if int(ok.sum()) >= 10:
            r = _corr_t_p(delta[ok].to_numpy(float), y[ok].to_numpy(float))
            out.update({"corr_delta_desfecho": r["corr"], "t_aprox": r["t"],
                       "p_delta_desfecho": r.get("p")})
    if datas is not None:
        t_dias = m["item_id"].map(datas)
        t_dias = pd.to_datetime(t_dias, errors="coerce")
        ok = t_dias.notna() & delta.notna()
        if int(ok.sum()) >= 10:
            x = (t_dias[ok] - t_dias[ok].min()).dt.days.to_numpy(float)
            r = _corr_t_p(x, delta[ok].abs().to_numpy(float))
            out.update({
                "tendencia_abs_delta_vs_t_corr": r["corr"],
                "tendencia_abs_delta_vs_t_p": r.get("p"),
                "tendencia_abs_delta_vs_t_n": r["n"],
                "tendencia_esperada": "negativa (efeito encolhe em itens mais "
                                      "recentes, que carregam menos futuro "
                                      "conhecido sob o cutoff do modelo)",
            })
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


# ---------------------------------------------------------------------------
# T6 — braço local (BERTimbau) vs. API, restrito ao pós-2019 (D14)
# ---------------------------------------------------------------------------

CORTE_T6 = pd.Timestamp("2019-01-01")


def comparar_t6(serie_api: pd.DataFrame, serie_local: pd.DataFrame,
                corte: pd.Timestamp = CORTE_T6) -> dict:
    """Compara a série mensal da API com a do braço local (BERTimbau).

    RESTRITO a `corte` (padrão 2019-01-01, D14): antes disso o pré-treino do
    BERTimbau (brWaC, cutoff ~2019) também cobre parte do futuro do item, e o
    contraste deixa de ser informativo sobre vazamento — vira só uma
    diferença de qualidade entre os dois classificadores. Itens de `serie_*`
    anteriores ao corte são descartados, não só ocultos do resumo.

    Espera colunas `mes` (Period ou string 'YYYY-MM') e `c_llm` em cada
    DataFrame. Retorna correlação, diferença média/absoluta e as maiores
    divergências (candidatas a "evento notório" para inspeção manual —
    concentração dessas divergências ao redor de desfechos conhecidos é o
    sinal de vazamento; o número sozinho não decide nada).
    """
    def _corta(df):
        d = df.copy()
        d["mes_ts"] = pd.PeriodIndex(d["mes"].astype(str), freq="M").to_timestamp()
        return d[d["mes_ts"] >= corte]

    a = _corta(serie_api)[["mes", "mes_ts", "c_llm"]]
    l = _corta(serie_local)[["mes", "mes_ts", "c_llm"]]
    m = a.merge(l, on="mes", suffixes=("_api", "_local")).sort_values("mes_ts_api")
    if m.empty:
        return {"n_meses": 0, "obs": f"nenhum mês >= {corte.date()} em comum"}

    dif = (m["c_llm_local"] - m["c_llm_api"]).astype(float)
    corr = (float(np.corrcoef(m["c_llm_api"], m["c_llm_local"])[0, 1])
            if m["c_llm_api"].std(ddof=1) > 0 and m["c_llm_local"].std(ddof=1) > 0
            else float("nan"))
    maiores = (m.assign(dif_abs=dif.abs())
                .nlargest(min(5, len(m)), "dif_abs")[["mes", "dif_abs"]]
                .to_dict("records"))
    return {
        "n_meses": int(len(m)),
        "corte_aplicado": str(corte.date()),
        "corr_api_local": corr,
        "dif_media": float(dif.mean()),
        "dif_abs_media": float(dif.abs().mean()),
        "maiores_divergencias": maiores,
        "nota": ("contraste só informativo pós-corte (D14): pré-2019 o "
                "pré-treino do BERTimbau também cobre o futuro do item"),
    }

# -*- coding: utf-8 -*-
"""Figuras do artigo de medição (PDF vetorial + PNG), num estilo único.

Estilo: cinza primeiro e UMA cor de destaque (azul) no que o título afirma;
cores categóricas só para identidade (veículos, modelos), na ordem fixa da
paleta validada (azul, laranja, água, amarelo, magenta); um eixo por painel;
grade horizontal discreta; legenda sempre que houver mais de uma série.

Uso (da raiz):  python -m validacao.figuras_artigo
Lê as saídas de `python -m validacao.artigo` e as séries de dados/derivados/.
Saída: dados/derivados/validacao/artigo/figuras/ (local).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

from . import construto, eventos  # noqa: E402
from mercado.bcb import RAIZ  # noqa: E402

DERIV = RAIZ / "dados" / "derivados"
ART = DERIV / "validacao" / "artigo"
SAIDA = ART / "figuras"

AZUL, LARANJA, AGUA, AMARELO, MAGENTA = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
CINZA, CINZA_CLARO, GRADE, TINTA, TINTA2 = "#8a8a86", "#d9d8d4", "#e9e8e4", "#1f1f1e", "#5b5a56"
LARGURA = 6.5  # polegadas (largura de texto do artigo)
PRESIDENTES = [("Tombini", "2011-01-01", "2016-06-09"), ("Goldfajn", "2016-06-09", "2019-02-28"),
               ("Campos Neto", "2019-02-28", "2025-01-01"), ("Galípolo", "2025-01-01", "2026-10-01")]


def _estilo() -> None:
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
        "font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 8.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "legend.fontsize": 8, "axes.edgecolor": CINZA, "axes.labelcolor": TINTA2, "xtick.color": TINTA2,
        "ytick.color": TINTA2, "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.titlepad": 8,
        "legend.frameon": False, "savefig.bbox": "tight", "savefig.dpi": 300,
    })


def _br(v: float, casas: int = 1) -> str:
    """Número no padrão brasileiro (vírgula decimal, ponto de milhar, sinal de menos tipográfico)."""
    s = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s.replace("-", "−")


_VIRGULA = matplotlib.ticker.FuncFormatter(
    lambda v, _: (f"{v:.2f}".rstrip("0").rstrip(".") if abs(v - round(v)) > 1e-9 else f"{round(v):d}")
    .replace(".", ",").replace("-", "−"))


def _eixo(ax, grade_y: bool = True, virgula_x: bool = False) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if grade_y:
        ax.grid(axis="y", color=GRADE, lw=0.6)
        ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(_VIRGULA)
    if virgula_x:
        ax.xaxis.set_major_formatter(_VIRGULA)


def _anos(ax) -> None:
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_minor_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(pd.Timestamp("2010-12-01"), pd.Timestamp("2026-10-01"))


def _mandatos(ax, rotulos: bool = True) -> None:
    for i, (nome, a, b) in enumerate(PRESIDENTES):
        a, b = pd.Timestamp(a), pd.Timestamp(b)
        if i % 2 == 1:
            ax.axvspan(a, b, color="#f3f2ee", lw=0, zorder=0)
        if rotulos:
            ax.text(a + (b - a) / 2, 1.005, nome, transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                    fontsize=7.5, color=TINTA2, style="italic")


def _salvar(fig, nome: str) -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    fig.savefig(SAIDA / f"{nome}.pdf")
    fig.savefig(SAIDA / f"{nome}.png", dpi=220)
    plt.close(fig)


def _mes(df: pd.DataFrame, col: str = "mes") -> pd.DatetimeIndex:
    return pd.PeriodIndex(df[col].astype(str), freq="M").to_timestamp() + pd.Timedelta(days=14)


# ── 1. funil do corpus ──────────────────────────────────────────────────────

def fig_funil() -> None:
    c = json.loads((DERIV / "producao_v11_contagens.json").read_text(encoding="utf-8"))
    enviadas = c["rotulagem_api"] + c["filtro_enviadas_api"] + c["filtro_descartadas_auditadas_api"]
    etapas = [("Corpus coletado", c["corpus_total"]), ("Produção (sem a quarentena de 10%)", c["producao"]),
              ("Enviadas ao LLM", enviadas), ("Com sinal sobre a meta (D1)", c["api_com_sinal"])]
    fig, ax = plt.subplots(figsize=(LARGURA, 2.5))
    y = np.arange(len(etapas))[::-1]
    for yi, (nome, n), cor in zip(y, etapas, [CINZA_CLARO, CINZA_CLARO, CINZA_CLARO, AZUL]):
        ax.barh(yi, n, height=0.62, color=cor, edgecolor="none")
        ax.text(n + 600, yi, _br(n, 0), va="center", fontsize=8.5, color=TINTA)
    ax.set_yticks(y, [e for e, _ in etapas])
    ax.set_xlim(0, c["corpus_total"] * 1.12)
    ax.xaxis.set_visible(False)
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    nunca = c["filtro_descartadas_nao_enviadas"]
    ax.annotate(f"{_br(nunca, 0)} nunca enviadas ({_br(100 * c['fracao_producao_nao_enviada'])}% da produção)",
                xy=(enviadas, y[2] + 0.31), xytext=(enviadas + 3000, y[2] + 0.62), fontsize=8, color=TINTA2,
                arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.6))
    ax.text(c["api_com_sinal"] + 6500, y[3], f"sinal perdido pelo filtro, estimado pela auditoria: ≈ "
            f"{_br(c['sinal_perdido_estimado'], 0)} notícias ({_br(100 * c['fracao_sinal_perdido_estimada'])}% do sinal)",
            va="center", fontsize=8, color=TINTA2)
    ax.set_title("Seis em cada dez notícias nunca foram ao LLM; o filtro perde cerca de 4% do sinal")
    _salvar(fig, "fig01_funil_corpus")


# ── 2. cobertura por veículo e ano ──────────────────────────────────────────

def fig_cobertura() -> None:
    corpus = pd.read_parquet(RAIZ / "dados" / "llm" / "corpus.parquet", columns=["veiculo", "data_publicacao"])
    corpus["ano"] = pd.to_datetime(corpus["data_publicacao"], format="mixed").dt.year
    tab = pd.crosstab(corpus["ano"], corpus["veiculo"])
    ordem = ["InfoMoney", "Valor", "Money Times", "Poder360", "O Globo"]
    tab = tab[[v for v in ordem if v in tab]]
    fig, ax = plt.subplots(figsize=(LARGURA, 2.9))
    base = np.zeros(len(tab))
    for v, cor in zip(tab.columns, [AZUL, LARANJA, AGUA, AMARELO, MAGENTA]):
        ax.bar(tab.index, tab[v], bottom=base, width=0.74, color=cor, label=v, edgecolor="white", lw=0.6)
        base += tab[v].to_numpy()
    for x, t in zip(tab.index, base):
        ax.text(x, t + 120, f"{t / 1000:.1f}".replace(".", ","), ha="center", fontsize=7, color=TINTA2)
    ax.set_xticks(tab.index, [str(a) if a % 2 == 1 else "" for a in tab.index])
    ax.set_ylabel("notícias por ano")
    ax.legend(ncol=5, loc="upper left", bbox_to_anchor=(0, -0.1), handlelength=1, columnspacing=1.2)
    _eixo(ax)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f} mil" if v else "0"))
    ax.set_title("Até 2015 o corpus é InfoMoney e Valor; o volume quadruplica até 2023")
    ax.text(1.0, -0.26, "Totais em milhares. 2026 vai até 1º de setembro.", transform=ax.transAxes, ha="right",
            fontsize=7, color=TINTA2)
    _salvar(fig, "fig02_cobertura_veiculos")


# ── 3. o índice ─────────────────────────────────────────────────────────────

def fig_indice() -> None:
    m = pd.read_csv(DERIV / "indice_mensal_v11_sabia.csv")
    j = pd.read_csv(DERIV / "indice_mensal_v11_sabia_jm3.csv")
    metas = pd.read_csv(RAIZ / "dados" / "macro" / "metas_inflacao_historico.csv")
    fig, ax = plt.subplots(figsize=(LARGURA, 3.0))
    _mandatos(ax)
    xj = _mes(j)
    ax.fill_between(xj, j["c_llm"] - 1.96 * j["ep"], j["c_llm"] + 1.96 * j["ep"], color=AZUL, alpha=0.15, lw=0,
                    label="IC 95% (janela de 3 meses)")
    ax.plot(_mes(m), m["c_llm"], color=CINZA, lw=0.7, alpha=0.8, label="mensal")
    ax.plot(xj, j["c_llm"], color=AZUL, lw=1.6, label="janela móvel de 3 meses")
    for _, r in metas[(metas["ano"] >= 2011) & (metas["ano"] <= 2025) & (metas["cumpriu"] == False)].iterrows():  # noqa: E712
        ax.axvspan(pd.Timestamp(f"{int(r['ano'])}-01-01"), pd.Timestamp(f"{int(r['ano'])}-12-31"), ymin=0, ymax=0.035,
                   color=TINTA, lw=0)
    ax.text(pd.Timestamp("2011-02-01"), 0.045, "▬ ano com meta descumprida", fontsize=7, color=TINTA2)
    ax.axhline(0.5, color=CINZA, lw=0.6, ls=":")
    ax.set_ylim(0, 1)
    ax.set_ylabel(r"$\hat{C}^{LLM}$ (0 = descumprimento certo; 1 = meta certa)")
    _anos(ax)
    _eixo(ax)
    ax.legend(loc="upper left", ncol=3, bbox_to_anchor=(0, -0.08))
    ax.set_title("Credibilidade percebida da meta, 2011–2026", pad=16)
    _salvar(fig, "fig03_indice")


# ── 4. D1, D2, D3 ───────────────────────────────────────────────────────────

def fig_dimensoes() -> None:
    s = pd.read_csv(DERIV / "indice_dimensoes_v11_sabia_trimestral.csv")
    g = pd.read_csv(DERIV / "indice_dimensoes_v11_gemini_flash_lite_trimestral.csv")
    x = pd.PeriodIndex(s["periodo"], freq="Q").to_timestamp() + pd.Timedelta(days=45)
    xg = pd.PeriodIndex(g["periodo"], freq="Q").to_timestamp() + pd.Timedelta(days=45)
    titulos = {"d1": "D1 — probabilidade de cumprimento da meta (o índice)",
               "d2": "D2 — confiança na condução da política", "d3": "D3 — autonomia percebida do BCB"}
    fig, axs = plt.subplots(3, 1, figsize=(LARGURA, 6.4), sharex=True, gridspec_kw={"hspace": 0.38})
    for ax, k in zip(axs, titulos):
        col = "d1" if k == "d1" else f"{k}_ipw"
        _mandatos(ax, rotulos=(k == "d1"))
        ax.fill_between(x, s[col] - 1.96 * s[f"{col}_ep"], s[col] + 1.96 * s[f"{col}_ep"], color=AZUL, alpha=0.15, lw=0)
        ax.plot(x, s[col], color=AZUL, lw=1.5, label="Sabiá (produção)")
        ax.plot(xg, g[col], color=LARANJA, lw=1.0, ls="--", label="Gemini (robustez)")
        ax.axhline(0.5, color=CINZA, lw=0.6, ls=":")
        ax.set_ylim(0.2, 0.9)
        ax.set_title(titulos[k], pad=14 if k == "d1" else 6)
        _eixo(ax)
    _anos(axs[-1])
    axs[0].legend(loc="lower left", ncol=2)
    fig.text(0.01, 0.005, "Trimestral; faixa = IC 95% (Sabiá). D2 e D3 ponderadas pelo desenho do pré-filtro.",
             fontsize=7, color=TINTA2)
    _salvar(fig, "fig04_dimensoes")


# ── 5. robustez da construção ───────────────────────────────────────────────

def fig_robustez() -> None:
    rob = pd.read_csv(DERIV / "robustez_indice_v11.csv")
    p = pd.read_csv(ART / "painel_construto.csv")
    v10 = pd.read_csv(DERIV / "indice_mensal.csv")[["mes", "c_llm"]].rename(columns={"c_llm": "v10"})
    v11 = pd.read_csv(DERIV / "indice_mensal_v11_sabia.csv")[["mes", "c_llm"]].merge(v10, on="mes").dropna()
    extra = pd.DataFrame([
        {"versao": "gemini", "agregacao": "mensal", "corr": p["c_llm"].corr(p["c_llm_gemini"])},
        {"versao": "gemini", "agregacao": "jm3", "corr": p["c_llm_jm3"].corr(p["c_llm_gemjm3"])},
        {"versao": "prompt_v10", "agregacao": "mensal", "corr": v11["c_llm"].corr(v11["v10"])}])
    t = pd.concat([rob[["versao", "agregacao", "corr"]], extra], ignore_index=True)
    nomes = {"gemini": "Outro modelo (Gemini)", "fe_veiculo": "Efeito fixo por veículo",
             "constante": "Só veículos da série inteira", "so_infomoney": "Só InfoMoney", "so_valor": "Só Valor",
             "amostra_aleatoria": "Só a amostra aleatória (sem filtro)", "prompt_v10": "Prompt v1.0"}
    ordem = list(nomes)
    fig, ax = plt.subplots(figsize=(LARGURA, 2.9))
    for i, v in enumerate(ordem[::-1]):
        for ag, mk, cor in (("mensal", "o", CINZA), ("jm3", "o", AZUL)):
            r = t[(t["versao"] == v) & (t["agregacao"] == ag)]
            if len(r):
                ax.plot(r["corr"], [i], mk, color=cor, ms=6, mfc=cor if ag == "jm3" else "white", mew=1.2,
                        label={"mensal": "mensal", "jm3": "janela de 3 meses"}[ag] if i == 0 or v == "gemini" else None)
    h, lab = ax.get_legend_handles_labels()
    uniq = dict(zip(lab, h))
    ax.legend(uniq.values(), uniq.keys(), loc="lower left")
    ax.set_yticks(range(len(ordem)), [nomes[v] for v in ordem[::-1]])
    ax.set_xlim(0.75, 1.0)
    ax.xaxis.set_major_formatter(_VIRGULA)
    ax.set_xlabel("correlação com o índice principal")
    ax.grid(axis="x", color=GRADE, lw=0.6)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.set_title("O índice muda pouco com o modelo, os veículos, o filtro ou o prompt")
    _salvar(fig, "fig05_robustez")


# ── 6. bateria anti-vazamento ───────────────────────────────────────────────

def fig_vazamento() -> None:
    r = json.loads((RAIZ / "dados" / "llm" / "bateria_v11" / "relatorio_sabia.json").read_text(encoding="utf-8"))
    testes = [("T2", "omitida", "Data omitida"), ("T2", "trocada", "Data trocada (±5 anos)"),
              ("T3", "L1", "Sem datas (L1)"), ("T3", "L2", "+ sem autoridades do BC (L2)"),
              ("T3", "L3", "+ sem políticos (L3)"), ("T3", "L4", "+ sem níveis numéricos (L4)")]
    fig, ax = plt.subplots(figsize=(LARGURA, 2.8))
    lim = r["criterios"]["rho_min"]
    ax.axvspan(lim, 0.7, color="#fbe9e2", lw=0)
    ax.axvspan(-0.7, -lim, color="#fbe9e2", lw=0)
    ax.axvline(0, color=CINZA, lw=0.6)
    for i, (t, k, nome) in enumerate(testes[::-1]):
        d = r[t][k]
        rho, n = d["corr_delta_desfecho"], d["n"]
        z, se = np.arctanh(rho), 1 / np.sqrt(n - 3)
        lo, hi = np.tanh(z - 1.96 * se), np.tanh(z + 1.96 * se)
        ax.plot([lo, hi], [i, i], color=AZUL, lw=1.2)
        ax.plot(rho, i, "o", color=AZUL, ms=5)
        ax.text(0.68, i, f"nota mudou em {_br(100 * d['pct_mudou'])}%", va="center", ha="right", fontsize=7.5,
                color=TINTA2)
    ax.set_yticks(range(len(testes)), [n for _, _, n in testes[::-1]])
    ax.set_xlim(-0.45, 0.7)
    ax.set_ylim(-1.1, len(testes) - 0.5)
    ax.xaxis.set_major_formatter(_VIRGULA)
    ax.set_xlabel("correlação entre a mudança da nota e a surpresa inflacionária futura (IC 95%)")
    ax.text(lim + 0.015, -0.8, "zona de reprovação (|ρ| ≥ 0,25)", fontsize=7.5, color="#b0482a")
    ax.tick_params(axis="y", length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_title("Esconder a data ou os nomes quase não muda a nota, e o que muda não antecipa o futuro")
    fig.text(0.01, -0.1, "Bateria v1.1, Sabiá, 150 notícias estratificadas por episódio. "
             "T3-L4 é significativo a 5%, mas apoiado em 2 notícias e abaixo do limite do critério.",
             fontsize=7, color=TINTA2)
    _salvar(fig, "fig06_vazamento")


# ── 7. convergência ─────────────────────────────────────────────────────────

def _z(s):
    return (s - s.mean()) / s.std()


def fig_convergencia() -> None:
    p = pd.read_csv(ART / "painel_construto.csv")
    p = p[p["c_llm_jm3"].notna()]
    x = _mes(p)
    alvos = [("foc_gap_neg", "Focus: distância à meta (sinal invertido)"),
             ("breakeven_neg", "Inflação implícita de 5 anos (sinal invertido)"),
             ("c_kf_suavizado", "Latente do filtro de Kalman (ancoragem)")]
    fig, axs = plt.subplots(3, 1, figsize=(LARGURA, 5.6), sharex=True, gridspec_kw={"hspace": 0.42})
    for ax, (col, nome) in zip(axs, alvos):
        ok = p[["c_llm_jm3", col]].dropna()
        ax.plot(x, _z(p["c_llm_jm3"]), color=AZUL, lw=1.4)
        ax.plot(x, _z(p[col]), color=CINZA, lw=1.1)
        ax.axhline(0, color=CINZA, lw=0.5, ls=":")
        ax.set_title(f"{nome} · correlação {_br(ok['c_llm_jm3'].corr(ok[col]), 2)}", fontsize=8.5)
        ax.set_ylabel("desvios-padrão")
        _eixo(ax)
    _anos(axs[-1])
    fig.suptitle("O índice acompanha expectativas e preços; o latente do Kalman mede outra coisa",
                 x=0.01, ha="left", fontsize=9.5, fontweight="bold", y=0.995)
    fig.legend([matplotlib.lines.Line2D([], [], color=AZUL, lw=1.4), matplotlib.lines.Line2D([], [], color=CINZA, lw=1.1)],
               ["índice (janela de 3 meses)", "medida do painel"], loc="upper left", bbox_to_anchor=(0.01, 0.965), ncol=2)
    fig.text(0.01, 0.005, "Séries padronizadas. Em 2021, a meta estourou (o índice cai) com expectativas ancoradas "
             "(o latente sobe).", fontsize=7, color=TINTA2)
    _salvar(fig, "fig07_convergencia")


# ── 8. o índice além da inflação ────────────────────────────────────────────

def fig_alem_inflacao() -> None:
    p = pd.read_csv(ART / "painel_construto.csv")
    d = p.dropna(subset=["c_llm_jm3", *construto.CONTROLES_INFLACAO]).copy()
    res = sm.OLS(d["c_llm_jm3"], sm.add_constant(d[list(construto.CONTROLES_INFLACAO)])).fit()
    d["ajuste"] = res.fittedvalues
    x = _mes(d)
    fig, ax = plt.subplots(figsize=(LARGURA, 2.9))
    _mandatos(ax)
    ax.fill_between(x, d["ajuste"], d["c_llm_jm3"], color=AZUL, alpha=0.12, lw=0)
    ax.plot(x, d["ajuste"], color=CINZA, lw=1.1, label="previsto só pela inflação corrente")
    ax.plot(x, d["c_llm_jm3"], color=AZUL, lw=1.5, label="índice (janela de 3 meses)")
    ax.set_ylim(0.15, 0.95)
    ax.set_ylabel(r"$\hat{C}^{LLM}$")
    _anos(ax)
    _eixo(ax)
    ax.legend(loc="upper left", ncol=2, bbox_to_anchor=(0, -0.09))
    ax.set_title(f"A inflação corrente explica {100 * res.rsquared:.0f}% do índice; a área sombreada vem do texto",
                 pad=16)
    fig.text(0.01, -0.1, "Inflação corrente = desvio do IPCA 12 meses à meta, sua variação em 12 meses e "
             "indicador de IPCA acima do teto. Índice em janela de 3 meses.", fontsize=7, color=TINTA2)
    _salvar(fig, "fig08_alem_da_inflacao")


# ── 9. capacidade preditiva ─────────────────────────────────────────────────

def fig_preditiva() -> None:
    t = pd.read_csv(ART / "preditiva.csv")
    alvos = [("foc_gap_neg", "Focus (distância à meta)"), ("breakeven_neg", "Implícita de 5 anos"),
             ("embi_neg", "Risco-país (EMBI+)")]
    series = [("c_llm", "Sabiá mensal", CINZA, -0.18), ("c_llm_jm3", "Sabiá janela de 3 meses", AZUL, 0.0),
              ("c_llm_gemjm3", "Gemini janela de 3 meses", LARANJA, 0.18)]
    fig, axs = plt.subplots(1, 3, figsize=(LARGURA, 2.6))
    for ax, (alvo, nome) in zip(axs, alvos):
        ax.axhline(0, color=CINZA, lw=0.6)
        for col, rot, cor, desl in series:
            r = t[(t["indice"] == col) & (t["alvo"] == alvo)]
            ax.errorbar(r["h"] + desl, r["b"], yerr=1.96 * r["ep_hac"], fmt="o", ms=4, color=cor, capsize=0,
                        elinewidth=1.1, label=rot)
        ax.set_xticks([1, 3, 6])
        ax.set_xlabel("horizonte (meses)")
        ax.set_title(nome, fontsize=8.5)
        _eixo(ax)
    axs[0].set_ylabel("efeito de 1 dp do índice\n(unidades da âncora)")
    axs[0].legend(loc="upper left", fontsize=7)
    fig.suptitle("Poder preditivo do índice a 1, 3 e 6 meses, além da própria história de cada alvo",
                 x=0.01, ha="left", fontsize=9.5, fontweight="bold", y=1.04)
    fig.text(0.01, -0.06, "Controla pelo nível e pela variação da âncora e pelo desvio da inflação à meta; "
             "IC 95% Newey–West. Teste primário: Focus, h = 6.", fontsize=7, color=TINTA2)
    fig.tight_layout()
    _salvar(fig, "fig09_preditiva")


# ── 10. Copom ───────────────────────────────────────────────────────────────

def fig_copom() -> None:
    fig, axs = plt.subplots(1, 2, figsize=(LARGURA, 2.7), sharey=True)
    for ax, (arq, nome) in zip(axs, (("copom_d1_7d.csv", "7 dias (teste primário)"), ("copom_d1_14d.csv", "14 dias"))):
        t = pd.read_csv(ART / arq).dropna(subset=["delta", "surpresa_bps"])
        m = sm.OLS(t["delta"], sm.add_constant(t["surpresa_bps"])).fit(cov_type="HC1")
        xs = np.linspace(t["surpresa_bps"].min(), t["surpresa_bps"].max(), 50)
        pr = m.get_prediction(sm.add_constant(xs)).summary_frame(alpha=0.05)
        ax.axhline(0, color=CINZA, lw=0.5); ax.axvline(0, color=CINZA, lw=0.5)
        ax.scatter(t["surpresa_bps"], t["delta"], s=10, color=CINZA, alpha=0.7, lw=0)
        ax.fill_between(xs, pr["mean_ci_lower"], pr["mean_ci_upper"], color=AZUL, alpha=0.15, lw=0)
        ax.plot(xs, pr["mean"], color=AZUL, lw=1.4)
        b = 10 * m.params["surpresa_bps"]
        ax.set_title(f"{nome}\n{'+' if b > 0 else ''}{_br(b, 3)} por 10 bps · p = {_br(m.pvalues['surpresa_bps'], 2)} · "
                     f"{int(m.nobs)} reuniões", fontsize=8.5, linespacing=1.4)
        ax.set_xlabel("surpresa do Copom, swap DI×Pré 3m (bps)")
        _eixo(ax)
    axs[0].set_ylabel("Δ do índice: depois − antes")
    fig.suptitle("Variação do índice em torno das reuniões do Copom contra a surpresa do swap",
                 x=0.01, ha="left", fontsize=9.5, fontweight="bold", y=1.03)
    fig.tight_layout()
    _salvar(fig, "fig10_copom")


# ── 11. eventos institucionais contra o placebo ─────────────────────────────

def fig_institucionais() -> None:
    it = eventos.itens("sabia")
    k = 30
    rotulos = {"2016-05-17": "mai/2016 · Goldfajn e PEC da autonomia técnica",
               "2020-11-03": "nov/2020 · Senado aprova a autonomia",
               "2021-02-10": "fev/2021 · Câmara aprova a autonomia",
               "2023-01-18": "jan/2023 · Presidente critica a autonomia",
               "2024-05-08": "mai/2024 · Copom dividido (5 a 4)",
               "2024-12-11": "dez/2024 · alta de 1 ponto e sinalização"}
    dims = [("d1", False, "D1 · meta"), ("d2", True, "D2 · condução"), ("d3", True, "D3 · autonomia")]
    fig, axs = plt.subplots(1, 3, figsize=(LARGURA, 3.0), sharey=True)
    for ax, (dim, pond, nome) in zip(axs, dims):
        tab = eventos.diarios(it, dim, pond)
        datas = pd.date_range(tab.index.min() + pd.Timedelta(days=k + 1), tab.index.max() - pd.Timedelta(days=k + 1), freq="7D")
        plac = np.array([eventos.delta(tab, d, k)["delta"] for d in datas])
        plac = plac[np.isfinite(plac)]
        lo, hi = np.percentile(plac, [5, 95])
        ax.axvspan(lo, hi, color="#eeede9", lw=0)
        ax.axvline(0, color=CINZA, lw=0.5)
        for i, data in enumerate(list(rotulos)[::-1]):
            dlt = eventos.delta(tab, data, k)["delta"]
            fora = dlt < lo or dlt > hi
            ax.plot(dlt, i, "o", ms=6, color=AZUL if fora else "white", mec=AZUL if fora else CINZA, mew=1.2)
        ax.set_title(nome, fontsize=8.5)
        ax.set_xlabel("Δ em 30 dias")
        ax.set_xlim(-0.25, 0.25)
        ax.xaxis.set_major_formatter(_VIRGULA)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axs[0].set_yticks(range(len(rotulos)), list(rotulos.values())[::-1])
    fig.suptitle("Variação de D1, D2 e D3 em eventos institucionais contra a faixa do placebo",
                 x=0.01, ha="left", fontsize=9.5, fontweight="bold", y=1.02)
    fig.text(0.01, -0.04, "Faixa cinza: 90% central das variações em todas as datas da amostra (placebo). "
             "Ponto cheio: fora da faixa. Exploratório: datas escolhidas depois de ver a série.",
             fontsize=7, color=TINTA2)
    fig.tight_layout()
    _salvar(fig, "fig11_eventos_institucionais")


# ── A1. prompt v1.0 × v1.1 ──────────────────────────────────────────────────

def fig_versoes_prompt() -> None:
    v10 = pd.read_csv(DERIV / "indice_mensal.csv")
    v11 = pd.read_csv(DERIV / "indice_mensal_v11_sabia.csv")
    fig, ax = plt.subplots(figsize=(LARGURA, 2.6))
    _mandatos(ax)
    ax.plot(_mes(v10), v10["c_llm"], color=CINZA, lw=1.1, label="v1.0 (nota 3 = neutro ou sem sinal)")
    ax.plot(_mes(v11), v11["c_llm"], color=AZUL, lw=1.1, label="v1.1 (sem sinal fora da média)")
    ax.axhline(0.5, color=CINZA, lw=0.6, ls=":")
    ax.set_ylim(0, 1)
    ax.set_ylabel(r"$\hat{C}^{LLM}$ mensal")
    _anos(ax)
    _eixo(ax)
    ax.legend(loc="lower left", ncol=2, bbox_to_anchor=(0, -0.3))
    j = v10[["mes", "c_llm"]].merge(v11[["mes", "c_llm"]], on="mes", suffixes=("_10", "_11")).dropna()
    ax.set_title(f"Separar ‘sem sinal’ de ‘equilibrado’ amplia a escala e preserva a dinâmica "
                 f"(correlação {_br(j['c_llm_10'].corr(j['c_llm_11']), 2)})", pad=16)
    _salvar(fig, "figA1_versoes_prompt")


FIGURAS = [fig_funil, fig_cobertura, fig_indice, fig_dimensoes, fig_robustez, fig_vazamento, fig_convergencia,
           fig_alem_inflacao, fig_preditiva, fig_copom, fig_institucionais, fig_versoes_prompt]


def main() -> None:
    _estilo()
    for f in FIGURAS:
        f()
        print("ok", f.__name__)


if __name__ == "__main__":
    main()

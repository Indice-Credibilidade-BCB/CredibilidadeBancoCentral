# -*- coding: utf-8 -*-
"""Figuras do artigo em inglês ("Stick to the news"), numeradas como no texto.

Mesmo estilo e mesmos dados de ``figuras_artigo.py``, com rótulos em inglês,
ponto decimal e SEM título interno: no padrão ABNT o título vai na legenda do
documento, acima da figura, e a fonte embaixo.

Uso (da raiz):  python -m validacao.figuras_paper
Saída: dados/derivados/validacao/artigo/figuras_paper/ (PDF vetorial + PNG 300 dpi).
"""
from __future__ import annotations

import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import statsmodels.api as sm  # noqa: E402

from . import construto, eventos  # noqa: E402
from .figuras_artigo import (AGUA, AMARELO, ART, AZUL, CINZA, CINZA_CLARO, DERIV, GRADE, LARANJA, LARGURA,  # noqa: E402
                             MAGENTA, RAIZ, TINTA, TINTA2, _anos, _estilo, _mandatos, _mes, _z)

SAIDA = ART / "figuras_paper"

_PONTO = matplotlib.ticker.FuncFormatter(
    lambda v, _: (f"{v:.2f}".rstrip("0").rstrip(".") if abs(v - round(v)) > 1e-9 else f"{round(v):d}")
    .replace("-", "−"))


def _n(v: float, casas: int = 1) -> str:
    return f"{v:,.{casas}f}".replace("-", "−")


def _eixo(ax, grade_y: bool = True) -> None:
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if grade_y:
        ax.grid(axis="y", color=GRADE, lw=0.6)
        ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(_PONTO)


def _salvar(fig, nome: str) -> None:
    SAIDA.mkdir(parents=True, exist_ok=True)
    fig.savefig(SAIDA / f"{nome}.pdf")
    fig.savefig(SAIDA / f"{nome}.png", dpi=300)
    plt.close(fig)


# ── Figure 1: corpus by outlet and year (Section 3) ─────────────────────────

def fig1_coverage() -> None:
    corpus = pd.read_parquet(RAIZ / "dados" / "llm" / "corpus.parquet", columns=["veiculo", "data_publicacao"])
    corpus["ano"] = pd.to_datetime(corpus["data_publicacao"], format="mixed").dt.year
    tab = pd.crosstab(corpus["veiculo"], corpus["ano"])
    tab = tab.loc[tab.sum(axis=1).sort_values(ascending=False).index]
    anos = tab.columns.to_numpy()
    grandes, outros = list(tab.index[:5]), list(tab.index[5:])
    fig = plt.figure(figsize=(LARGURA, 6.0))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.05], hspace=0.10)
    ax = fig.add_subplot(gs[0])
    xs = np.arange(len(anos)) + 0.5
    base = np.zeros(len(anos))
    for v, cor in zip(grandes, [AZUL, LARANJA, AGUA, AMARELO, MAGENTA]):
        ax.bar(xs, tab.loc[v], bottom=base, width=0.78, color=cor, label=v, edgecolor="white", lw=0.6)
        base += tab.loc[v].to_numpy()
    resto = tab.loc[outros].sum()
    ax.bar(xs, resto, bottom=base, width=0.78, color=CINZA_CLARO, edgecolor="white", lw=0.6,
           label=f"other {len(outros)} outlets")
    base += resto.to_numpy()
    for x, tot in zip(xs, base):
        ax.text(x, tot + base.max() * 0.012, f"{tot / 1000:.1f}", ha="center", fontsize=7, color=TINTA2)
    ax.set_xlim(0, len(anos) + 1)
    ax.set_xticks([])
    ax.set_ylabel("articles per year")
    ax.legend(ncol=3, loc="upper left", handlelength=1, columnspacing=1.2, fontsize=7.5)
    _eixo(ax)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1000:.0f}k" if v else "0"))
    ax.set_ylim(0, base.max() * 1.22)
    tb = fig.add_subplot(gs[1])
    linhas = list(tab.index) + ["Total"]
    cols = [str(a) for a in anos] + ["Total"]
    m = np.vstack([np.c_[tab.to_numpy(), tab.sum(axis=1).to_numpy()], np.r_[tab.sum().to_numpy(), tab.to_numpy().sum()]])
    escala = matplotlib.colors.LinearSegmentedColormap.from_list("azul", ["#ffffff", "#cfe0f6", AZUL])
    vmax = tab.to_numpy().max()
    for i in range(len(linhas)):
        for j in range(len(cols)):
            v = int(m[i, j])
            total = i == len(linhas) - 1 or j == len(cols) - 1
            fundo = "#f1f0ec" if total else escala(min(v / vmax, 1.0) ** 0.6)
            tb.add_patch(matplotlib.patches.Rectangle((j, i), 1, 1, facecolor=fundo, edgecolor="white", lw=1.2))
            escuro = (not total) and v / vmax > 0.45
            tb.text(j + 0.5, i + 0.5, "" if v == 0 else f"{v:,}", ha="center", va="center",
                    fontsize=5.6 if j < len(anos) else 6, color="white" if escuro else TINTA,
                    fontweight="bold" if total else "normal")
    tb.set_xlim(0, len(cols)); tb.set_ylim(len(linhas), 0)
    tb.set_xticks(np.arange(len(cols)) + 0.5, cols, fontsize=6.5)
    tb.xaxis.tick_top()
    tb.set_yticks(np.arange(len(linhas)) + 0.5, linhas, fontsize=7)
    tb.get_yticklabels()[-1].set_fontweight("bold")
    tb.tick_params(length=0)
    for s in tb.spines.values():
        s.set_visible(False)
    _salvar(fig, "fig01_corpus_by_outlet")


# ── Figure 2: from the corpus to the articles with a signal ─────────────────

def fig2_funnel() -> None:
    c = json.loads((DERIV / "producao_v11_contagens.json").read_text(encoding="utf-8"))
    enviadas = c["rotulagem_api"] + c["filtro_enviadas_api"] + c["filtro_descartadas_auditadas_api"]
    etapas = [("Corpus", c["corpus_total"]), ("Production (10% quarantine excluded)", c["producao"]),
              ("Sent to the model", enviadas), ("With a signal on the target (D1)", c["api_com_sinal"])]
    fig, ax = plt.subplots(figsize=(LARGURA, 2.3))
    y = np.arange(len(etapas))[::-1]
    for yi, (_, n), cor in zip(y, etapas, [CINZA_CLARO, CINZA_CLARO, CINZA_CLARO, AZUL]):
        ax.barh(yi, n, height=0.62, color=cor, edgecolor="none")
        ax.text(n + 600, yi, f"{n:,}", va="center", fontsize=8.5, color=TINTA)
    ax.set_yticks(y, [e for e, _ in etapas])
    ax.set_xlim(0, c["corpus_total"] * 1.12)
    ax.xaxis.set_visible(False)
    for s in ("top", "right", "bottom"):
        ax.spines[s].set_visible(False)
    ax.annotate(f"{c['filtro_descartadas_nao_enviadas']:,} never sent ({100 * c['fracao_producao_nao_enviada']:.1f}% "
                "of production)", xy=(enviadas, y[2] + 0.31), xytext=(enviadas + 3000, y[2] + 0.62), fontsize=8,
                color=TINTA2, arrowprops=dict(arrowstyle="-", color=CINZA, lw=0.6))
    ax.text(c["api_com_sinal"] + 6500, y[3], f"signal lost by the filter, estimated by the audit: ≈ "
            f"{c['sinal_perdido_estimado']:,.0f} articles ({100 * c['fracao_sinal_perdido_estimada']:.1f}% of the signal)",
            va="center", fontsize=8, color=TINTA2)
    _salvar(fig, "fig02_funnel")


# ── Figure 3: the index ─────────────────────────────────────────────────────

def fig3_index() -> None:
    m = pd.read_csv(DERIV / "indice_mensal_v11_sabia.csv")
    j = pd.read_csv(DERIV / "indice_mensal_v11_sabia_jm3.csv")
    metas = pd.read_csv(RAIZ / "dados" / "macro" / "metas_inflacao_historico.csv")
    fig, ax = plt.subplots(figsize=(LARGURA, 3.0))
    _mandatos(ax)
    xj = _mes(j)
    ax.fill_between(xj, j["c_llm"] - 1.96 * j["ep"], j["c_llm"] + 1.96 * j["ep"], color=AZUL, alpha=0.15, lw=0,
                    label="95% CI (three-month window)")
    ax.plot(_mes(m), m["c_llm"], color=CINZA, lw=0.7, alpha=0.8, label="monthly")
    ax.plot(xj, j["c_llm"], color=AZUL, lw=1.6, label="three-month window")
    for _, r in metas[(metas["ano"] >= 2011) & (metas["ano"] <= 2025) & (metas["cumpriu"] == False)].iterrows():  # noqa: E712
        ax.axvspan(pd.Timestamp(f"{int(r['ano'])}-01-01"), pd.Timestamp(f"{int(r['ano'])}-12-31"), ymin=0, ymax=0.035,
                   color=TINTA, lw=0)
    ax.text(pd.Timestamp("2011-02-01"), 0.045, "▬ target missed", fontsize=7, color=TINTA2)
    ax.axhline(0.5, color=CINZA, lw=0.6, ls=":")
    ax.set_ylim(0, 1)
    ax.set_ylabel(r"$\hat{C}^{LLM}$ (0 = target surely missed; 1 = surely met)", fontsize=7.5)
    _anos(ax)
    _eixo(ax)
    ax.legend(loc="upper left", ncol=3, bbox_to_anchor=(0, -0.08))
    _salvar(fig, "fig03_index")


# ── Figure 4: D1, D2, D3 by model ───────────────────────────────────────────

def fig4_dimensions() -> None:
    s = pd.read_csv(DERIV / "indice_dimensoes_v11_sabia_trimestral.csv")
    g = pd.read_csv(DERIV / "indice_dimensoes_v11_gemini_flash_lite_trimestral.csv")
    x = pd.PeriodIndex(s["periodo"], freq="Q").to_timestamp() + pd.Timedelta(days=45)
    xg = pd.PeriodIndex(g["periodo"], freq="Q").to_timestamp() + pd.Timedelta(days=45)
    titulos = {"d1": "D1 — probability that the target is met (the index)",
               "d2": "D2 — confidence in the conduct of policy", "d3": "D3 — perceived autonomy of the BCB"}
    fig, axs = plt.subplots(3, 1, figsize=(LARGURA, 6.2), sharex=True, gridspec_kw={"hspace": 0.38})
    for ax, k in zip(axs, titulos):
        col = "d1" if k == "d1" else f"{k}_ipw"
        _mandatos(ax, rotulos=(k == "d1"))
        ax.fill_between(x, s[col] - 1.96 * s[f"{col}_ep"], s[col] + 1.96 * s[f"{col}_ep"], color=AZUL, alpha=0.15, lw=0)
        ax.plot(x, s[col], color=AZUL, lw=1.5, label="Sabiá (production)")
        ax.plot(xg, g[col], color=LARANJA, lw=1.0, ls="--", label="Gemini (robustness)")
        ax.axhline(0.5, color=CINZA, lw=0.6, ls=":")
        ax.set_ylim(0.2, 0.9)
        ax.set_title(titulos[k], pad=14 if k == "d1" else 6, fontsize=8.5)
        _eixo(ax)
    _anos(axs[-1])
    axs[0].legend(loc="lower left", ncol=2)
    _salvar(fig, "fig04_dimensions")


# ── Figure 5: T2 and T3 ─────────────────────────────────────────────────────

def fig5_leakage_tests() -> None:
    r = json.loads((RAIZ / "dados" / "llm" / "bateria_v11" / "relatorio_sabia.json").read_text(encoding="utf-8"))
    testes = [("T2", "omitida", "Date omitted"), ("T2", "trocada", "Date shifted (±5 years)"),
              ("T3", "L1", "No dates (L1)"), ("T3", "L2", "+ no BCB officials (L2)"),
              ("T3", "L3", "+ no politicians (L3)"), ("T3", "L4", "+ no numeric levels (L4)")]
    fig, ax = plt.subplots(figsize=(LARGURA, 2.7))
    lim = r["criterios"]["rho_min"]
    ax.axvspan(lim, 0.7, color="#fbe9e2", lw=0)
    ax.axvspan(-0.7, -lim, color="#fbe9e2", lw=0)
    ax.axvline(0, color=CINZA, lw=0.6)
    for i, (t, k, _) in enumerate(testes[::-1]):
        d = r[t][k]
        rho, n = d["corr_delta_desfecho"], d["n"]
        z, se = np.arctanh(rho), 1 / np.sqrt(n - 3)
        ax.plot([np.tanh(z - 1.96 * se), np.tanh(z + 1.96 * se)], [i, i], color=AZUL, lw=1.2)
        ax.plot(rho, i, "o", color=AZUL, ms=5)
        ax.text(0.68, i, f"score changed in {100 * d['pct_mudou']:.1f}%", va="center", ha="right", fontsize=7.5,
                color=TINTA2)
    ax.set_yticks(range(len(testes)), [n for _, _, n in testes[::-1]])
    ax.set_xlim(-0.45, 0.7)
    ax.set_ylim(-1.1, len(testes) - 0.5)
    ax.xaxis.set_major_formatter(_PONTO)
    ax.set_xlabel("correlation between the change in score and the future inflation surprise (95% CI)")
    ax.text(lim + 0.015, -0.8, f"rejection zone (|ρ| ≥ {lim})", fontsize=7.5, color="#b0482a")
    ax.tick_params(axis="y", length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    _salvar(fig, "fig05_leakage_tests")


# ── Figure 6: V-max and V-min ───────────────────────────────────────────────

def fig6_vmax_vmin() -> None:
    d = pd.read_csv(DERIV / "indice_mensal_v11_sabia_vmax_vmin.csv")
    x = _mes(d)
    fig, axs = plt.subplots(2, 1, figsize=(LARGURA, 3.6), sharex=True,
                            gridspec_kw={"height_ratios": [2.2, 1], "hspace": 0.12})
    ax = axs[0]
    _mandatos(ax)
    ax.plot(x, d["c_llm_vmax"], color=AZUL, lw=1.2, label="V-max (full text)")
    ax.plot(x, d["c_llm_vmin"], color=LARANJA, lw=1.0, ls="--", label="V-min (L5: no numbers, names, dates, outlet)")
    ax.set_ylim(0, 1)
    ax.set_ylabel(r"$\hat{C}^{LLM}$, monthly")
    ax.legend(loc="lower left", ncol=2, fontsize=7.5)
    _eixo(ax)
    ok = d.dropna(subset=["c_llm_vmax", "c_llm_vmin"])
    ax.text(0.99, 0.04, f"correlation {ok['c_llm_vmax'].corr(ok['c_llm_vmin']):.3f}", transform=ax.transAxes,
            ha="right", fontsize=7.5, color=TINTA2)
    b = axs[1]
    b.bar(x, d["delta_t"], width=25, color=np.where(d["delta_t"] >= 0, AZUL, LARANJA), lw=0)
    b.axhline(0, color=CINZA, lw=0.6)
    b.set_ylabel(r"$\Delta_t$ = V-max − V-min", fontsize=7.5)
    _eixo(b)
    _anos(b)
    _salvar(fig, "fig06_vmax_vmin")


# ── Figure 7: convergence ───────────────────────────────────────────────────

def fig7_convergence() -> None:
    p = pd.read_csv(ART / "painel_construto.csv")
    p = p[p["c_llm_jm3"].notna()]
    x = _mes(p)
    alvos = [("foc_gap_neg", "Focus: distance from the target (sign reversed)"),
             ("breakeven_neg", "Five-year breakeven inflation (sign reversed)"),
             ("c_kf_suavizado", "Anchoring latent from the Kalman filter")]
    fig, axs = plt.subplots(3, 1, figsize=(LARGURA, 5.4), sharex=True, gridspec_kw={"hspace": 0.42})
    for ax, (col, nome) in zip(axs, alvos):
        ok = p[["c_llm_jm3", col]].dropna()
        ax.plot(x, _z(p["c_llm_jm3"]), color=AZUL, lw=1.4)
        ax.plot(x, _z(p[col]), color=CINZA, lw=1.1)
        ax.axhline(0, color=CINZA, lw=0.5, ls=":")
        ax.set_title(f"{nome} · correlation {ok['c_llm_jm3'].corr(ok[col]):.2f}", fontsize=8.5)
        ax.set_ylabel("standard deviations", fontsize=7.5)
        _eixo(ax)
    _anos(axs[-1])
    fig.legend([matplotlib.lines.Line2D([], [], color=AZUL, lw=1.4), matplotlib.lines.Line2D([], [], color=CINZA, lw=1.1)],
               ["index (three-month window)", "panel measure"], loc="upper left", bbox_to_anchor=(0.01, 0.995), ncol=2)
    _salvar(fig, "fig07_convergence")


# ── Figure 8: beyond current inflation ──────────────────────────────────────

def fig8_beyond_inflation() -> None:
    p = pd.read_csv(ART / "painel_construto.csv")
    d = p.dropna(subset=["c_llm_jm3", *construto.CONTROLES_INFLACAO]).copy()
    res = sm.OLS(d["c_llm_jm3"], sm.add_constant(d[list(construto.CONTROLES_INFLACAO)])).fit()
    d["ajuste"] = res.fittedvalues
    x = _mes(d)
    fig, ax = plt.subplots(figsize=(LARGURA, 2.8))
    _mandatos(ax)
    ax.fill_between(x, d["ajuste"], d["c_llm_jm3"], color=AZUL, alpha=0.12, lw=0)
    ax.plot(x, d["ajuste"], color=CINZA, lw=1.1, label=f"predicted by current inflation only (R² = {res.rsquared:.2f})")
    ax.plot(x, d["c_llm_jm3"], color=AZUL, lw=1.5, label="index (three-month window)")
    ax.set_ylim(0.15, 0.95)
    ax.set_ylabel(r"$\hat{C}^{LLM}$")
    _anos(ax)
    _eixo(ax)
    ax.legend(loc="upper left", ncol=2, bbox_to_anchor=(0, -0.09))
    _salvar(fig, "fig08_beyond_inflation")


# ── Figure 9: predictive power ──────────────────────────────────────────────

def fig9_predictive() -> None:
    t = pd.read_csv(ART / "preditiva.csv")
    alvos = [("foc_gap_neg", "Focus (distance from target)"), ("breakeven_neg", "Five-year breakeven"),
             ("embi_neg", "Country risk (EMBI+)")]
    series = [("c_llm", "Sabiá, monthly", CINZA, -0.18), ("c_llm_jm3", "Sabiá, three-month window", AZUL, 0.0),
              ("c_llm_gemini", "Gemini, monthly", LARANJA, 0.18)]
    fig, axs = plt.subplots(1, 3, figsize=(LARGURA, 2.6))
    for ax, (alvo, nome) in zip(axs, alvos):
        ax.axhline(0, color=CINZA, lw=0.6)
        for col, rot, cor, desl in series:
            r = t[(t["indice"] == col) & (t["alvo"] == alvo)]
            ax.errorbar(r["h"] + desl, r["b"], yerr=1.96 * r["ep_hac"], fmt="o", ms=4, color=cor, capsize=0,
                        elinewidth=1.1, label=rot)
        ax.set_xticks([1, 3, 6])
        ax.set_xlabel("horizon (months)")
        ax.set_title(nome, fontsize=8.5)
        _eixo(ax)
    axs[0].set_ylabel("effect of 1 s.d. of the index\n(units of the target variable)", fontsize=7.5)
    axs[0].legend(loc="upper left", fontsize=7)
    fig.tight_layout()
    _salvar(fig, "fig09_predictive")


# ── Figure 10: Copom ────────────────────────────────────────────────────────

def fig10_copom() -> None:
    fig, axs = plt.subplots(1, 2, figsize=(LARGURA, 2.7), sharey=True)
    for ax, (arq, nome) in zip(axs, (("copom_d1_7d.csv", "7 days (pre-registered test)"),
                                     ("copom_d1_14d.csv", "14 days (secondary)"))):
        t = pd.read_csv(ART / arq).dropna(subset=["delta", "surpresa_bps"])
        m = sm.OLS(t["delta"], sm.add_constant(t["surpresa_bps"])).fit(cov_type="HC1")
        xs = np.linspace(t["surpresa_bps"].min(), t["surpresa_bps"].max(), 50)
        pr = m.get_prediction(sm.add_constant(xs)).summary_frame(alpha=0.05)
        ax.axhline(0, color=CINZA, lw=0.5); ax.axvline(0, color=CINZA, lw=0.5)
        ax.scatter(t["surpresa_bps"], t["delta"], s=10, color=CINZA, alpha=0.7, lw=0)
        ax.fill_between(xs, pr["mean_ci_lower"], pr["mean_ci_upper"], color=AZUL, alpha=0.15, lw=0)
        ax.plot(xs, pr["mean"], color=AZUL, lw=1.4)
        b = 10 * m.params["surpresa_bps"]
        ax.set_title(f"{nome}\n{'+' if b > 0 else ''}{b:.3f} per 10 bp · p = {m.pvalues['surpresa_bps']:.2f} · "
                     f"{int(m.nobs)} meetings", fontsize=8.5, linespacing=1.4)
        ax.set_xlabel("Copom surprise, 3-month swap (bp)")
        _eixo(ax)
        ax.xaxis.set_major_formatter(_PONTO)
    axs[0].set_ylabel("change in the index: after − before")
    fig.tight_layout()
    _salvar(fig, "fig10_copom")


# ── Figure 11: institutional events against the placebo ─────────────────────

def fig11_institutional() -> None:
    it = eventos.itens("sabia")
    k = 30
    rotulos = {"2016-05-17": "May 2016 · Goldfajn and technical-autonomy bill",
               "2020-11-03": "Nov 2020 · Senate approves autonomy",
               "2021-02-10": "Feb 2021 · Chamber approves autonomy",
               "2023-01-18": "Jan 2023 · President criticises autonomy",
               "2024-05-08": "May 2024 · split Copom vote (5–4)",
               "2024-12-11": "Dec 2024 · 100 bp hike and guidance"}
    dims = [("d1", False, "D1 · target"), ("d2", True, "D2 · conduct"), ("d3", True, "D3 · autonomy")]
    fig, axs = plt.subplots(1, 3, figsize=(LARGURA, 3.0), sharey=True)
    for ax, (dim, pond, nome) in zip(axs, dims):
        tab = eventos.diarios(it, dim, pond)
        datas = pd.date_range(tab.index.min() + pd.Timedelta(days=k + 1), tab.index.max() - pd.Timedelta(days=k + 1),
                              freq="7D")
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
        ax.set_xlabel("change over 30 days")
        ax.set_xlim(-0.25, 0.25)
        ax.xaxis.set_major_formatter(_PONTO)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.tick_params(axis="y", length=0)
    axs[0].set_yticks(range(len(rotulos)), list(rotulos.values())[::-1])
    fig.tight_layout()
    _salvar(fig, "fig11_institutional_events")


# ── Appendix B: prompt versions ─────────────────────────────────────────────

def figB1_prompt_versions() -> None:
    v10 = pd.read_csv(DERIV / "indice_mensal.csv")
    v11 = pd.read_csv(DERIV / "indice_mensal_v11_sabia.csv")
    fig, ax = plt.subplots(figsize=(LARGURA, 2.6))
    _mandatos(ax)
    ax.plot(_mes(v10), v10["c_llm"], color=CINZA, lw=1.1, label="v1.0 (score 3 = balanced or no signal)")
    ax.plot(_mes(v11), v11["c_llm"], color=AZUL, lw=1.1, label="v1.1 (no signal leaves the mean)")
    ax.axhline(0.5, color=CINZA, lw=0.6, ls=":")
    ax.set_ylim(0, 1)
    ax.set_ylabel(r"$\hat{C}^{LLM}$, monthly")
    _anos(ax)
    _eixo(ax)
    ax.legend(loc="lower left", ncol=2, bbox_to_anchor=(0, -0.3))
    _salvar(fig, "figB1_prompt_versions")


# ── Appendix F: index by outlet and by model ────────────────────────────────

def figF1_outlets() -> None:
    sys.path.insert(0, str(RAIZ / "llm"))
    import robustez_indice as rob  # noqa: E402
    sc, corpus = rob._scores_e_corpus()
    principal = pd.read_csv(DERIV / "indice_mensal_v11_sabia_jm3.csv")
    gem = pd.read_csv(DERIV / "indice_mensal_v11_gemini_flash_lite_jm3.csv")
    veiculos = ["Exame", "InfoMoney", "Valor", "G1", "Money Times"]
    fig, axs = plt.subplots(3, 2, figsize=(LARGURA, 6.0), sharex=True, sharey=True,
                            gridspec_kw={"hspace": 0.35, "wspace": 0.08})
    for ax, v in zip(axs.flat, veiculos):
        s = rob._serie(sc, corpus[corpus["veiculo"] == v], 3)
        ok = principal[["mes", "c_llm"]].merge(s[["mes", "c_llm", "n_itens"]], on="mes", suffixes=("", "_v")).dropna()
        ax.plot(_mes(principal), principal["c_llm"], color=CINZA_CLARO, lw=1.6)
        ax.plot(_mes(s), s["c_llm"].where(s["n_itens"] >= 10), color=AZUL, lw=1.0)
        ax.set_title(f"{v} · correlation {ok['c_llm'].corr(ok['c_llm_v']):.2f}", fontsize=8.5)
        ax.set_ylim(0, 1)
        _eixo(ax)
    ax = axs.flat[-1]
    ok = principal[["mes", "c_llm"]].merge(gem[["mes", "c_llm"]], on="mes", suffixes=("", "_g")).dropna()
    ax.plot(_mes(principal), principal["c_llm"], color=AZUL, lw=1.2)
    ax.plot(_mes(gem), gem["c_llm"], color=LARANJA, lw=1.0, ls="--")
    ax.set_title(f"Sabiá and Gemini · correlation {ok['c_llm'].corr(ok['c_llm_g']):.2f}", fontsize=8.5)
    _eixo(ax)
    for a in axs[-1]:
        _anos(a)
    fig.legend([matplotlib.lines.Line2D([], [], color=CINZA_CLARO, lw=1.6), matplotlib.lines.Line2D([], [], color=AZUL, lw=1.0),
                matplotlib.lines.Line2D([], [], color=LARANJA, lw=1.0, ls="--")],
               ["main index (Sabiá, all outlets)", "single outlet (months with ≥ 10 articles with a signal)", "Gemini"],
               loc="upper left", bbox_to_anchor=(0.01, 1.0), ncol=3, fontsize=7)
    _salvar(fig, "figF1_index_by_outlet_and_model")


FIGURAS = [fig1_coverage, fig2_funnel, fig3_index, fig4_dimensions, fig5_leakage_tests, fig6_vmax_vmin,
           fig7_convergence, fig8_beyond_inflation, fig9_predictive, fig10_copom, fig11_institutional,
           figB1_prompt_versions, figF1_outlets]


def main() -> None:
    _estilo()
    for f in FIGURAS:
        f()
        print("ok", f.__name__)


if __name__ == "__main__":
    main()

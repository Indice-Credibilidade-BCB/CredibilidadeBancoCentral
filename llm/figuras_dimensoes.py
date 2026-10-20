# -*- coding: utf-8 -*-
"""Séries das três dimensões (D1, D2, D3) do prompt v1.1, com figuras para o artigo.

Por que D2 e D3 precisam de peso
--------------------------------
O pré-filtro escolhe as notícias pelo sinal da D1. Notícias que falam da
condução (D2) ou da autonomia (D3) sem falar da meta caem em boa parte no
estrato descartado, do qual só 10% (sorteados) vão à API. Uma média simples
das notícias pontuadas sub-representaria esse estrato. O estimador é de
Horvitz-Thompson (forma de Hájek), condicional à partição já sorteada:

    rotulagem (amostra aleatória, toda pontuada)   peso 1
    enviadas pelo filtro (todas pontuadas)          peso 1
    descartadas auditadas (10% das descartadas)     peso N_desc / N_aud (~10)

A D1 usa a série oficial (média simples; a ponderada tem correlação > 0,99
com ela), e a ponderada vai junto no CSV.

Para cada dimensão k e período:
    nível   = soma(w * y_k) / soma(w), nas notícias com sinal em k, y = (d - 1)/4
    atenção = soma(w * 1{sinal em k}) / soma(w), em todas as notícias da produção
EP por linearização, agrupado por dia. Agência replicada conta uma vez por
período. Trimestral (soma notícias) e mensal em janela móvel de 3 meses para
trás, como a regra registrada para a D1.

Uso (de dentro de llm/):  python figuras_dimensoes.py
"""
from __future__ import annotations

import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import sandbox  # noqa: E402
import schema  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DERIV = RAIZ / "dados" / "derivados"
FIG = DERIV / "figuras"
PASTAS = {"sabia": "producao_v11", "gemini_flash_lite": "producao_v11_gemini"}
NOMES = {"sabia": "Sabiá (produção)", "gemini_flash_lite": "Gemini Flash-Lite (robustez)"}
DIMS = {
    "d1": "D1 — probabilidade percebida de cumprimento da meta",
    "d2": "D2 — confiança na condução da política monetária",
    "d3": "D3 — autonomia percebida do BCB",
}
ESCALA = {
    "d1": "0 = descumprimento certo · 1 = cumprimento certo",
    "d2": "0 = ceticismo forte · 1 = confiança forte",
    "d3": "0 = subordinação clara · 1 = autonomia plena",
}
PRESIDENTES = [("Tombini", "2011-01-01", "2016-06-09"), ("Goldfajn", "2016-06-09", "2019-02-28"),
               ("Campos Neto", "2019-02-28", "2025-01-01"), ("Galípolo", "2025-01-01", "2026-10-01")]
MARCOS_D3 = [("2016-05-17", "PEC da autonomia\ntécnica (anúncio)"), ("2021-02-10", "Câmara aprova\nLC 179/2021")]


def itens(provider: str) -> pd.DataFrame:
    """Notícias da produção pontuadas pela API, com peso de desenho e notas em [0,1]."""
    caminho = RAIZ / "dados" / "llm" / PASTAS[provider] / "consolidado_vmax.jsonl"
    df = pd.DataFrame([json.loads(l) for l in caminho.read_text(encoding="utf-8").splitlines()])
    df = df.drop_duplicates("item_id", keep="last")
    df = df[~df["item_id"].astype(str).map(sandbox.em_sandbox)]
    n_desc = int((df["origem"].isin(["filtro", "api_auditoria"])).sum())
    n_aud = int((df["origem"] == "api_auditoria").sum())
    df = df[df["origem"] != "filtro"].copy()
    # erro de API (raro): nenhuma das três dimensões preenchida nem marcada sem sinal -> fora
    sem1 = df["d1_sem_sinal"].eq(True) if "d1_sem_sinal" in df else False
    df = df[pd.to_numeric(df["d1"], errors="coerce").notna() | sem1]
    df["w"] = np.where(df["origem"] == "api_auditoria", n_desc / n_aud, 1.0)
    for k in DIMS:
        df[k] = (pd.to_numeric(df[k], errors="coerce") - 1) / 4.0
    corpus = schema.dedup(schema.validate(pd.read_parquet(RAIZ / "dados" / "llm" / "corpus.parquet")))
    df = df.merge(corpus[["item_id", "data_publicacao", "wire_cluster"]], on="item_id", how="inner")
    df["dia"] = pd.to_datetime(df["data_publicacao"]).dt.normalize()
    return df[["item_id", "dia", "wire_cluster", "origem", "w", *DIMS]]


def _media_ponderada(y: np.ndarray, w: np.ndarray, grupos: np.ndarray) -> tuple[float, float]:
    """Média de Hájek e EP por linearização agrupado por `grupos` (dias)."""
    if len(y) == 0:
        return np.nan, np.nan
    m = np.sum(w * y) / np.sum(w)
    z = pd.Series(w * (y - m) / np.sum(w)).groupby(grupos).sum().to_numpy()
    g = len(z)
    ep = np.sqrt(g / (g - 1) * np.sum(z ** 2)) if g > 1 else np.nan
    return float(m), float(ep)


def agregar(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """freq = 'Q' (trimestral) ou 'M3' (mensal, janela móvel de 3 meses para trás)."""
    if freq == "Q":
        df = df.assign(periodo=df["dia"].dt.to_period("Q"))
    else:
        mes = df["dia"].dt.to_period("M")
        ultimo = mes.max()
        df = pd.concat([df.assign(periodo=mes + k) for k in range(3)], ignore_index=True)
        df = df[df["periodo"] <= ultimo]
    # agência replicada: uma observação por (período, cluster)
    obs = df.groupby(["periodo", "wire_cluster"], as_index=False).agg(
        w=("w", "mean"), dia=("dia", "min"), **{k: (k, "mean") for k in DIMS})
    linhas = []
    for per, g in obs.groupby("periodo"):
        linha = {"periodo": str(per), "n_noticias": len(g), "n_ponderado": g["w"].sum()}
        dias = g["dia"].dt.strftime("%Y%m%d").to_numpy()
        for k in DIMS:
            tem = g[k].notna().to_numpy()
            nivel, ep = _media_ponderada(g.loc[tem, k].to_numpy(float), g.loc[tem, "w"].to_numpy(float), dias[tem])
            aten, ep_a = _media_ponderada(tem.astype(float), g["w"].to_numpy(float), dias)
            linha.update({f"{k}_ipw": nivel, f"{k}_ipw_ep": ep, f"{k}_atencao": aten, f"{k}_atencao_ep": ep_a,
                          f"{k}_n_sinal": int(tem.sum())})
        # D1 oficial: média simples das notícias com sinal (sem peso)
        t1 = g["d1"].notna().to_numpy()
        m1, ep1 = _media_ponderada(g.loc[t1, "d1"].to_numpy(float), np.ones(t1.sum()), dias[t1])
        linha.update({"d1": m1, "d1_ep": ep1})
        linhas.append(linha)
    return pd.DataFrame(linhas)


def _x(periodos: pd.Series, freq: str) -> pd.DatetimeIndex:
    if freq == "Q":
        return pd.PeriodIndex(periodos, freq="Q").to_timestamp(how="start") + pd.Timedelta(days=45)
    return pd.PeriodIndex(periodos, freq="M").to_timestamp(how="start") + pd.Timedelta(days=14)


def _estilo():
    plt.rcParams.update({"font.family": "serif", "font.serif": ["STIXGeneral", "DejaVu Serif"],
                         "mathtext.fontset": "stix", "font.size": 10, "axes.titlesize": 10.5,
                         "axes.labelsize": 9.5, "legend.fontsize": 8.5})


def _fundo(ax, rotular: bool, linha_meio: bool = True):
    for i, (nome, ini, fim) in enumerate(PRESIDENTES):
        a, b = pd.Timestamp(ini), pd.Timestamp(fim)
        if i % 2 == 1:
            ax.axvspan(a, b, color="0.93", lw=0, zorder=0)
        if rotular:
            ax.text(a + (b - a) / 2, 1.01, nome, transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                    fontsize=8, color="0.35")
    if linha_meio:
        ax.axhline(0.5, color="0.45", lw=0.7, ls=":", zorder=1)
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(pd.Timestamp("2010-12-01"), pd.Timestamp("2026-11-01"))
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def figura_niveis(series: dict[str, pd.DataFrame], freq: str, caminho: pathlib.Path) -> None:
    _estilo()
    fig, axs = plt.subplots(3, 1, figsize=(7.2, 8.6), sharex=True, gridspec_kw={"hspace": 0.32})
    for ax, k in zip(axs, DIMS):
        _fundo(ax, rotular=(k == "d1"))
        col = "d1" if k == "d1" else f"{k}_ipw"
        for prov, s in series.items():
            x = _x(s["periodo"], freq)
            if prov == "sabia":
                ax.fill_between(x, s[col] - 1.96 * s[f"{col}_ep"], s[col] + 1.96 * s[f"{col}_ep"],
                                color="#1f3b73", alpha=0.16, lw=0, zorder=2, label="IC 95% (Sabiá)")
                ax.plot(x, s[col], color="#1f3b73", lw=1.5, zorder=3, label=NOMES[prov])
            else:
                ax.plot(x, s[col], color="#b5541c", lw=1.0, ls="--", zorder=3, label=NOMES[prov])
        if k == "d3":
            for data, rot in MARCOS_D3:
                ax.axvline(pd.Timestamp(data), color="0.25", lw=0.7, ls="-.", zorder=1)
                ax.text(pd.Timestamp(data) + pd.Timedelta(days=40), 0.06, rot, fontsize=7.2, color="0.25", va="bottom")
        ax.set_ylim(0, 1)
        ax.set_title(DIMS[k], loc="left", pad=16 if k == "d1" else 6)
        ax.set_ylabel(ESCALA[k].replace(" · ", "\n"), fontsize=8)
    axs[0].legend(loc="lower left", frameon=False, ncol=3)
    nota = ("trimestral (média das notícias do trimestre)" if freq == "Q"
            else "mensal em janela móvel de 3 meses para trás")
    fig.text(0.01, 0.005,
             f"Frequência: {nota}. Prompt v1.1; só notícias com sinal na dimensão; quarentena (10%) excluída; "
             "agência replicada conta uma vez.\nD1: série oficial (média simples). D2 e D3: média ponderada pelo "
             "inverso da probabilidade de envio à API (o pré-filtro seleciona pela D1). Faixas: mandatos no BCB.",
             fontsize=7, color="0.3", va="bottom")
    fig.savefig(caminho.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(caminho.with_suffix(".png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def figura_atencao(s: pd.DataFrame, freq: str, caminho: pathlib.Path) -> None:
    _estilo()
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    _fundo(ax, rotular=True, linha_meio=False)
    x = _x(s["periodo"], freq)
    estilos = {"d1": dict(color="#1f3b73", lw=1.5), "d2": dict(color="#b5541c", lw=1.2, ls="--"),
               "d3": dict(color="#3d7a3d", lw=1.2, ls="-.")}
    curtos = {"d1": "D1 (cumprimento da meta)", "d2": "D2 (condução)", "d3": "D3 (autonomia)"}
    for k, e in estilos.items():
        ax.plot(x, 100 * s[f"{k}_atencao"], label=curtos[k], **e)
    ax.set_ylabel("% das notícias com sinal")
    ax.set_ylim(0, None)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), frameon=False, ncol=3)
    fig.text(0.01, -0.1, "Sabiá, prompt v1.1. Fração ponderada pelo desenho do pré-filtro (inclui as notícias "
             "não enviadas à API, representadas pela auditoria aleatória).", fontsize=7, color="0.3")
    fig.savefig(caminho.with_suffix(".pdf"), bbox_inches="tight")
    fig.savefig(caminho.with_suffix(".png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    base = {p: itens(p) for p in PASTAS}
    for freq, suf in (("Q", "trimestral"), ("M3", "jm3")):
        series = {p: agregar(df, freq) for p, df in base.items()}
        for p, s in series.items():
            s.to_csv(DERIV / f"indice_dimensoes_v11_{p}_{suf}.csv", index=False)
        figura_niveis(series, freq, FIG / f"dimensoes_v11_{suf}")
        figura_atencao(series["sabia"], freq, FIG / f"atencao_dimensoes_v11_{suf}")
        s = series["sabia"]
        print(f"[{suf}] {len(s)} períodos; notícias com sinal por período (mediana): "
              + ", ".join(f"{k} {s[f'{k}_n_sinal'].median():.0f}" for k in DIMS))
        print(f"  corr D1 oficial x D1 ponderada: {s['d1'].corr(s['d1_ipw']):.3f}")
        for a, b in (("d1_ipw", "d2_ipw"), ("d1_ipw", "d3_ipw"), ("d2_ipw", "d3_ipw")):
            print(f"  corr {a[:2]} x {b[:2]}: {s[a].corr(s[b]):.2f}")
        g = series["gemini_flash_lite"]
        print("  corr Sabiá x Gemini: " + ", ".join(
            f"{k} {s['d1' if k == 'd1' else f'{k}_ipw'].corr(g['d1' if k == 'd1' else f'{k}_ipw']):.2f}" for k in DIMS))


if __name__ == "__main__":
    main()

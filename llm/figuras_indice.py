# -*- coding: utf-8 -*-
"""Índice v1.1 em frequência diária e trimestral, com figuras.

Mesmo núcleo da série mensal (`aggregate._agregar_core`): nota c = (d1 − 1)/4
só nas notícias com sinal, colapso de agência (1 observação por período e
cluster wire) e EP agrupado por dia. O efeito fixo de tipo de veículo é
omitido porque o corpus atual só tem imprensa (gamma = 0).

- Diária: média do dia, mais a média móvel de 30 dias PARA TRÁS (soma
  notícias na janela, sem look-ahead), que é o que se lê no gráfico.
- Trimestral: soma as notícias do trimestre e tira uma média (robustez da
  regra de agregação registrada em 2026-10-19).

Uso (de dentro de llm/):
    python figuras_indice.py
Saídas em dados/derivados/: indice_diario_v11_sabia.csv,
indice_trimestral_v11_{sabia,gemini_flash_lite}.csv e figuras/*.png.
"""
from __future__ import annotations

import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import aggregate  # noqa: E402
import schema  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DERIV = RAIZ / "dados" / "derivados"
FIG = DERIV / "figuras"
PASTAS = {"sabia": "producao_v11", "gemini_flash_lite": "producao_v11_gemini"}
NOMES = {"sabia": "Sabiá (produção)", "gemini_flash_lite": "Gemini Flash-Lite (robustez)"}
JANELA_DIAS = 30


def itens_com_sinal(provider: str) -> pd.DataFrame:
    """Uma linha por notícia com sinal na D1: dia, cluster wire e nota c em [0,1]."""
    sc = aggregate.carregar_scores(str(RAIZ / "dados" / "llm" / PASTAS[provider] / "consolidado_vmax.jsonl"))
    sc = aggregate.excluir_sandbox(sc)
    corpus = schema.dedup(schema.validate(pd.read_parquet(RAIZ / "dados" / "llm" / "corpus.parquet")))
    df = sc.merge(corpus[["item_id", "data_publicacao", "wire_cluster"]], on="item_id", how="inner")
    df["dia"] = pd.to_datetime(df["data_publicacao"]).dt.normalize()
    df["c"] = (pd.to_numeric(df["d1"], errors="coerce") - 1) / 4.0
    return df.dropna(subset=["c"])[["item_id", "dia", "wire_cluster", "c"]]


def _colapsar_wire(df: pd.DataFrame, periodo: pd.Series) -> pd.DataFrame:
    return (df.assign(periodo=periodo)
              .groupby(["periodo", "wire_cluster"], as_index=False)
              .agg(c=("c", "mean"), dia=("dia", "min")))


def diario(df: pd.DataFrame) -> pd.DataFrame:
    """Média por dia e média móvel de 30 dias para trás (ponderada por notícia)."""
    obs = _colapsar_wire(df, df["dia"])
    d = obs.groupby("periodo").agg(c_llm=("c", "mean"), soma=("c", "sum"), n_itens=("c", "size"))
    d.index.name = "dia"
    cal = d.reindex(pd.date_range(d.index.min(), d.index.max(), freq="D"))
    cal.index.name = "dia"
    soma = cal["soma"].fillna(0).rolling(f"{JANELA_DIAS}D").sum()
    n = cal["n_itens"].fillna(0).rolling(f"{JANELA_DIAS}D").sum()
    cal[f"c_llm_mm{JANELA_DIAS}"] = (soma / n).where(n > 0)
    cal[f"n_itens_mm{JANELA_DIAS}"] = n
    return cal.drop(columns="soma").dropna(subset=[f"c_llm_mm{JANELA_DIAS}"])


def trimestral(df: pd.DataFrame) -> pd.DataFrame:
    """Média por trimestre (soma notícias) com EP agrupado por dia."""
    obs = _colapsar_wire(df, df["dia"].dt.to_period("Q"))
    linhas = []
    for tri, g in obs.groupby("periodo"):
        medias_dia = g.groupby("dia")["c"].mean()
        linhas.append({"trimestre": str(tri), "c_llm": g["c"].mean(), "c_llm_mediana": g["c"].median(),
                       "ep": medias_dia.std(ddof=1) / np.sqrt(len(medias_dia)) if len(medias_dia) > 1 else np.nan,
                       "n_itens": len(g), "n_dias": len(medias_dia)})
    return pd.DataFrame(linhas)


def _eixo_anos(ax):
    ax.xaxis.set_major_locator(mdates.YearLocator(1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.grid(axis="y", alpha=0.3)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def figura_diaria(d: pd.DataFrame, caminho: pathlib.Path) -> None:
    fig, (ax, axn) = plt.subplots(2, 1, figsize=(12, 6.5), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08})
    pts = d.dropna(subset=["c_llm"])
    ax.scatter(pts.index, pts["c_llm"], s=4 + 2 * np.sqrt(pts["n_itens"]), color="#9aa7b8", alpha=0.35,
               linewidths=0, label="média do dia")
    ax.plot(d.index, d[f"c_llm_mm{JANELA_DIAS}"], color="#1f3b73", lw=1.6,
            label=f"média móvel de {JANELA_DIAS} dias (para trás)")
    ax.axhline(0.5, color="0.4", lw=0.8, ls=":")
    ax.set_ylim(-0.02, 1.02)
    ax.set_ylabel(r"$\hat{C}^{LLM}$ (0 = descumprimento certo, 1 = meta certa)")
    ax.set_title("Índice de credibilidade do BCB (prompt v1.1, Sabiá) — frequência diária", loc="left")
    ax.legend(loc="lower left", frameon=False, fontsize=9)
    _eixo_anos(ax)
    axn.bar(pts.index, pts["n_itens"], width=1.0, color="#9aa7b8")
    axn.set_ylabel("notícias\ncom sinal/dia")
    _eixo_anos(axn)
    fig.text(0.01, 0.005, "Notícias sem sinal sobre a meta ficam fora da média. Quarentena (10%) excluída. "
             "Agência replicada conta uma vez.", fontsize=8, color="0.35")
    fig.savefig(caminho, dpi=160, bbox_inches="tight")
    plt.close(fig)


def figura_trimestral(series: dict[str, pd.DataFrame], caminho: pathlib.Path) -> None:
    fig, (ax, axn) = plt.subplots(2, 1, figsize=(12, 6.5), sharex=True,
                                  gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08})
    estilos = {"sabia": dict(color="#1f3b73", lw=1.8, marker="o", ms=3.5),
               "gemini_flash_lite": dict(color="#c0612b", lw=1.3, ls="--", marker="s", ms=2.5)}
    for prov, t in series.items():
        x = pd.PeriodIndex(t["trimestre"], freq="Q").to_timestamp(how="start") + pd.Timedelta(days=45)
        ax.plot(x, t["c_llm"], label=NOMES[prov], **estilos[prov])
        if prov == "sabia":
            ax.fill_between(x, t["c_llm"] - 1.96 * t["ep"], t["c_llm"] + 1.96 * t["ep"],
                            color="#1f3b73", alpha=0.15, lw=0, label="IC 95% (EP agrupado por dia)")
            axn.bar(x, t["n_itens"], width=70, color="#9aa7b8")
    ax.axhline(0.5, color="0.4", lw=0.8, ls=":")
    ax.set_ylim(0.2, 1.0)
    ax.set_ylabel(r"$\hat{C}^{LLM}$ (0 = descumprimento certo, 1 = meta certa)")
    ax.set_title("Índice de credibilidade do BCB (prompt v1.1) — frequência trimestral", loc="left")
    ax.legend(loc="lower left", frameon=False, fontsize=9)
    _eixo_anos(ax)
    axn.set_ylabel("notícias com\nsinal/trimestre\n(Sabiá)")
    _eixo_anos(axn)
    fig.text(0.01, 0.005, "Média das notícias do trimestre (soma notícias, não faz média de médias). "
             "Quarentena (10%) excluída. Agência replicada conta uma vez.", fontsize=8, color="0.35")
    fig.savefig(caminho, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    itens = {p: itens_com_sinal(p) for p in PASTAS}
    d = diario(itens["sabia"])
    d.to_csv(DERIV / "indice_diario_v11_sabia.csv", date_format="%Y-%m-%d")
    tri = {p: trimestral(df) for p, df in itens.items()}
    for p, t in tri.items():
        t.to_csv(DERIV / f"indice_trimestral_v11_{p}.csv", index=False)
    figura_diaria(d, FIG / "indice_v11_diario.png")
    figura_trimestral(tri, FIG / "indice_v11_trimestral.png")
    print(f"diária: {d['c_llm'].notna().sum()} dias com notícia com sinal, de {d.index.min():%Y-%m-%d} "
          f"a {d.index.max():%Y-%m-%d}")
    for p, t in tri.items():
        print(f"trimestral {p}: {len(t)} trimestres; notícias por trimestre min {t['n_itens'].min()}, "
              f"mediana {t['n_itens'].median():.0f}")


if __name__ == "__main__":
    main()

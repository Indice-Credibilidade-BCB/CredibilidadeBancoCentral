# -*- coding: utf-8 -*-
"""Etapa 4 de ponta a ponta: painel -> Kalman (Bloco 2) -> rivais -> encompassing (Bloco 3).

Uso (da raiz do repositório)::

    python -m validacao.pipeline                       # usa cache de dados/macro/
    python -m validacao.pipeline --atualizar           # baixa de novo do BCB
    python -m validacao.pipeline --indice sabia=dados/derivados/indice_mensal.csv \
                                 --indice gemini=dados/derivados/indice_mensal_gemini.csv

Saídas em ``dados/derivados/validacao/`` (agregados sem texto de terceiros):

* ``painel.csv`` — painel mensal completo (``validacao.painel``).
* ``c_kf.csv`` — latente filtrado e suavizado, EP, ganho, |d_t| (logístico)
  e a versão linear (``_lin``) como robustez.
* ``rivais.csv`` — de Mendonça 2007/2009, dispersão, DEG/mercado se houver.
* ``encompassing.csv`` — tabela completa (nível e diferenças, todas as
  variantes do LLM disponíveis); ``encompassing_veredito.csv`` — resumo;
  ``encompassing_vmax_vmin.csv`` — banda de vazamento, se houver V-min.
* ``fig_*.png`` — figuras de inspeção.
* ``relatorio.md`` — resumo legível com os números que vão para o Paper 1.
"""
from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from mercado import bcb as dados_bcb

from . import encompassing, kalman, painel as painel_mod, rivais as rivais_mod

RAIZ = dados_bcb.RAIZ
DIR_SAIDA = RAIZ / "dados" / "derivados" / "validacao"
INDICES_PADRAO = {
    "": RAIZ / "dados" / "derivados" / "indice_mensal_v11_sabia.csv",
    "_gemini": RAIZ / "dados" / "derivados" / "indice_mensal_v11_gemini_flash_lite.csv",
}


def _carregar_indices(especs: list[str] | None) -> dict[str, pd.DataFrame]:
    """"nome=caminho" -> {sufixo: DataFrame}. Sem especs, usa os padrões que existirem."""
    out: dict[str, pd.DataFrame] = {}
    if not especs:
        for suf, p in INDICES_PADRAO.items():
            if p.exists():
                out[suf] = painel_mod.carregar_indice_llm(p, sufixo=suf)
        return out
    for e in especs:
        nome, _, caminho = e.partition("=")
        suf = "" if nome in ("", "sabia", "principal") else f"_{nome}"
        out[suf] = painel_mod.carregar_indice_llm(caminho, sufixo=suf)
    return out


def rodar(atualizar: bool = False, indices: list[str] | None = None,
          saida: Path = DIR_SAIDA, inicio: str = "2001-11", figuras: bool = True) -> dict:
    saida.mkdir(parents=True, exist_ok=True)
    fontes = dados_bcb.baixar_tudo(atualizar=atualizar)
    idx = _carregar_indices(indices)
    pn = painel_mod.construir_painel(fontes, idx, inicio=inicio)
    painel_mod.salvar_painel(pn, saida / "painel.csv")

    # ── Bloco 2 ──
    amostra_kf = pn.dropna(subset=["pi_focus", "pi_lag", "pi_star"])
    tvp = kalman.TVPCredibilidade(link="logistica")
    kf = tvp.ajustar(amostra_kf)
    tvp_lin = kalman.TVPCredibilidade(link="identidade")
    kf_lin = tvp_lin.ajustar(amostra_kf)
    kf["c_kf_filtrado_lin"] = kf_lin["c_kf_filtrado"]
    kf["c_kf_suavizado_lin"] = kf_lin["c_kf_suavizado"]
    kf.index.name = "mes"
    kf.to_csv(saida / "c_kf.csv")
    diag = kalman.diagnostico_identificacao(kf)
    params_kf = {"logistico": {"sigma_eta": tvp.sigma_eta, "sigma_nu": tvp.sigma_nu, **tvp.resultado_otim},
                 "linear": {"sigma_eta": tvp_lin.sigma_eta, "sigma_nu": tvp_lin.sigma_nu, **tvp_lin.resultado_otim},
                 "identificacao": diag}
    (saida / "kalman_parametros.json").write_text(json.dumps(params_kf, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── Rivais ──
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        riv = rivais_mod.montar_rivais(pn)
    riv.index.name = "mes"
    # séries de fornecedor (CDS, EMBI+) não saem em arquivo, nem agregadas
    riv.drop(columns=[c for c in ("cds_neg", "embi_neg") if c in riv]).to_csv(saida / "rivais.csv")
    avisos_txt = [str(a.message) for a in avisos]

    # ── Bloco 3 ──
    cols_llm = [c for c in pn.columns if c.startswith("c_llm") and not c.startswith("c_llm_mediana")]
    tabelas = []
    veredito = vmaxmin = None
    if cols_llm:
        variantes = pn[cols_llm]
        latente = kf["c_kf_suavizado"]
        for em_dif in (False, True):
            t = encompassing.encompassing_variantes(latente, variantes, riv, em_diferencas=em_dif)
            tabelas.append(t)
        tab = pd.concat(tabelas, ignore_index=True)
        tab.to_csv(saida / "encompassing.csv", index=False)
        veredito = encompassing.veredito(tab[tab["em_diferencas"] == False])  # noqa: E712
        veredito.to_csv(saida / "encompassing_veredito.csv", index=False)
        vmaxmin = encompassing.comparar_vmax_vmin(tab[tab["em_diferencas"] == False])  # noqa: E712
        if vmaxmin is not None:
            vmaxmin.to_csv(saida / "encompassing_vmax_vmin.csv", index=False)
    else:
        tab = pd.DataFrame()

    if figuras:
        _figuras(pn, kf, riv, saida)
    _relatorio(pn, kf, params_kf, riv, tab, veredito, vmaxmin, avisos_txt, saida)
    return {"painel": pn, "kf": kf, "rivais": riv, "encompassing": tab, "veredito": veredito, "vmax_vmin": vmaxmin}


def _figuras(pn: pd.DataFrame, kf: pd.DataFrame, riv: pd.DataFrame, saida: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = kf.index.to_timestamp()
    fig, ax = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    ax[0].plot(t, kf["c_kf_suavizado"], label="Ĉ_KF suavizado (logístico)")
    ax[0].fill_between(t, kf["c_kf_suavizado"] - 1.96 * kf["ep_suavizado"],
                       kf["c_kf_suavizado"] + 1.96 * kf["ep_suavizado"], alpha=0.2)
    ax[0].plot(t, kf["c_kf_filtrado"], lw=0.8, alpha=0.7, label="Ĉ_KF filtrado (tempo real)")
    ax[0].plot(t, kf["c_kf_suavizado_lin"], ls="--", lw=0.8, label="linear (robustez)")
    for c in [c for c in pn.columns if c in ("c_llm", "c_llm_gemini", "c_llm_vmax", "c_llm_vmin")]:
        ax[0].plot(pn.index.to_timestamp(), pn[c], lw=0.9, label=c)
    ax[0].set_ylim(-0.05, 1.05); ax[0].legend(fontsize=8, ncol=3); ax[0].set_title("Bloco 2 — credibilidade latente vs. índice LLM")
    ax[1].plot(t, kf["identificacao"], color="gray"); ax[1].axhline(1.0, ls=":", color="k")
    ax[1].set_title("|π* − π_{t−1}| (identificação; abaixo da linha o filtro segue o prior)")
    for c in riv.columns:
        ax[2].plot(riv.index.to_timestamp(), riv[c], lw=0.9, label=c)
    ax[2].legend(fontsize=8, ncol=3); ax[2].set_title("Rivais (orientados: maior = mais credibilidade)")
    fig.tight_layout(); fig.savefig(saida / "fig_bloco2_latente.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 4))
    tp = pn.index.to_timestamp()
    ax.plot(tp, pn["pi_focus"], label="Focus 12m"); ax.plot(tp, pn["pi_lag"], label="IPCA 12m (t−1)")
    ax.plot(tp, pn["pi_star"], label="meta 12m à frente", color="k", lw=0.8)
    ax.fill_between(tp, pn["pi_star"] - pn["banda"], pn["pi_star"] + pn["banda"], color="k", alpha=0.08)
    ax.legend(fontsize=8); ax.set_title("Insumos do Bloco 2"); fig.tight_layout()
    fig.savefig(saida / "fig_insumos_bloco2.png", dpi=130); plt.close(fig)


def _relatorio(pn, kf, params_kf, riv, tab, veredito, vmaxmin, avisos, saida: Path) -> None:
    L = []
    L.append("# Etapa 4 — Kalman e encompassing (saída automática)\n")
    L.append(f"Painel: {pn.index.min()} a {pn.index.max()} ({len(pn)} meses). "
             f"Amostra do filtro: {kf.index.min()} a {kf.index.max()} ({len(kf)} meses).\n")
    L.append("## Bloco 2 — parâmetros por máxima verossimilhança\n")
    for k in ("logistico", "linear"):
        p = params_kf[k]
        L.append(f"- **{k}**: σ_η = {p['sigma_eta']:.4f}, σ_ν = {p['sigma_nu']:.4f}, "
                 f"loglik = {p['loglik']:.2f}, otimizador ok = {p['sucesso']}")
    d = params_kf["identificacao"]
    L.append(f"\nIdentificação fraca (|π*−π_{{t−1}}| < {d['limiar_pp']} p.p.): "
             f"{100*d['frac_meses_fracos']:.1f}% dos meses; ganho médio {d['ganho_medio_fraco']:.3f} (fraco) "
             f"vs {d['ganho_medio_forte']:.3f} (forte); EP médio {d['ep_medio_fraco']:.3f} vs {d['ep_medio_forte']:.3f}.\n")
    desc = kf[["c_kf_filtrado", "c_kf_suavizado", "c_kf_suavizado_lin"]].describe().T[["mean", "std", "min", "max"]]
    L.append(desc.round(3).to_markdown() + "\n")
    L.append("## Rivais disponíveis\n")
    for c in riv.columns:
        L.append(f"- `{c}` ({rivais_mod.FAMILIA.get(c, '?')}): {riv[c].notna().sum()} meses")
    for a in avisos:
        L.append(f"- ⚠ {a}")
    corr = pd.concat([kf["c_kf_suavizado"], riv], axis=1).corr().iloc[0, 1:]
    L.append("\nCorrelação do latente com cada rival:\n")
    L.append(corr.round(3).to_frame("corr").to_markdown() + "\n")
    if len(tab):
        L.append("## Bloco 3 — encompassing (nível, padronizado, HAC)\n")
        niv = tab[(tab["em_diferencas"] == False)].copy()  # noqa: E712
        cols = ["variante_llm", "rival", "n", "b1", "t_b1", "p_b1", "b2", "t_b2", "p_b2", "r2"]
        cols = [c for c in cols if c in niv.columns]
        L.append(niv[cols].round(3).to_markdown(index=False) + "\n")
        L.append("### Robustez em primeiras diferenças\n")
        dif = tab[(tab["em_diferencas"] == True)]  # noqa: E712
        L.append(dif[cols].round(3).to_markdown(index=False) + "\n")
        if veredito is not None:
            L.append("### Veredito por variante (nível, α = 5%)\n")
            L.append(veredito.round(3).to_markdown(index=False) + "\n")
        if vmaxmin is not None:
            L.append("### Banda de vazamento V-max × V-min (D12)\n")
            L.append(vmaxmin.round(3).to_markdown(index=False) + "\n")
    else:
        L.append("## Bloco 3\n\nNenhum índice LLM encontrado no painel — encompassing pulado.\n")
    L.append("\n> Leitura: o índice é validado se b1 segue significativo com cada rival; "
             "se V-max e V-min divergirem, o V-min manda (D12). Latente e rivais de Focus "
             "compartilham a fonte — as âncoras decisivas são institucional e de mercado.")
    (saida / "relatorio.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:  # pragma: no cover
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--atualizar", action="store_true")
    ap.add_argument("--indice", action="append", help="nome=caminho (repetível)")
    ap.add_argument("--saida", default=str(DIR_SAIDA))
    ap.add_argument("--inicio", default="2001-11")
    ap.add_argument("--sem-figuras", action="store_true")
    a = ap.parse_args()
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # console do Windows é cp1252
    r = rodar(atualizar=a.atualizar, indices=a.indice,
              saida=Path(a.saida), inicio=a.inicio, figuras=not a.sem_figuras)
    print((Path(a.saida) / "relatorio.md").read_text(encoding="utf-8"))


if __name__ == "__main__":  # pragma: no cover
    main()

# -*- coding: utf-8 -*-
"""Artigo de medição, de ponta a ponta: robustez do índice, validação e eventos.

Versão "clean" decidida em 2026-10-20 (sem NK e sem projeções locais).
Especificações e critérios registrados antes de rodar: docs/local, 4.2.17.

Uso (da raiz):  python -m validacao.artigo
Saídas em dados/derivados/validacao/artigo/ (locais): tabelas CSV, figuras e
relatorio.md com os veredictos pelos critérios registrados.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from . import construto, eventos
from . import pipeline as pipeline_validacao
from mercado.bcb import RAIZ

DERIV = RAIZ / "dados" / "derivados"
DIR_SAIDA = DERIV / "validacao" / "artigo"
INDICES = [f"sabia={DERIV / 'indice_mensal_v11_sabia.csv'}",
           f"jm3={DERIV / 'indice_mensal_v11_sabia_jm3.csv'}",
           f"gemini={DERIV / 'indice_mensal_v11_gemini_flash_lite.csv'}",
           f"gemjm3={DERIV / 'indice_mensal_v11_gemini_flash_lite_jm3.csv'}",
           f"dupla={DERIV / 'indice_mensal_v11_sabia_vmax_vmin.csv'}"]
VENDOR = ("cds_neg", "embi_neg")
COLS_C = ["c_llm", "c_llm_jm3", "c_llm_gemini", "c_llm_gemjm3"]
NOMES = {"c_llm": "Sabiá mensal", "c_llm_jm3": "Sabiá jm3", "c_llm_gemini": "Gemini mensal",
         "c_llm_gemjm3": "Gemini jm3"}


def _robustez_indice() -> pd.DataFrame:
    sys.path.insert(0, str(RAIZ / "llm"))
    import robustez_indice  # noqa: E402
    return robustez_indice.main()


def rodar(saida: Path = DIR_SAIDA, figuras: bool = True) -> dict:
    saida.mkdir(parents=True, exist_ok=True)
    enc = pipeline_validacao.rodar(indices=INDICES, saida=saida / "encompassing", figuras=False)
    df = construto.preparar(enc["painel"], enc["rivais"], enc["kf"])
    # séries de fornecedor (CDS, EMBI+) não saem em arquivo, nem agregadas
    df.drop(columns=[c for c in VENDOR if c in df]).to_csv(saida / "painel_construto.csv")

    conv = construto.convergente(df, COLS_C)
    disc_a, disc_b = construto.discriminante(df, COLS_C)
    pred = construto.preditiva(df, COLS_C)
    rob = _robustez_indice()

    it = eventos.itens("sabia")
    sur = eventos.surpresas_copom()
    copom = {}
    for nome, kw in (("d1_7d", dict(k=7)), ("d1_14d", dict(k=14)), ("d2_7d", dict(k=7, dim="d2", ponderar=True))):
        tab, res = eventos.estudo_copom(it, sur, **kw)
        tab.to_csv(saida / f"copom_{nome}.csv", index=False)
        copom[nome] = res
    inst = eventos.eventos_institucionais(it)

    for nome, t in (("convergente", conv), ("discriminante_a", disc_a), ("discriminante_b", disc_b),
                    ("preditiva", pred), ("robustez_indice", rob), ("eventos_institucionais", inst)):
        t.to_csv(saida / f"{nome}.csv", index=False)
    vered = {"convergente": construto.veredito_convergente(conv),
             "discriminante": construto.veredito_discriminante(disc_a, disc_b),
             "preditiva": construto.veredito_preditiva(pred),
             "copom": copom}
    (saida / "veredictos.json").write_text(json.dumps(vered, indent=2, ensure_ascii=False, default=float), encoding="utf-8")
    if figuras:
        from . import figuras_artigo
        figuras_artigo.main()
    _relatorio(enc, conv, disc_a, disc_b, pred, rob, copom, inst, vered, saida)
    return {"painel": df, "convergente": conv, "discriminante": (disc_a, disc_b), "preditiva": pred,
            "robustez": rob, "copom": copom, "institucionais": inst, "veredictos": vered}


def _md(t: pd.DataFrame) -> str:
    return t.round(3).to_markdown(index=False)


def _relatorio(enc, conv, disc_a, disc_b, pred, rob, copom, inst, vered, saida: Path) -> None:
    v = vered
    L = ["# Artigo de medição — resultados provisórios (saída automática)\n",
         "Critérios registrados antes de rodar: docs/local, seção 4.2.17. Série principal: Sabiá v1.1 mensal.\n",
         "## Seção 5 — robustez da construção (composição de veículos e amostra aleatória)\n", _md(rob) + "\n",
         "## 7.1 Convergente\n",
         f"Critério (Sabiá mensal): positiva e p < 5% com breakeven_neg E com dm2007 ou foc_gap_neg → "
         f"**{'APROVADO' if v['convergente']['aprovado'] else 'REPROVADO'}** {v['convergente']}\n",
         _md(conv.pivot_table(index="alvo", columns="indice", values="corr").reset_index()) + "\n",
         "p HAC:\n", _md(conv.pivot_table(index="alvo", columns="indice", values="p_hac").reset_index()) + "\n",
         "## 7.2 Discriminante\n",
         f"Critério: R² da inflação < 0,8 E c > 0, p < 5% para breakeven_neg ou embi_neg → "
         f"**{'APROVADO' if v['discriminante']['aprovado'] else 'REPROVADO'}** {v['discriminante']}\n",
         _md(disc_a[["indice", "n", "r2_inflacao"]]) + "\n", _md(disc_b) + "\n",
         "## 7.3 Preditiva (não vista antes)\n",
         f"Primário: foc_gap_neg, h = 6, b > 0 e p < 5% → "
         f"**{'APROVADO' if v['preditiva']['aprovado_primario'] else 'REPROVADO'}** {v['preditiva']}\n",
         _md(pred) + "\n",
         "## 7.4 Encompassing (contra o latente do Kalman)\n",
         _md(enc["encompassing"][enc["encompassing"]["em_diferencas"] == False][  # noqa: E712
             ["variante_llm", "rival", "n", "b1", "p_b1", "r2"]]) + "\n",
         "## 8 Estudo de eventos do Copom (não visto antes)\n",
         "b = variação do Δ do índice por 10 bps de surpresa; HC1.\n",
         _md(pd.DataFrame({k: {**r["surpresa"], "delta_medio": r["delta_medio"]} for k, r in copom.items()}).T.reset_index()) + "\n",
         "|surpresa|:\n", _md(pd.DataFrame({k: r["abs_surpresa"] for k, r in copom.items()}).T.reset_index()) + "\n",
         "## 8 Eventos institucionais (EXPLORATÓRIO)\n", _md(inst) + "\n"]
    (saida / "relatorio.md").write_text("\n".join(L), encoding="utf-8")


def main() -> None:  # pragma: no cover
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--saida", default=str(DIR_SAIDA))
    ap.add_argument("--sem-figuras", action="store_true")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    rodar(Path(a.saida), figuras=not a.sem_figuras)
    print((Path(a.saida) / "relatorio.md").read_text(encoding="utf-8"))


if __name__ == "__main__":  # pragma: no cover
    main()

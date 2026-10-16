# -*- coding: utf-8 -*-
"""Bateria anti-vazamento (D6/D11/D12) de ponta a ponta: amostra, desfecho
futuro, comandos de pontuação e relatório de T0, T2, T3, T4, T5 e T6.

Uso (de dentro de llm/):
  python bateria.py preparar --provider gemini_flash_lite      # amostra + surpresa + entradas
  # ... rodar os comandos impressos (t0_probe.py, scorer.py) ...
  python bateria.py relatorio --provider gemini_flash_lite     # T0/T2/T3/T5 (+ T4/T6 se houver insumos)

Desenho
-------
* Amostra: itens de PRODUÇÃO (fora da quarentena D13), estratificados pelos
  episódios de `config.pilot.strata`, ``N_POR_ESTRATO`` por episódio,
  semente fixa. A base de comparação de T2/T3 é a nota de produção (V-max:
  data real, texto integral) do mesmo provedor.
* Desfecho futuro (T2/T3/T4): surpresa de inflação 12 meses à frente da
  data do item = IPCA acumulado em 12 meses realizado no mês t+12 − mediana
  Focus do IPCA 12 meses (suavizada) na última pesquisa até a data do item,
  em p.p. Itens dos últimos 12 meses ficam sem desfecho (ainda não realizado).
* Critérios de reprovação (pré-registrados em D6):
    T2/T3 — corr(Δ, desfecho futuro) significativa a 5% E |ρ| ≥ 0,25,
            Δ = nota da variante − nota de produção;
    T4    — coeficiente significativo a 5% (Newey-West);
    T5    — diferença pareada entre eras significativa a 5%.
* T4 ADAPTADO (sem ouro humano): o pré-registro controla pelo escore humano.
  Como não há rotulagem humana, a referência passa a ser a nota V-min (a
  versão mascarada no nível que o T0 aprovou): regride-se a parte da nota
  V-max NÃO explicada pela V-min na surpresa futura. Se a informação extra
  do texto integral prevê o desfecho, é vazamento de desfecho.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd
import yaml

ROOT = pathlib.Path(__file__).parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO))

import sandbox  # noqa: E402
from diagnostics.leakage import (comparar_t6, comparar_variantes,  # noqa: E402
                                 gerar_variantes_data, teste_sinteticos)
from diagnostics.temporal_probe import avaliar_t0, nivel_minimo_cego  # noqa: E402

DIR = REPO / "dados" / "llm" / "bateria"
N_POR_ESTRATO = 50
SEMENTE = 42
NIVEIS_T3 = ("L1", "L2", "L3", "L4")
RHO_MIN = 0.25
ALFA = 0.05


def _cfg() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def _scores(path: pathlib.Path, variante: str | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["item_id", "d1"])
    s = pd.read_json(path, lines=True)
    s = s[s["erro"].isna() & s["d1"].notna()]
    if variante is not None:
        s = s[s["variante"] == variante]
    return s.drop_duplicates("item_id", keep="last")[["item_id", "d1"]]


# ─── preparação ──────────────────────────────────────────────────────────

def amostra_estratificada(corpus: pd.DataFrame, n_por_estrato: int = N_POR_ESTRATO,
                          semente: int = SEMENTE) -> pd.DataFrame:
    prod, _ = sandbox.separar(corpus)
    d = pd.to_datetime(prod["data_publicacao"], format="mixed")
    partes = []
    for e in _cfg()["pilot"]["strata"]:
        m = (d >= pd.Timestamp(e["start"])) & (d <= pd.Timestamp(e["end"]))
        g = prod[m]
        partes.append(g.sample(n=min(n_por_estrato, len(g)), random_state=semente).assign(estrato=e["label"]))
    return pd.concat(partes, ignore_index=True)


def surpresa_futura(datas: pd.Series) -> pd.Series:
    """IPCA 12m realizado em t+12 − mediana Focus 12m (suavizada) na data (p.p.)."""
    from validacao import dados_bcb
    ipca = dados_bcb.sgs("ipca_12m")
    ipca.index = pd.DatetimeIndex(ipca.index).to_period("M")
    focus = dados_bcb.focus_ipca_12m().sort_values("Data")
    f_d = pd.Series(focus["Mediana"].to_numpy(), index=pd.DatetimeIndex(focus["Data"]))
    d = pd.to_datetime(datas, format="mixed")
    esperado = f_d.reindex(f_d.index.union(d.dropna().unique())).sort_index().ffill().reindex(d).to_numpy()
    realizado = ipca.reindex(d.dt.to_period("M") + 12).to_numpy()
    return pd.Series(realizado - esperado, index=datas.index, name="surpresa_futura")


def preparar(provider: str) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    corpus = pd.read_parquet(REPO / "dados" / "llm" / "corpus.parquet")
    a = amostra_estratificada(corpus)
    a["surpresa_futura"] = surpresa_futura(a["data_publicacao"])
    a.to_csv(DIR / "amostra.csv", index=False)
    gerar_variantes_data(a).to_csv(DIR / "amostra_t2_trocada.csv", index=False)
    print(f"amostra: {len(a)} itens de produção ({a['estrato'].nunique()} episódios); "
          f"com desfecho realizado: {int(a['surpresa_futura'].notna().sum())}")
    print("\nComandos (de dentro de llm/):")
    print(f"python t0_probe.py rodar --provider {provider} --input {DIR / 'amostra.csv'} --out {DIR / 't0.jsonl'}")
    print(f"python scorer.py --provider {provider} --mode producao --input {DIR / 'amostra.csv'} --date-mode omitida --out {DIR / 't2.jsonl'}")
    print(f"python scorer.py --provider {provider} --mode producao --input {DIR / 'amostra_t2_trocada.csv'} --date-mode trocada --out {DIR / 't2.jsonl'}")
    for n in NIVEIS_T3:
        print(f"python scorer.py --provider {provider} --mode producao --input {DIR / 'amostra.csv'} --anonimizacao {n} --out {DIR / 't3.jsonl'}")
    print(f"python scorer.py --provider {provider} --mode producao --input fixtures/sinteticos_T5.csv --out {DIR / 't5.jsonl'}")


# ─── relatório ───────────────────────────────────────────────────────────

def _reprova_t2t3(r: dict) -> bool | None:
    if "p_delta_desfecho" not in r or r.get("p_delta_desfecho") is None:
        return None
    return bool(r["p_delta_desfecho"] < ALFA and abs(r["corr_delta_desfecho"]) >= RHO_MIN)


def relatorio_t0() -> dict | None:
    p = DIR / "t0.jsonl"
    if not p.exists():
        return None
    df = pd.read_json(p, lines=True)
    df = df[df["erro"].isna()].drop_duplicates(["item_id", "nivel"], keep="last")
    res = {n: avaliar_t0(g[["item_id", "ano_estimado", "data_publicacao_real"]]) for n, g in df.groupby("nivel")}
    return {"por_nivel": res, "nivel_minimo_vmin": nivel_minimo_cego(res)}


def relatorio(provider: str, vmin_path: pathlib.Path | None = None,
              local_scores: pathlib.Path | None = None) -> dict:
    a = pd.read_csv(DIR / "amostra.csv")
    desf = a.set_index("item_id")["surpresa_futura"]
    datas = a.set_index("item_id")["data_publicacao"]
    base = _scores(REPO / "dados" / "llm" / "scores" / f"producao_{provider}.jsonl", "producao|real|nenhuma")
    base = base[base["item_id"].isin(a["item_id"])]
    out: dict = {"provider": provider, "n_amostra": len(a), "n_base": len(base),
                 "criterios": {"rho_min": RHO_MIN, "alfa": ALFA}}

    out["T0"] = relatorio_t0()

    t2 = {}
    for modo in ("omitida", "trocada"):
        alt = _scores(DIR / "t2.jsonl", f"producao|{modo}|nenhuma")
        if len(alt):
            r = comparar_variantes(base, alt, desf, datas)
            r["reprova"] = _reprova_t2t3(r)
            t2[modo] = r
    out["T2"] = t2

    t3 = {}
    for n in NIVEIS_T3:
        alt = _scores(DIR / "t3.jsonl", f"producao|real|{n}")
        if len(alt):
            r = comparar_variantes(base, alt, desf, datas)
            r["reprova"] = _reprova_t2t3(r)
            t3[n] = r
    out["T3"] = t3

    t5p = DIR / "t5.jsonl"
    if t5p.exists():
        fx = pd.read_csv(ROOT / "fixtures" / "sinteticos_T5.csv")[["item_id", "texto_grupo", "era"]]
        s5 = _scores(t5p).merge(fx, on="item_id")
        r = teste_sinteticos(s5)
        r["reprova"] = bool(r.get("p_pareado", 1.0) < ALFA)
        out["T5"] = r

    if vmin_path is not None and vmin_path.exists():
        out["T4"] = t4_adaptado(provider, vmin_path)
    if local_scores is not None and local_scores.exists():
        out["T6"] = t6(provider, local_scores)

    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / f"relatorio_{provider}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False, default=str),
                                                    encoding="utf-8")
    return out


def t4_adaptado(provider: str, vmin_path: pathlib.Path) -> dict:
    """T4 com a nota V-min no lugar do ouro humano (ver docstring do módulo)."""
    from validacao.econometria import ols_hac
    corpus = pd.read_parquet(REPO / "dados" / "llm" / "corpus.parquet")[["item_id", "data_publicacao"]]
    vmax = _scores(REPO / "dados" / "llm" / "scores" / f"producao_{provider}.jsonl", "producao|real|nenhuma")
    vmin = _scores(vmin_path)
    m = vmax.merge(vmin, on="item_id", suffixes=("_vmax", "_vmin")).merge(corpus, on="item_id")
    m = m[~m["item_id"].astype(str).map(sandbox.em_sandbox)]
    m["surpresa"] = surpresa_futura(m["data_publicacao"]).to_numpy()
    m["mes"] = pd.to_datetime(m["data_publicacao"], format="mixed").dt.to_period("M")
    # resíduo item a item da V-max dado a V-min (OLS simples)
    x, y = m["d1_vmin"].astype(float), m["d1_vmax"].astype(float)
    b = np.polyfit(x, y, 1)
    m["resid"] = y - (b[0] * x + b[1])
    mens = m.dropna(subset=["surpresa"]).groupby("mes").agg(resid=("resid", "mean"), surpresa=("surpresa", "first"),
                                                            n=("resid", "size"))
    mens = mens[mens["n"] >= 10]
    res = ols_hac(mens["resid"], mens[["surpresa"]])
    item = m.dropna(subset=["surpresa"])
    rho = float(np.corrcoef(item["resid"], item["surpresa"])[0, 1])
    return {"n_itens": int(len(m)), "n_meses": int(res.n), "coef_surpresa": float(res.params["surpresa"]),
            "ep_hac": float(res.ep["surpresa"]), "p": float(res.p["surpresa"]),
            "corr_item_resid_surpresa": rho, "reprova": bool(res.p["surpresa"] < ALFA),
            "obs": "adaptado: referência = nota V-min (não há ouro humano)"}


def t6(provider: str, local_scores: pathlib.Path) -> dict:
    """Série mensal do braço local (BERTimbau) × API, só pós-2019 (D14)."""
    import aggregate
    corpus = pd.read_parquet(REPO / "dados" / "llm" / "corpus.parquet")
    loc = aggregate.excluir_sandbox(aggregate.carregar_scores(str(local_scores)))
    serie_local = aggregate.agregar(loc, corpus)
    serie_local["mes"] = serie_local["mes"].astype(str)  # mesmo formato do CSV da API
    serie_local.to_csv(REPO / "dados" / "derivados" / "indice_mensal_bertimbau.csv", index=False)
    arq = "indice_mensal.csv" if provider == "sabia" else f"indice_mensal_{provider.split('_')[0]}.csv"
    api = pd.read_csv(REPO / "dados" / "derivados" / arq)
    return comparar_t6(api, serie_local)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p1 = sub.add_parser("preparar"); p1.add_argument("--provider", required=True)
    p2 = sub.add_parser("relatorio"); p2.add_argument("--provider", required=True)
    p2.add_argument("--vmin", default=None, help="jsonl da passada V-min (para o T4)")
    p2.add_argument("--local", default=None, help="jsonl do braço local (para o T6)")
    a = ap.parse_args()
    if a.cmd == "preparar":
        preparar(a.provider)
    else:
        r = relatorio(a.provider, pathlib.Path(a.vmin) if a.vmin else None,
                      pathlib.Path(a.local) if a.local else None)
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str))

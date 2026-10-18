# -*- coding: utf-8 -*-
"""Produção do índice com o prompt v1.1, com economia de tokens:
pré-filtro local de sinal + auditoria (uma notícia por chamada).

O empacotamento em lote foi testado e REJEITADO pelos critérios registrados
(efeito de contraste: notícias com sinal recebem nota mais baixa no lote; ver
docs/local, 4.2.12). A economia vem do filtro e do V-min só na amostra.

Etapas (cada uma retomável; rodar de dentro de llm/):
  1. rotulagem  — amostra aleatória de produção pontuada pela API
  2. filtro     — treina o BERTimbau para "tem sinal?" nos rótulos da etapa 1
  3. rotear     — P(sinal) local para o resto; envia os prováveis e uma
                  auditoria aleatória das descartadas
  4. pontuar    — API nas enviadas + auditadas
  5. vmin       — V-min (D12) no nível L5, só na amostra de rotulagem (aleatória)
  6. consolidar — junta tudo, agrega as séries e grava as CONTAGENS

  python producao_v11.py tudo --provider sabia

Contagens (``dados/derivados/producao_v11_contagens.json`` e
``producao_v11_contagens_mensais.csv``): quantas notícias o projeto deixa de
mandar à API e por quê — números que vão para o paper.

Estimativa de sinal perdido: a auditoria é uma amostra aleatória das
descartadas; a fração com sinal nela estima a fração com sinal em TODAS as
descartadas. Robustez: média com peso inverso da probabilidade de auditoria
(``c_llm_ipw`` nas contagens mensais).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))

import subprocess  # noqa: E402

import aggregate  # noqa: E402
import sandbox  # noqa: E402

DIR = REPO / "dados" / "llm" / "producao_v11"
DERIV = REPO / "dados" / "derivados"
N_ROTULAGEM = 9000   # ~15% da produção: rótulos do filtro E base do V-min
N_PROCESSOS = 3
FRAC_AUDITORIA = 0.10
SEMENTE = 2026


def _corpus() -> pd.DataFrame:
    return pd.read_parquet(REPO / "dados" / "llm" / "corpus.parquet")


def _producao() -> pd.DataFrame:
    prod, _ = sandbox.separar(_corpus())
    return prod.reset_index(drop=True)


def _validos(path: pathlib.Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["item_id", "d1", "d1_sem_sinal"])
    s = pd.read_json(path, lines=True)
    s = s[s["erro"].isna()].drop_duplicates("item_id", keep="last")
    return s


# ─── pontuação individual em processos paralelos ─────────────────────────

def _pontuar_individual(provider: str, df: pd.DataFrame, out: pathlib.Path,
                        anonimizacao: str = "nenhuma", n_proc: int = N_PROCESSOS) -> dict:
    """Divide ``df`` em ``n_proc`` partes, roda ``scorer.py`` (v1.1, uma notícia
    por chamada) em paralelo, cada parte no seu arquivo (retomável), e junta em
    ``out``. Devolve contagens de válidos e erros."""
    pasta = out.parent / (out.stem + "_partes")
    pasta.mkdir(parents=True, exist_ok=True)
    d = df.sample(frac=1, random_state=SEMENTE).reset_index(drop=True)
    procs = []
    for k in range(n_proc):
        parte = pasta / f"parte_{k}.parquet"
        d.iloc[k::n_proc].to_parquet(parte, index=False)
        cmd = [sys.executable, str(ROOT / "scorer.py"), "--provider", provider, "--mode", "producao",
               "--prompt-versao", "v1.1", "--anonimizacao", anonimizacao,
               "--input", str(parte), "--out", str(pasta / f"parte_{k}.jsonl")]
        procs.append(subprocess.Popen(cmd, cwd=ROOT, stdout=(pasta / f"log_{k}.txt").open("a"),
                                      stderr=subprocess.STDOUT))
    for pr in procs:
        pr.wait()
    linhas = []
    for k in range(n_proc):
        f = pasta / f"parte_{k}.jsonl"
        if f.exists():
            linhas += [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    out.write_text("\n".join(linhas) + ("\n" if linhas else ""), encoding="utf-8")
    v = _validos(out)
    return {"pedidos": len(df), "validos": int(len(v)), "faltando": int(len(df) - len(v)),
            "sem_sinal": int(v["d1_sem_sinal"].eq(True).sum()) if len(v) else 0}


# ─── etapas ──────────────────────────────────────────────────────────────

def etapa_rotulagem(provider: str, n: int = N_ROTULAGEM) -> dict:
    DIR.mkdir(parents=True, exist_ok=True)
    p_ids = DIR / "rotulagem_ids.csv"
    prod = _producao()
    if p_ids.exists():
        ids = pd.read_csv(p_ids)["item_id"].astype(str)
    else:
        ids = prod.sample(n=min(n, len(prod)), random_state=SEMENTE)["item_id"].astype(str)
        ids.to_frame().to_csv(p_ids, index=False)
    df = prod[prod["item_id"].astype(str).isin(set(ids))]
    return _pontuar_individual(provider, df, DIR / "scores_rotulagem.jsonl")


def etapa_filtro(retreinar: bool = False) -> dict:
    from local_encoder import filtro_sinal
    ck = DIR / "filtro"
    if (ck / "filtro_sinal.pt").exists() and not retreinar:
        return json.loads((ck / "metricas_filtro.json").read_text(encoding="utf-8"))
    rot = _validos(DIR / "scores_rotulagem.jsonl")[["item_id", "d1_sem_sinal"]]
    df = _producao().merge(rot, on="item_id")
    df["tem_sinal"] = ~df["d1_sem_sinal"].astype(bool)
    return filtro_sinal.treinar(df, ck)


def etapa_rotear() -> dict:
    from local_encoder import filtro_sinal
    rot_ids = set(pd.read_csv(DIR / "rotulagem_ids.csv")["item_id"].astype(str))
    resto = _producao()
    resto = resto[~resto["item_id"].astype(str).isin(rot_ids)].reset_index(drop=True)
    p, limiar = filtro_sinal.prever(resto, DIR / "filtro")
    rng = np.random.default_rng(SEMENTE)
    decisao = np.where(p >= limiar, "enviado", "descartado")
    desc = np.flatnonzero(decisao == "descartado")
    aud = rng.choice(desc, size=int(round(len(desc) * FRAC_AUDITORIA)), replace=False) if len(desc) else []
    decisao[aud] = "auditado"
    out = pd.DataFrame({"item_id": resto["item_id"], "p_sinal": p, "decisao": decisao, "limiar": limiar})
    out.to_csv(DIR / "roteamento.csv", index=False)
    return out["decisao"].value_counts().to_dict() | {"limiar": limiar}


def etapa_pontuar(provider: str) -> dict:
    r = pd.read_csv(DIR / "roteamento.csv")
    ids = set(r.loc[r["decisao"].isin(["enviado", "auditado"]), "item_id"].astype(str))
    df = _producao()
    df = df[df["item_id"].astype(str).isin(ids)]
    return _pontuar_individual(provider, df, DIR / "scores_roteadas.jsonl")


def etapa_vmin(provider: str, nivel: str = "L5") -> dict:
    """V-min só na amostra ALEATÓRIA de rotulagem (economia): Δt fica estimado
    em ~15% da produção, como no V-min da v1.0."""
    ids = set(_validos(DIR / "scores_rotulagem.jsonl")["item_id"].astype(str))
    df = _producao()
    df = df[df["item_id"].astype(str).isin(ids)]
    return _pontuar_individual(provider, df, DIR / "scores_vmin.jsonl", anonimizacao=nivel)


# ─── consolidação e contagens ────────────────────────────────────────────

def etapa_consolidar(provider: str) -> dict:
    corpus = _corpus()
    prod = _producao()
    rot = _validos(DIR / "scores_rotulagem.jsonl").assign(origem="api_rotulagem")
    rte = _validos(DIR / "scores_roteadas.jsonl")
    r = pd.read_csv(DIR / "roteamento.csv")
    rte = rte.merge(r[["item_id", "decisao"]], on="item_id", how="left")
    rte["origem"] = np.where(rte["decisao"] == "auditado", "api_auditoria", "api_filtro")
    filt = r[r["decisao"] == "descartado"][["item_id"]].assign(
        d1=None, d1_sem_sinal=True, d2=None, d3=None, erro=None, origem="filtro",
        cache_key=lambda d: "filtro|" + d["item_id"].astype(str))
    vmax = pd.concat([rot, rte.drop(columns=["decisao"]), filt], ignore_index=True)
    vmax["variante_vazamento"] = "vmax"
    vmax.to_json(DIR / "consolidado_vmax.jsonl", orient="records", lines=True, force_ascii=False)

    # V-max (inclui as descartadas como sem sinal, para a taxa)
    sc = aggregate.carregar_scores(str(DIR / "consolidado_vmax.jsonl"))
    serie = aggregate.agregar(sc, corpus)
    serie["mes"] = serie["mes"].astype(str)
    serie.to_csv(DERIV / f"indice_mensal_v11_{provider}.csv", index=False)

    # Dupla V-max/V-min (só notícias pontuadas pela API, nas duas variantes)
    vmin = _validos(DIR / "scores_vmin.jsonl")
    if len(vmin):
        api_vmax = vmax[vmax["origem"] != "filtro"]
        comuns = set(api_vmax["item_id"]) & set(vmin["item_id"])
        dup = pd.concat([api_vmax[api_vmax["item_id"].isin(comuns)].assign(variante_vazamento="vmax"),
                         vmin[vmin["item_id"].isin(comuns)].assign(variante_vazamento="vmin")], ignore_index=True)
        dup.to_json(DIR / "consolidado_dupla.jsonl", orient="records", lines=True, force_ascii=False)
        d = aggregate.agregar_vmax_vmin(aggregate.carregar_scores(str(DIR / "consolidado_dupla.jsonl")), corpus)
        d["mes"] = d["mes"].astype(str)
        d.to_csv(DERIV / f"indice_mensal_v11_{provider}_vmax_vmin.csv", index=False)

    cont = contagens(prod, corpus, rot, rte, r)
    (DERIV / "producao_v11_contagens.json").write_text(json.dumps(cont["total"], indent=2, ensure_ascii=False),
                                                       encoding="utf-8")
    cont["mensal"].to_csv(DERIV / "producao_v11_contagens_mensais.csv", index=False)
    return cont["total"]


def contagens(prod, corpus, rot, rte, r) -> dict:
    n_corpus = len(corpus)
    api = pd.concat([rot.assign(grupo="rotulagem"),
                     rte.assign(grupo=np.where(rte["decisao"] == "auditado", "auditado", "enviado"))])
    aud = api[api["grupo"] == "auditado"]
    taxa_sinal_aud = float((~aud["d1_sem_sinal"].astype(bool)).mean()) if len(aud) else float("nan")
    n_desc = int((r["decisao"] == "descartado").sum())
    n_aud = int((r["decisao"] == "auditado").sum())
    erros = int(len(r[r["decisao"].isin(["enviado", "auditado"])]) - len(rte))
    total = {
        "corpus_total": n_corpus,
        "quarentena_excluida": n_corpus - len(prod),
        "producao": len(prod),
        "rotulagem_api": int(len(rot)),
        "filtro_enviadas_api": int((r["decisao"] == "enviado").sum()),
        "filtro_descartadas": n_desc + n_aud,
        "filtro_descartadas_auditadas_api": n_aud,
        "filtro_descartadas_nao_enviadas": n_desc,
        "fracao_producao_nao_enviada": n_desc / len(prod) if len(prod) else float("nan"),
        "api_sem_sinal": int(api["d1_sem_sinal"].astype(bool).sum()),
        "api_com_sinal": int((~api["d1_sem_sinal"].astype(bool)).sum()),
        "erros_ou_faltantes_api": erros,
        "taxa_sinal_na_auditoria": taxa_sinal_aud,
        "sinal_perdido_estimado": taxa_sinal_aud * n_desc if n_desc else 0.0,
        "limiar_filtro": float(r["limiar"].iloc[0]) if len(r) else float("nan"),
    }
    com_sinal_total = total["api_com_sinal"] + total["sinal_perdido_estimado"]
    total["fracao_sinal_perdido_estimada"] = (total["sinal_perdido_estimado"] / com_sinal_total
                                              if com_sinal_total else float("nan"))
    # mensal
    meses = corpus.set_index("item_id")["data_publicacao"]
    mes = lambda ids: pd.to_datetime(meses.reindex(ids).to_numpy(), format="mixed").to_period("M").astype(str)  # noqa: E731
    base = pd.DataFrame({"item_id": prod["item_id"], "mes": mes(prod["item_id"])})
    base = base.merge(r[["item_id", "decisao"]], on="item_id", how="left")
    base["decisao"] = base["decisao"].fillna("rotulagem")
    base = base.merge(api[["item_id", "d1", "d1_sem_sinal"]], on="item_id", how="left")
    base["peso"] = np.where(base["decisao"] == "auditado", 1.0 / FRAC_AUDITORIA, 1.0)
    base["c"] = (pd.to_numeric(base["d1"], errors="coerce") - 1) / 4
    linhas = []
    for m, g in base.groupby("mes"):
        sinal = g.dropna(subset=["c"])
        linhas.append({
            "mes": m, "producao": len(g),
            "enviadas_api": int(g["decisao"].isin(["rotulagem", "enviado", "auditado"]).sum()),
            "descartadas_nao_enviadas": int((g["decisao"] == "descartado").sum()),
            "auditadas": int((g["decisao"] == "auditado").sum()),
            "com_sinal_api": int(len(sinal)),
            "sem_sinal_api": int(g["d1_sem_sinal"].eq(True).sum()),
            "c_llm_simples": float(sinal["c"].mean()) if len(sinal) else np.nan,
            "c_llm_ipw": float(np.average(sinal["c"], weights=sinal["peso"])) if len(sinal) else np.nan,
        })
    return {"total": total, "mensal": pd.DataFrame(linhas)}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("etapa", choices=["rotulagem", "filtro", "rotear", "pontuar", "vmin", "consolidar", "tudo"])
    ap.add_argument("--provider", default="sabia")
    ap.add_argument("--n-rotulagem", type=int, default=N_ROTULAGEM)
    ap.add_argument("--retreinar", action="store_true")
    a = ap.parse_args()
    etapas = ["rotulagem", "filtro", "rotear", "pontuar", "vmin", "consolidar"] if a.etapa == "tudo" else [a.etapa]
    for e in etapas:
        print(f"== {e} ==", flush=True)
        if e == "rotulagem":
            r = etapa_rotulagem(a.provider, a.n_rotulagem)
        elif e == "filtro":
            r = etapa_filtro(a.retreinar)
        elif e == "rotear":
            r = etapa_rotear()
        elif e == "pontuar":
            r = etapa_pontuar(a.provider)
        elif e == "vmin":
            r = etapa_vmin(a.provider)
        else:
            r = etapa_consolidar(a.provider)
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str), flush=True)

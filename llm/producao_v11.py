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
import hashlib
import json
import os
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
# Fontes novas (docs/local 4.2.20): rotulagem por hash com sal próprio, para a
# notícia que chega com a coleta em andamento ter a mesma chance de entrar.
DIR_REF = REPO / "dados" / "llm" / "producao_v11"   # roteamento antigo (Sabiá)
SAL_ROTULAGEM_NOVA = "rotulagem-nova-2026-10-21|"
FRAC_ROTULAGEM_NOVA = 0.15


def _corpus() -> pd.DataFrame:
    return pd.read_parquet(REPO / "dados" / "llm" / "corpus.parquet")


def _producao() -> pd.DataFrame:
    prod, _ = sandbox.separar(_corpus())
    return prod.reset_index(drop=True)


def em_rotulagem_nova(item_id: str) -> bool:
    h = hashlib.sha256((SAL_ROTULAGEM_NOVA + str(item_id)).encode()).hexdigest()
    return int(h[:15], 16) / 16 ** 15 < FRAC_ROTULAGEM_NOVA


def _novas() -> pd.DataFrame:
    """Produção fora da rotulagem e do roteamento antigos (fontes novas e as
    poucas notícias que mudaram de URL na reconstrução do corpus)."""
    antigos = set(pd.read_csv(DIR_REF / "rotulagem_ids.csv")["item_id"].astype(str))
    antigos |= set(pd.read_csv(DIR_REF / "roteamento.csv")["item_id"].astype(str))
    prod = _producao()
    return prod[~prod["item_id"].astype(str).isin(antigos)].reset_index(drop=True)


# Custo por chamada (R$) para a trava de verba (4.2.20, item 7): sabiazinho-4 a
# R$ 1/R$ 3 por milhão de tokens com ~1.000 de entrada e ~40 de saída; Gemini
# pelo gasto real da v1.1 (R$ 48 em 24.068 chamadas), metade em lote.
CUSTO_CHAMADA = {"sabia": 0.0011, "gemini_flash_lite": 0.0020, "gemini_flash_lite_lote": 0.0010}
VERBA = 150.0
INICIO_VERBA = "2026-10-21T11:00:00"   # início do plano 4.2.20
GASTO = DIR_REF / "gasto_estimado.json"
DIR_GEMINI = REPO / "dados" / "llm" / "producao_v11_gemini"


def _chamadas_desde_inicio() -> dict:
    """Chamadas feitas desde INICIO_VERBA, pelo carimbo `ts` de cada nota.
    Individuais: arquivos das partes; lote: linhas com o campo `lote`."""
    n = {"sabia": 0, "gemini_flash_lite": 0, "gemini_flash_lite_lote": 0}
    arquivos = list(DIR_REF.glob("*_partes/parte_*.jsonl")) + list(DIR_GEMINI.glob("*_partes/parte_*.jsonl"))
    arquivos += list(DIR_GEMINI.glob("scores_*.jsonl"))
    for f in arquivos:
        nas_partes = f.parent.name.endswith("_partes")
        for linha in f.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(linha)
            except json.JSONDecodeError:
                continue
            if rec.get("ts", "") < INICIO_VERBA:
                continue
            if nas_partes and "lote" not in rec:
                prov = rec.get("provider", "sabia")
                n[prov] = n.get(prov, 0) + 1
            elif "lote" in rec and not nas_partes:
                n["gemini_flash_lite_lote"] += 1
    lotes = DIR_GEMINI / "lotes_gemini.json"
    if lotes.exists():
        n["gemini_flash_lite_lote"] += sum(len(x["ids"]) for x in json.loads(lotes.read_text(encoding="utf-8"))
                                           if x["status"] == "enviado")
    return n


def _cabe(etapa: str, provider: str, falta: int, lote: bool = False) -> bool:
    """A etapa só roda se o gasto medido + o que ela vai pedir couber na verba."""
    n = _chamadas_desde_inicio()
    gasto = sum(v * CUSTO_CHAMADA.get(k, 0.0) for k, v in n.items())
    custo = falta * CUSTO_CHAMADA[provider + ("_lote" if lote else "")]
    GASTO.write_text(json.dumps({"chamadas_desde_inicio": n, "gasto_estimado": round(gasto, 2),
                                 "proxima_etapa": etapa, "provider": provider, "custo_proxima": round(custo, 2)},
                                indent=1), encoding="utf-8")
    if gasto + custo > VERBA:
        print(f"VERBA: {etapa} ({provider}) custaria R$ {custo:.2f}; gasto estimado R$ {gasto:.2f} de R$ {VERBA:.0f}")
        return False
    return True


def _roteamento() -> pd.DataFrame:
    """Roteamento em vigor: o do filtro único (v2, 4.2.20) se já existe."""
    v2 = DIR_REF / "roteamento_v2.csv"
    return pd.read_csv(v2 if v2.exists() else DIR_REF / "roteamento.csv")


def _ids_rotulagem() -> set:
    ids = set(pd.read_csv(DIR_REF / "rotulagem_ids.csv")["item_id"].astype(str))
    nova = DIR_REF / "rotulagem_nova_ids.csv"
    if (DIR_REF / "roteamento_v2.csv").exists() and nova.exists():
        ids |= set(pd.read_csv(nova)["item_id"].astype(str))
    return ids


def _rotulos(pasta: pathlib.Path) -> pd.DataFrame:
    """Notas da rotulagem em vigor (antiga + nova) do provedor de `pasta`."""
    partes = [_validos(pasta / "scores_rotulagem.jsonl")]
    if (pasta / "scores_rotulagem_nova.jsonl").exists():
        partes.append(_validos(pasta / "scores_rotulagem_nova.jsonl"))
    rot = pd.concat(partes, ignore_index=True).drop_duplicates("item_id", keep="last")
    return rot[rot["item_id"].astype(str).isin(_ids_rotulagem())]


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
    pedidos = len(df)
    # Já pontuadas em QUALQUER parte não voltam à API: com o corpus crescendo,
    # a divisão em partes muda e o cache de cada parte não bastaria.
    feitos = set()
    for f in pasta.glob("parte_*.jsonl"):
        feitos |= set(_validos(f)["item_id"].astype(str))
    df = df[~df["item_id"].astype(str).isin(feitos)]
    d = df.sample(frac=1, random_state=SEMENTE).reset_index(drop=True)
    procs = []
    for k in range(n_proc):
        parte = pasta / f"parte_{k}.parquet"
        if not len(d.iloc[k::n_proc]):
            continue
        d.iloc[k::n_proc].to_parquet(parte, index=False)
        cmd = [sys.executable, str(ROOT / "scorer.py"), "--provider", provider, "--mode", "producao",
               "--prompt-versao", "v1.1", "--anonimizacao", anonimizacao,
               "--input", str(parte), "--out", str(pasta / f"parte_{k}.jsonl")]
        env = dict(os.environ, SCORER_N_PROC=str(n_proc), SCORER_PROC_ID=str(k))
        # Sem janela de console no Windows: uma janela fechada ou um Ctrl+C
        # derrubava todos os processos da pontuação (visto em 2026-10-22).
        procs.append(subprocess.Popen(cmd, cwd=ROOT, stdout=(pasta / f"log_{k}.txt").open("a"),
                                      stderr=subprocess.STDOUT, env=env,
                                      creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)))
    for pr in procs:
        pr.wait()
    linhas = []
    for k in range(n_proc):
        f = pasta / f"parte_{k}.jsonl"
        if f.exists():
            linhas += [l for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    out.write_text("\n".join(linhas) + ("\n" if linhas else ""), encoding="utf-8")
    v = _validos(out)
    return {"pedidos": pedidos, "validos": int(len(v)), "faltando": int(pedidos - len(v)),
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


def etapa_rotulagem_nova(provider: str, lote: bool = False) -> dict:
    """Rotulagem das fontes novas (4.2.20). Pode rodar várias vezes durante a
    coleta: só pontua o que ainda não tem nota. `lote`: Batch API do Gemini."""
    DIR.mkdir(parents=True, exist_ok=True)
    nov = _novas()
    df = nov[nov["item_id"].map(em_rotulagem_nova)]
    df[["item_id", "veiculo"]].to_csv(DIR_REF / "rotulagem_nova_ids.csv", index=False)
    out = DIR / "scores_rotulagem_nova.jsonl"
    feitos = set(_validos(out)["item_id"].astype(str))
    falta = int((~df["item_id"].astype(str).isin(feitos)).sum())
    if falta and not _cabe("rotulagem_nova", provider, falta, lote):
        return {"parado_por_verba": True, "faltando": falta}
    if lote:
        import gemini_batch
        r = gemini_batch.pontuar(provider, df, out)
    else:
        r = _pontuar_individual(provider, df, out)
    return {"novas_producao": len(nov), "sorteadas": len(df), **r,
            "por_veiculo": df["veiculo"].value_counts().to_dict()}


def etapa_filtro(retreinar: bool = False) -> dict:
    from local_encoder import filtro_sinal
    ck = DIR / "filtro"
    if (ck / "filtro_sinal.pt").exists() and not retreinar:
        return json.loads((ck / "metricas_filtro.json").read_text(encoding="utf-8"))
    rot = _validos(DIR / "scores_rotulagem.jsonl")[["item_id", "d1_sem_sinal"]]
    df = _producao().merge(rot, on="item_id")
    df["tem_sinal"] = ~df["d1_sem_sinal"].astype(bool)
    return filtro_sinal.treinar(df, ck)


def etapa_filtro_v2() -> dict:
    """Filtro único (4.2.20): rótulos do Sabiá, rotulagem antiga + nova."""
    from local_encoder import filtro_sinal
    ck = DIR_REF / "filtro_v2"
    if (ck / "filtro_sinal.pt").exists():
        return json.loads((ck / "metricas_filtro.json").read_text(encoding="utf-8"))
    ids = set(pd.read_csv(DIR_REF / "rotulagem_ids.csv")["item_id"].astype(str))
    ids |= set(pd.read_csv(DIR_REF / "rotulagem_nova_ids.csv")["item_id"].astype(str))
    rot = pd.concat([_validos(DIR_REF / "scores_rotulagem.jsonl"),
                     _validos(DIR_REF / "scores_rotulagem_nova.jsonl")]).drop_duplicates("item_id", keep="last")
    rot = rot[rot["item_id"].astype(str).isin(ids)][["item_id", "d1_sem_sinal"]]
    df = _producao().merge(rot, on="item_id")
    df["tem_sinal"] = ~df["d1_sem_sinal"].astype(bool)
    return filtro_sinal.treinar(df, ck)


def etapa_rotear_v2() -> dict:
    """O filtro único vale para a produção inteira; sorteio novo da auditoria."""
    from local_encoder import filtro_sinal
    rot_ids = set(pd.read_csv(DIR_REF / "rotulagem_ids.csv")["item_id"].astype(str))
    rot_ids |= set(pd.read_csv(DIR_REF / "rotulagem_nova_ids.csv")["item_id"].astype(str))
    resto = _producao()
    resto = resto[~resto["item_id"].astype(str).isin(rot_ids)].reset_index(drop=True)
    p, limiar = filtro_sinal.prever(resto, DIR_REF / "filtro_v2")
    rng = np.random.default_rng(SEMENTE)
    decisao = np.where(p >= limiar, "enviado", "descartado")
    desc = np.flatnonzero(decisao == "descartado")
    aud = rng.choice(desc, size=int(round(len(desc) * FRAC_AUDITORIA)), replace=False) if len(desc) else []
    decisao[aud] = "auditado"
    out = pd.DataFrame({"item_id": resto["item_id"], "veiculo": resto["veiculo"], "p_sinal": p,
                        "decisao": decisao, "limiar": limiar})
    out.to_csv(DIR_REF / "roteamento_v2.csv", index=False)
    antigo = pd.read_csv(DIR_REF / "roteamento.csv")[["item_id", "decisao"]]
    troca = out.merge(antigo, on="item_id", suffixes=("", "_v1"))
    return {**out["decisao"].value_counts().to_dict(), "limiar": limiar,
            "antigas_v1_para_v2": pd.crosstab(troca["decisao_v1"], troca["decisao"]).to_dict()}


SAL_AUDITORIA_INCREMENTAL = "auditoria-incremental-2026-10-21|"


def etapa_rotear_incremental() -> dict:
    """Notícias que chegaram depois do treino do filtro único (adendo de
    2026-10-21 a 4.2.20): o MESMO filtro, congelado, sem retreino. A auditoria
    das descartadas é sorteada por hash (10%), porque o lote chega aos poucos."""
    from local_encoder import filtro_sinal
    r = pd.read_csv(DIR_REF / "roteamento_v2.csv")
    fora = set(r["item_id"].astype(str)) | _ids_rotulagem()
    novos = _producao()
    novos = novos[~novos["item_id"].astype(str).isin(fora)].reset_index(drop=True)
    if not len(novos):
        return {"novos": 0}
    p, limiar = filtro_sinal.prever(novos, DIR_REF / "filtro_v2")
    aud = novos["item_id"].astype(str).map(lambda i: int(hashlib.sha256((SAL_AUDITORIA_INCREMENTAL + i).encode())
                                                      .hexdigest()[:15], 16) / 16 ** 15 < FRAC_AUDITORIA)
    decisao = np.where(p >= limiar, "enviado", np.where(aud, "auditado", "descartado"))
    out = pd.DataFrame({"item_id": novos["item_id"], "veiculo": novos["veiculo"], "p_sinal": p,
                        "decisao": decisao, "limiar": limiar, "lote_roteamento": "incremental"})
    pd.concat([r, out], ignore_index=True).to_csv(DIR_REF / "roteamento_v2.csv", index=False)
    return {"novos": len(out), **out["decisao"].value_counts().to_dict(),
            "por_veiculo": out["veiculo"].value_counts().to_dict()}


def etapa_pontuar_v2(provider: str, lote: bool = False) -> dict:
    r = _roteamento()
    ids = set(r.loc[r["decisao"].isin(["enviado", "auditado"]), "item_id"].astype(str))
    df = _producao()
    df = df[df["item_id"].astype(str).isin(ids)]
    out = DIR / "scores_roteadas.jsonl"
    feitos = set(_validos(out)["item_id"].astype(str))
    falta = int((~df["item_id"].astype(str).isin(feitos)).sum())
    if falta and not _cabe("pontuar_v2", provider, falta, lote):
        return {"parado_por_verba": True, "faltando": falta}
    if lote:
        import gemini_batch
        return gemini_batch.pontuar(provider, df, out)
    return _pontuar_individual(provider, df, out)


def etapa_vmin_v2(provider: str, nivel: str = "L5") -> dict:
    """V-min só nas notícias com sinal no V-max (4.2.20, item 6)."""
    r = _roteamento()
    enviados = set(r.loc[r["decisao"].isin(["enviado", "auditado"]), "item_id"].astype(str))
    rte = _validos(DIR / "scores_roteadas.jsonl")
    api = pd.concat([_rotulos(DIR), rte[rte["item_id"].astype(str).isin(enviados)]])
    com_sinal = set(api.loc[~api["d1_sem_sinal"].astype(bool), "item_id"].astype(str))
    df = _producao()
    df = df[df["item_id"].astype(str).isin(com_sinal)]
    feitos = set(_validos(DIR / "scores_vmin.jsonl")["item_id"].astype(str))
    falta = int((~df["item_id"].astype(str).isin(feitos)).sum())
    if falta and not _cabe("vmin_v2", provider, falta):
        return {"parado_por_verba": True, "faltando": falta}
    return _pontuar_individual(provider, df, DIR / "scores_vmin.jsonl", anonimizacao=nivel)


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
    rot = _rotulos(DIR).assign(origem="api_rotulagem")
    r = _roteamento()
    # só as notas de notícias que o roteamento em vigor manda à API: a nota
    # antiga de uma notícia que o filtro único descarta não entra (4.2.20, item 4)
    rte = _validos(DIR / "scores_roteadas.jsonl").merge(
        r.loc[r["decisao"].isin(["enviado", "auditado"]), ["item_id", "decisao"]], on="item_id", how="inner")
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
    jm = aggregate.agregar_janela_movel(sc, corpus, 3)  # regra de 2026-10-19 (docs/local 4.2.14)
    jm["mes"] = jm["mes"].astype(str)
    jm.to_csv(DERIV / f"indice_mensal_v11_{provider}_jm3.csv", index=False)

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
    suf = "" if provider == "sabia" else f"_{provider}"  # Sabiá mantém os nomes já publicados
    (DERIV / f"producao_v11_contagens{suf}.json").write_text(json.dumps(cont["total"], indent=2, ensure_ascii=False),
                                                             encoding="utf-8")
    cont["mensal"].to_csv(DERIV / f"producao_v11_contagens_mensais{suf}.csv", index=False)
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
    ap.add_argument("etapa", choices=["rotulagem", "rotulagem_nova", "filtro", "rotear", "pontuar", "vmin",
                                      "filtro_v2", "rotear_v2", "rotear_incremental", "pontuar_v2", "vmin_v2",
                                      "consolidar", "tudo"])
    ap.add_argument("--lote", action="store_true", help="Gemini: Batch API (50% mais barato, até 24 h)")
    ap.add_argument("--provider", default="sabia")
    ap.add_argument("--n-rotulagem", type=int, default=N_ROTULAGEM)
    ap.add_argument("--retreinar", action="store_true")
    ap.add_argument("--dir", default=None,
                    help="pasta de trabalho (outro provedor: copie rotulagem_ids.csv e roteamento.csv "
                         "da pasta do Sabiá para reusar a amostra e o filtro)")
    a = ap.parse_args()
    if a.dir:
        DIR = pathlib.Path(a.dir)
    etapas = ["rotulagem", "filtro", "rotear", "pontuar", "vmin", "consolidar"] if a.etapa == "tudo" else [a.etapa]
    for e in etapas:
        print(f"== {e} ==", flush=True)
        if e == "rotulagem":
            r = etapa_rotulagem(a.provider, a.n_rotulagem)
        elif e == "rotulagem_nova":
            r = etapa_rotulagem_nova(a.provider, a.lote)
        elif e == "filtro_v2":
            r = etapa_filtro_v2()
        elif e == "rotear_v2":
            r = etapa_rotear_v2()
        elif e == "rotear_incremental":
            r = etapa_rotear_incremental()
        elif e == "pontuar_v2":
            r = etapa_pontuar_v2(a.provider, a.lote)
        elif e == "vmin_v2":
            r = etapa_vmin_v2(a.provider)
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

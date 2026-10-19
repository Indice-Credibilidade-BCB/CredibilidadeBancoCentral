# -*- coding: utf-8 -*-
"""Agregação mensal do índice (spec travada na Seção 4.2 + extensões da
auditoria de 2026-08-18).

Passos:
  1. Reescala item: c = (d1 - 1)/4  em [0,1].
  2. Colapsa clusters wire: mesma matéria de agência em vários veículos conta
     UMA vez por (mês, cluster) — média dentro do cluster.
  3. Efeito fixo de tipo de veículo estimado por DEMEANING ITERATIVO
     (projeções alternadas mês x tipo). O demeaning de uma passada só é
     exato em painel balanceado; como research entra tarde no corpus e há
     meses só de imprensa, iterar até convergir evita contaminar gamma com
     efeito-época. gamma é normalizado com PESOS de participação global
     (sum w_v * gamma_v = 0), preservando o nível médio do índice em [0,1].
  4. Índice mensal = média simples dos itens ajustados; mediana como robustez.
  5. Banda de incerteza: ep clusterizado por DIA (rajadas de cobertura em
     dias de Copom violam independência item a item; a unidade de erro é a
     média diária). ep_iid = dp/sqrt(n) reportado como referência.
  6. Séries auxiliares: d2/d3 médios e taxa de sem_sinal por mês (o
     "sem sinal" não é aleatório — some em crise, cresce na calmaria — e por
     isso vira série observável, não faltante ignorado).

Entrada: JSONL do scorer + corpus (p/ data, veículo, tipo, wire_cluster).
Saída: CSV mensal.
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np
import pandas as pd

import sandbox
import schema


def carregar_scores(jsonl_path: str) -> pd.DataFrame:
    recs = [json.loads(l) for l in
            pathlib.Path(jsonl_path).read_text(encoding="utf-8").splitlines()]
    df = pd.DataFrame(recs)
    # Reexecuções reprocessam itens que falharam: pode haver mais de uma linha
    # por cache_key. Mantém a ÚLTIMA com d1 válido.
    # v1.1: d1 nulo com d1_sem_sinal = True é resposta válida (texto sem sinal
    # sobre a meta) — fica para a taxa de sem-sinal, mas fora da média.
    sem = df["d1_sem_sinal"].eq(True) if "d1_sem_sinal" in df.columns else False
    df = df[df["d1"].notna() | sem]
    if "cache_key" in df.columns:
        df = df.drop_duplicates(subset="cache_key", keep="last")
    cols = ["item_id", "d1", "d1_sem_sinal", "d2", "d3", "provider", "model", "prompt_version",
            "variante_vazamento"]  # D12: presente só quando o scorer rodou dupla_vmax_vmin
    return df[[c for c in cols if c in df.columns]]


def _fe_tipo_iterativa(df: pd.DataFrame, tol: float = 1e-10,
                       max_iter: int = 200) -> pd.Series:
    """Efeitos de tipo_veiculo em modelo c = alpha_mes + gamma_tipo + e,
    por projeções alternadas (Gauss–Seidel); exato mesmo desbalanceado."""
    y = df["c"].to_numpy(float)
    mes = df["mes"].to_numpy()
    tipo = df["tipo_veiculo"].to_numpy()
    alpha = pd.Series(0.0, index=pd.unique(mes))
    gamma = pd.Series(0.0, index=pd.unique(tipo))
    for _ in range(max_iter):
        res_m = pd.Series(y - gamma[tipo].to_numpy(), index=mes)
        alpha_new = res_m.groupby(level=0).mean()
        res_t = pd.Series(y - alpha_new[mes].to_numpy(), index=tipo)
        gamma_new = res_t.groupby(level=0).mean()
        # normalização ponderada pela participação global de cada tipo
        w = pd.Series(tipo).value_counts(normalize=True)
        gamma_new = gamma_new - (gamma_new * w).sum()
        delta = (gamma_new - gamma.reindex(gamma_new.index).fillna(0)).abs().max()
        alpha, gamma = alpha_new, gamma_new
        if delta < tol:
            break
    return gamma


def agregar(scores: pd.DataFrame, corpus: pd.DataFrame) -> pd.DataFrame:
    """Agregação de UMA série (o caso de sempre: um scorer sem
    `dupla_vmax_vmin`). Para a série dupla V-max/V-min de D12, ver
    `agregar_vmax_vmin`."""
    if "variante_vazamento" in scores.columns:
        vals = set(scores["variante_vazamento"].dropna().unique())
        if len(vals) > 1:
            # Sem esta guarda, vmax e vmin do MESMO item entrariam juntos na
            # mesma média mensal — dobra a contagem de itens e mistura as
            # duas variantes de vazamento numa série sem sentido, em silêncio.
            raise ValueError(
                "scores contém mais de uma variante_vazamento (vmax/vmin) — "
                "use agregar_vmax_vmin() em vez de agregar()")
    return _agregar_core(scores, corpus)


def agregar_janela_movel(scores: pd.DataFrame, corpus: pd.DataFrame, janela: int = 3) -> pd.DataFrame:
    """Série mensal em JANELA MÓVEL PARA TRÁS (decidida em 2026-10-19, antes de
    rodar o Bloco 3): o valor do mês t junta as notícias de t−(janela−1) a t
    e tira UMA média — soma as notícias, não faz média de médias, para que
    um mês com 3 notícias não pese igual a um com 80. Só olha para trás: o
    mês t nunca usa informação de t+1 (sem look-ahead).

    Mesmo núcleo da série mensal (colapso wire, FE de tipo, EP por dia), com
    cada notícia contada nas `janela` janelas que a contêm. Colunas extras:
    ``janela`` e ``meses_na_janela`` (< janela nos primeiros meses do corpus).
    """
    out = _agregar_core(scores, corpus, janela=janela)
    out["janela"] = janela
    return out


def _agregar_core(scores: pd.DataFrame, corpus: pd.DataFrame, janela: int = 1) -> pd.DataFrame:
    corpus = schema.dedup(schema.validate(corpus))
    df = scores.merge(
        corpus[["item_id", "data_publicacao", "tipo_veiculo", "wire_cluster"]],
        on="item_id", how="inner")
    df["dia"] = pd.to_datetime(df["data_publicacao"])
    df["mes"] = df["dia"].dt.to_period("M")
    if janela > 1:
        # cada notícia entra na janela do próprio mês e das (janela−1) seguintes
        primeiro, ultimo = df["mes"].min(), df["mes"].max()
        df = pd.concat([df.assign(mes=df["mes"] + k) for k in range(janela)], ignore_index=True)
        df = df[df["mes"] <= ultimo]
        meses_na_janela = {m: min(janela, (m - primeiro).n + 1) for m in df["mes"].unique()}
    df["c"] = (pd.to_numeric(df["d1"], errors="coerce") - 1) / 4.0
    for d in ("d2", "d3"):
        if d in df.columns:
            df[d] = pd.to_numeric(df[d], errors="coerce")
            df[f"{d}_sem_sinal"] = df[d].isna()
    # Taxa de itens SEM sinal sobre a meta (v1.1), antes de descartá-los da média.
    tem_sem_sinal = "d1_sem_sinal" in df.columns and df["d1_sem_sinal"].notna().any()
    if tem_sem_sinal:
        flag = df["d1_sem_sinal"].eq(True)
        taxa_d1 = flag.groupby(df["mes"]).mean()
        n_total = df.groupby("mes").size()
    df = df.dropna(subset=["c"])

    # (2) colapsa wire: 1 observação por (mês, cluster)
    agg_map = {"c": ("c", "mean"), "dia": ("dia", "min")}
    for d in ("d2", "d3"):
        if d in df.columns:
            agg_map[d] = (d, "mean")
            agg_map[f"{d}_sem_sinal"] = (f"{d}_sem_sinal", "mean")
    df = (df.groupby(["mes", "wire_cluster", "tipo_veiculo"], as_index=False)
            .agg(**agg_map))

    # (3) FE de tipo de veículo (iterativa; ver docstring)
    gamma = _fe_tipo_iterativa(df)
    df["c_aj"] = df["c"] - df["tipo_veiculo"].map(gamma).astype(float)

    # (4)-(5) índice mensal + bandas
    linhas = []
    for mes, g in df.groupby("mes"):
        medias_dia = g.groupby(g["dia"].dt.date)["c_aj"].mean()
        n_dias = len(medias_dia)
        ep_dia = (medias_dia.std(ddof=1) / np.sqrt(n_dias)
                  if n_dias > 1 else np.nan)
        linha = {
            "mes": mes,
            "c_llm": g["c_aj"].mean(),
            "c_llm_mediana": g["c_aj"].median(),
            "ep": ep_dia,                       # oficial: cluster por dia
            "ep_iid": (g["c_aj"].std(ddof=1) / np.sqrt(len(g))
                       if len(g) > 1 else np.nan),
            "n_itens": len(g),
            "n_dias": n_dias,
        }
        for d in ("d2", "d3"):
            if d in g.columns:
                linha[f"{d}_media"] = g[d].mean()
                linha[f"taxa_{d}_sem_sinal"] = g[f"{d}_sem_sinal"].mean()
        linhas.append(linha)
    out = pd.DataFrame(linhas)
    if janela > 1:
        out["meses_na_janela"] = out["mes"].map(meses_na_janela)
    if tem_sem_sinal:
        out["taxa_d1_sem_sinal"] = out["mes"].map(taxa_d1)
        out["n_itens_total"] = out["mes"].map(n_total)
    # O ajuste aditivo de FE pode extrapolar [0,1] em meses ralos (poucos
    # itens). NÃO truncar a série usada nos Blocos 2/3/6: censurar nas
    # bordas atenuaria a variância exatamente nos episódios extremos, que
    # são o sinal de interesse (a logística Λ do projeto vive no ESTADO
    # latente do Kalman, não neste proxy). c_llm_trunc existe só p/ leitura.
    out["c_llm_trunc"] = out["c_llm"].clip(0, 1)
    return out


# ---------------------------------------------------------------------------
# D12/pendência 8 — série dupla V-max/V-min e Δt como série própria.
#
# Exige que `scores` tenha a coluna `variante_vazamento` (só existe quando o
# scorer rodou com --dupla-vmax-vmin). Agrega CADA variante pelo mesmo núcleo
# (mesma FE de tipo, mesmo cluster wire) e depois junta por mês. V-max é a
# série PRINCIPAL (D12; `c_llm` replica `c_llm_vmax` por conveniência de quem
# só quer uma coluna); V-min é a robustez obrigatória; Δt = vmax - vmin vira
# número publicável, não ressalva retórica.
# ---------------------------------------------------------------------------

def agregar_vmax_vmin(scores: pd.DataFrame, corpus: pd.DataFrame) -> pd.DataFrame:
    if "variante_vazamento" not in scores.columns:
        raise ValueError(
            "scores sem coluna 'variante_vazamento' — rode o scorer com "
            "--dupla-vmax-vmin, ou use agregar() para série única")
    faltando = {"vmax", "vmin"} - set(scores["variante_vazamento"].dropna().unique())
    if faltando:
        raise ValueError(f"variante(s) ausente(s) em scores: {faltando}")

    def _preparar(variante: str) -> pd.DataFrame:
        sub = scores[scores["variante_vazamento"] == variante].drop(
            columns=["variante_vazamento"])
        r = _agregar_core(sub, corpus)
        return r.rename(columns={c: f"{c}_{variante}" for c in r.columns if c != "mes"})

    vmax = _preparar("vmax")
    vmin = _preparar("vmin")
    out = vmax.merge(vmin, on="mes", how="outer").sort_values("mes")
    out["c_llm"] = out["c_llm_vmax"]  # alias: V-max é a série principal (D12)
    out["delta_t"] = out["c_llm_vmax"] - out["c_llm_vmin"]
    return out.reset_index(drop=True)


def excluir_sandbox(scores: pd.DataFrame, manifesto: set | None = None) -> pd.DataFrame:
    """Remove os itens da quarentena de desenvolvimento (D13).

    A série de produção NUNCA inclui a quarentena: esses itens são usados para
    iterar prompt e regras, e deixá-los na série publicada permitiria que a
    calibração "visse" o agregado. Usa o manifesto congelado
    (`sandbox.congelar_manifesto`); sem manifesto, cai para a regra de hash,
    que é a mesma que gerou o manifesto.
    """
    ids = manifesto if manifesto is not None else sandbox.carregar_manifesto()
    if ids:
        mask = scores["item_id"].astype(str).isin(ids)
    else:
        mask = scores["item_id"].astype(str).map(sandbox.em_sandbox)
    return scores.loc[~mask].copy()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scores", required=True)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--incluir-sandbox", action="store_true",
                    help="NÃO usar em produção: inclui os itens da quarentena (D13)")
    a = ap.parse_args()
    corpus = (pd.read_parquet(a.corpus) if a.corpus.endswith(".parquet")
              else pd.read_csv(a.corpus))
    scores = carregar_scores(a.scores)
    if not a.incluir_sandbox:
        n0 = len(scores)
        scores = excluir_sandbox(scores)
        print(f"Quarentena (D13): {n0 - len(scores)} linhas de itens em sandbox excluídas.")
    if "variante_vazamento" in scores.columns and \
            set(scores["variante_vazamento"].dropna().unique()) >= {"vmax", "vmin"}:
        out = agregar_vmax_vmin(scores, corpus)
        print("Série dupla V-max/V-min detectada (D12).")
    else:
        out = agregar(scores, corpus)
    out.to_csv(a.out, index=False)
    print(f"Índice mensal salvo em {a.out}")

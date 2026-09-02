# -*- coding: utf-8 -*-
"""T0 — sonda de identificabilidade temporal (D11/4.2.3).

Lógica pura (sem chamada de API) usada por `../t0_probe.py`, que faz o
round-trip com o provedor. Separado assim pelo mesmo motivo de
`diagnostics/leakage.py`: a parte estatística tem que ser testável sem rede
nem chave.

Protocolo: sobre o item mascarado no nível candidato, pedir o ano de
publicação com intervalo, em chamada SEPARADA da pontuação de credibilidade
(perguntar os dois juntos deixaria o modelo "ancorar" a nota no ano que ele
mesmo acabou de estimar). Métricas:

  EAM        erro absoluto médio em anos (|ano_estimado - ano_real|)
  acurácia   fração em que o episódio atribuído (ver config.pilot.strata)
             bate com o episódio real, contra a taxa-base 1/n_estratos

Critério de cegueira (pré-registrado): EAM >= 4 anos E acurácia <= 0,25.
T0 roda em escada L1 -> L2 -> L3 -> L4; o MENOR nível que atinge cegueira
define a variante V-min de produção (D12).
"""
from __future__ import annotations

import pathlib

import pandas as pd
import yaml

ROOT = pathlib.Path(__file__).parent.parent
NIVEIS_ESCADA = ("L1", "L2", "L3", "L4")

EAM_MIN_CEGUEIRA = 4.0
ACC_MAX_CEGUEIRA = 0.25


def _cfg() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def _janelas_estrato(estrato: dict) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    janelas = estrato.get("windows") or [[estrato["start"], estrato["end"]]]
    return [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in janelas]


def episodio_de(data, strata: list[dict] | None = None) -> str | None:
    """Mapeia uma data ao rótulo do estrato (config.pilot.strata) que a
    contém. None se a data não cai em nenhuma janela (fora do desenho do
    piloto) — esses itens são descartados do cálculo de acurácia, não
    contados como erro."""
    strata = strata if strata is not None else _cfg()["pilot"]["strata"]
    d = pd.Timestamp(data)
    for estrato in strata:
        for ini, fim in _janelas_estrato(estrato):
            if ini <= d <= fim:
                return estrato["label"]
    return None


def taxa_base_episodios(strata: list[dict] | None = None) -> float:
    strata = strata if strata is not None else _cfg()["pilot"]["strata"]
    return 1.0 / len(strata) if strata else float("nan")


def avaliar_t0(respostas: pd.DataFrame, strata: list[dict] | None = None) -> dict:
    """respostas: colunas item_id, ano_estimado, ano_real (ou
    data_publicacao_real, convertida para ano). Uma linha por item, JÁ para
    um único nível de anonimização — chamar uma vez por nível e comparar.
    """
    strata = strata if strata is not None else _cfg()["pilot"]["strata"]
    df = respostas.copy()
    if "ano_real" not in df.columns:
        df["ano_real"] = pd.to_datetime(df["data_publicacao_real"]).dt.year
    df["ano_estimado"] = pd.to_numeric(df["ano_estimado"], errors="coerce")
    ok = df["ano_estimado"].notna()
    n = int(ok.sum())
    if n == 0:
        return {"n": 0, "eam": float("nan"), "acuracia_episodio": float("nan"),
               "taxa_base": taxa_base_episodios(strata), "cego": False,
               "obs": "nenhuma resposta parseável"}

    eam = float((df.loc[ok, "ano_estimado"] - df.loc[ok, "ano_real"]).abs().mean())

    dat_col = "data_publicacao_real" if "data_publicacao_real" in df.columns else None
    if dat_col:
        ep_real = df[dat_col].map(lambda d: episodio_de(d, strata))
        # ano estimado -> ponto médio do ano (1º de julho) para mapear a estrato
        ep_pred = df["ano_estimado"].map(
            lambda a: episodio_de(f"{int(a)}-07-01", strata) if pd.notna(a) else None)
        okk = ep_real.notna() & ep_pred.notna()
        acc = (float((ep_real[okk] == ep_pred[okk]).mean())
               if int(okk.sum()) > 0 else float("nan"))
    else:
        acc = float("nan")

    taxa_base = taxa_base_episodios(strata)
    cego = bool(eam >= EAM_MIN_CEGUEIRA and (pd.isna(acc) or acc <= ACC_MAX_CEGUEIRA))
    return {"n": n, "eam": eam, "acuracia_episodio": acc, "taxa_base": taxa_base,
           "cego": cego}


def nivel_minimo_cego(resultados_por_nivel: dict[str, dict],
                      ordem: tuple = NIVEIS_ESCADA) -> str | None:
    """resultados_por_nivel: {nivel: saida_de_avaliar_t0}. Retorna o PRIMEIRO
    nível da escada (L1 antes de L4) que atinge cegueira — é o nível mínimo
    de mascaramento e vira a variante V-min de produção (D12). None se
    nenhum nível cegou: T0 reprovou, revisar a escada antes da Etapa 3."""
    for nivel in ordem:
        r = resultados_por_nivel.get(nivel)
        if r and r.get("cego"):
            return nivel
    return None

# -*- coding: utf-8 -*-
"""Atualiza todos os dados da "lista 2" (essenciais e de validação) e imprime o estado.

    python -m mercado.lista2                # usa caches onde houver; ANBIMA sempre tenta a janela
    python -m mercado.lista2 --atualizar    # baixa tudo de novo

| Dado                                   | Fonte                      | Saída                                                   |
|----------------------------------------|----------------------------|---------------------------------------------------------|
| Focus — mediana IPCA 12m + dispersão   | BCB Olinda (Expectativas)  | dados/macro/focus_ipca_12m_{suav,nsuav}.csv + _mensal   |
| Metas históricas de inflação           | BCB SGS 13521 + CMN        | dados/macro/metas_inflacao_historico.csv                |
| Selic-meta histórica                   | BCB SGS 432 + Copom        | dados/macro/selic_meta.csv, reunioes_copom.csv          |
| Calendário Copom × vencimentos DI1     | BCB + regra B3 + ANBIMA    | dados/mercado/calendario_copom_di1.csv                  |
| Vencimentos genéricos DI1 (1º–4º)      | regra B3 + feriados ANBIMA | dados/mercado/di1_vencimentos_genericos.csv             |
| Curvas nominal/real, inflação implícita| Tesouro Direto (2004–)     | dados/mercado/curvas_tesouro_direto_diario.csv, ...     |
|                                        | ANBIMA ETTJ (janela 1 mês) | dados/mercado/anbima/*.csv (cumulativo)                 |
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from validacao import dados_bcb
from validacao.dados_bcb import BANDA_TOLERANCIA, DIR_MACRO

from . import anbima, b3_taxas, calendario, inflacao_implicita

# Metas revistas pelo CMN depois de fixadas (valor original -> o SGS traz o revisto).
META_ORIGINAL = {2003: 3.25, 2004: 3.75}
# Meta ajustada anunciada pelo BCB na carta aberta de jan/2003 (referência operacional, não a meta do CMN).
META_AJUSTADA_BCB = {2003: 8.5, 2004: 5.5}


def metas_historico(atualizar: bool = False) -> pd.DataFrame:
    """Meta, banda, limites, IPCA do ano e cumprimento, por ano-calendário."""
    meta = dados_bcb.sgs("meta_inflacao", atualizar=atualizar)
    ipca12 = dados_bcb.sgs("ipca_12m", atualizar=atualizar)
    dez = ipca12[ipca12.index.month == 12]
    linhas = []
    for d, m in meta.items():
        a = d.year
        b = BANDA_TOLERANCIA.get(a, 1.5)
        lo, hi = float(m) - b, float(m) + b
        ipca = dez[dez.index.year == a]
        ipca = float(ipca.iloc[0]) if len(ipca) else np.nan
        continua = a >= 2025
        if continua:
            # Meta contínua (Decreto 12.079/2024): descumprimento = IPCA 12m fora da banda
            # por 6 meses consecutivos. Avalia as sequências que terminam dentro do ano.
            fora = ((ipca12 < lo) | (ipca12 > hi)).astype(int)
            seq = fora.groupby((fora != fora.shift()).cumsum()).cumsum() * fora
            no_ano = seq[seq.index.year == a]
            cumpriu = (bool((no_ano < 6).all()) if len(no_ano) else np.nan)
            meses_fora = int(fora[fora.index.year == a].sum()) if len(no_ano) else np.nan
        else:
            cumpriu = bool(lo <= ipca <= hi) if np.isfinite(ipca) else np.nan
            meses_fora = np.nan
        fechado = pd.Timestamp(a, 12, 1) <= ipca12.index.max()
        linhas.append({
            "ano": a, "ano_fechado": bool(fechado), "meta": float(m), "banda": b, "limite_inferior": lo, "limite_superior": hi,
            "meta_original_cmn": META_ORIGINAL.get(a, float(m)), "meta_ajustada_bcb": META_AJUSTADA_BCB.get(a, np.nan),
            "regime": "meta contínua" if continua else "ano-calendário",
            "ipca_dezembro_12m": ipca,
            "cumpriu": cumpriu if fechado or continua else np.nan, "meses_fora_da_banda": meses_fora,
            "desvio_pp": ipca - float(m) if np.isfinite(ipca) else np.nan,
        })
    df = pd.DataFrame(linhas)
    df.to_csv(DIR_MACRO / "metas_inflacao_historico.csv", index=False)
    return df


def focus_mensal(atualizar: bool = False) -> pd.DataFrame:
    """Focus IPCA 12m (suavizada e não suavizada) em frequência mensal, com dispersão."""
    partes = []
    for suav in (True, False):
        f = dados_bcb.focus_ipca_12m(atualizar=atualizar, suavizada=suav).set_index("Data").sort_index()
        f["amplitude"] = f["Maximo"] - f["Minimo"]
        g = f.resample("MS")
        suf = "suav" if suav else "nsuav"
        partes.append(pd.DataFrame({
            f"mediana_media_{suf}": g["Mediana"].mean(), f"mediana_fim_{suf}": g["Mediana"].last(),
            f"desvio_padrao_{suf}": g["DesvioPadrao"].mean(), f"amplitude_{suf}": g["amplitude"].mean(),
            f"n_respondentes_{suf}": g["numeroRespondentes"].mean(),
        }))
    m = pd.concat(partes, axis=1)
    m.index = m.index.to_period("M"); m.index.name = "mes"
    m.to_csv(DIR_MACRO / "focus_ipca_12m_mensal.csv")
    return m


def rodar(atualizar: bool = False) -> pd.DataFrame:
    status = []

    def ok(dado, fonte, saida, n, ini, fim, obs=""):
        status.append({"dado": dado, "fonte": fonte, "saida": saida, "n": n, "inicio": ini, "fim": fim, "obs": obs})

    # 1) Focus mediana + dispersão
    fm = focus_mensal(atualizar)
    ok("Focus IPCA 12m (mediana + dispersão)", "BCB Olinda", "dados/macro/focus_ipca_12m_mensal.csv",
       len(fm), str(fm.index.min()), str(fm.index.max()), "diário em focus_ipca_12m_suav/_nsuav.csv")
    # 2) Metas
    mt = metas_historico(atualizar)
    ok("Metas históricas de inflação", "SGS 13521 + CMN", "dados/macro/metas_inflacao_historico.csv",
       len(mt), str(mt.ano.min()), str(mt.ano.max()), f"cumpriu em {int(mt.loc[mt.ano_fechado, 'cumpriu'].sum())} de {int(mt.ano_fechado.sum())} anos fechados; {int(mt.loc[mt.ano_fechado, 'ano'].count() - mt.loc[mt.ano_fechado, 'cumpriu'].sum())} descumprimentos")
    # 3) Selic-meta + Copom
    sm = dados_bcb.sgs("selic_meta", atualizar=atualizar)
    rc = dados_bcb.reunioes_copom(atualizar=atualizar)
    ok("Selic-meta histórica (diária)", "SGS 432", "dados/macro/selic_meta.csv", len(sm),
       str(sm.index.min().date()), str(sm.index.max().date()))
    ok("Decisões do Copom", "BCB histórico de taxas", "dados/macro/reunioes_copom.csv", len(rc),
       str(rc.data_reuniao.min().date()), str(rc.data_reuniao.max().date()))
    # 4) Calendário Copom × DI1 + genéricos (agenda oficial do BCB inclui as reuniões futuras)
    calendario.feriados_anbima(atualizar=atualizar)
    calendario.feriados.cache_clear()
    ag = calendario.agenda_copom_bcb(atualizar=True)
    futuras = ag[ag.data_reuniao > rc.data_reuniao.max()]
    ok("Agenda do Copom (inclui futuras)", "BCB — agenda 'Reuniões do Copom'", "dados/mercado/copom_agenda.csv",
       len(ag), str(ag.data_reuniao.min().date()), str(ag.data_reuniao.max().date()),
       f"{len(futuras)} reuniões futuras: " + ", ".join(str(d.date()) for d in futuras.data_reuniao.head(3)) + ("…" if len(futuras) > 3 else ""))
    cal = calendario.salvar_calendario()
    ok("Calendário Copom × DI1", "BCB + regra B3 + feriados ANBIMA", "dados/mercado/calendario_copom_di1.csv",
       len(cal), str(cal.data_reuniao.min().date()), str(cal.data_reuniao.max().date()),
       f"{int(cal.kuttner_curto_demais.sum())} reuniões com contrato curto < 5 DU; "
       f"{int((cal.kuttner_atravessa_proxima == True).sum())} com contrato curto atravessando a próxima reunião")  # noqa: E712
    gen = calendario.tabela_vencimentos_genericos("2001-01-01", pd.Timestamp.today().strftime("%Y-%m-%d"))
    gen.to_csv(calendario.DIR_MERCADO / "di1_vencimentos_genericos.csv", index=False, date_format="%Y-%m-%d")
    ok("DI1 1º–4º vencimento por dia útil", "regra B3", "dados/mercado/di1_vencimentos_genericos.csv",
       len(gen), str(gen.data.min().date()), str(gen.data.max().date()), "casa as séries genéricas com o contrato vivo")
    # 5) ANBIMA (janela)
    try:
        an = anbima.coletar()
        c = an.get("parametros_cobertura", ("", "", 0))
        ok("ETTJ ANBIMA (nominal, real, implícita)", "ANBIMA", "dados/mercado/anbima/", c[2], c[0], c[1],
           "só a janela gratuita (~1 mês); cumulativo a cada execução")
    except Exception as e:  # noqa: BLE001
        ok("ETTJ ANBIMA", "ANBIMA", "dados/mercado/anbima/", 0, "", "", f"falhou: {e}")
    # 6) Tesouro Direto
    td = inflacao_implicita.construir(atualizar=atualizar)
    d = td["diario"]
    ok("Curvas nominal/real e implícita (histórico)", "Tesouro Direto", "dados/mercado/curvas_tesouro_direto_diario.csv",
       len(d), str(d.data.min().date()), str(d.data.max().date()),
       f"implícita 5a em {100*td['cobertura']['implicita_5a']:.0f}% dos dias; rival -> dados/mercado/breakeven.csv")
    if td["validacao"] is not None:
        v = td["validacao"].dropna(subset=["dif_media_pp"])
        v5 = v[(v.horizonte_anos == 5) & (v.curva == "implicita")]
        if len(v5):
            ok("Validação Tesouro Direto × ANBIMA", "—", "dados/mercado/validacao_td_vs_anbima.csv", int(v5.n_dias.iloc[0]),
               "", "", f"implícita 5a: dif. média {v5.dif_media_pp.iloc[0]:+.3f} p.p., corr {v5.corr_diaria.iloc[0]:.3f}")
    # 7) B3 — curvas de referência (DI×Pré desde 2001; LTN/NTN-B desde 2004; DI×IPCA desde 2005)
    b3 = b3_taxas.construir(coletar_antes=True)
    bd = b3["diario"]
    ok("Curvas B3: DI×Pré, DI×IPCA, LTN, NTN-B", "B3 TaxaSwap", "dados/mercado/curvas_b3_diario.csv",
       len(bd), str(bd.data.min().date()), str(bd.data.max().date()),
       f"implícita de títulos 5a em {100*b3['cobertura']['implicita_titulos_5a']:.0f}% dos dias")
    if b3["validacao"] is not None:
        v = b3["validacao"]
        v5 = v[(v.horizonte == "5a") & (v.fonte_b3 == "titulos") & (v.curva == "implicita")]
        if len(v5):
            ok("Validação B3 (títulos) × ANBIMA", "—", "dados/mercado/validacao_b3_vs_anbima.csv", int(v5.n_dias.iloc[0]),
               "", "", f"implícita 5a: dif. média {v5.dif_media_pp.iloc[0]:+.3f} p.p., corr {v5.corr_diaria.iloc[0]:.3f}")
    # 8) Rival de mercado: implícita 5a de títulos da B3; buracos preenchidos com o Tesouro Direto
    riv = salvar_breakeven(bd, d)
    ok("Rival breakeven (Bloco 3)", "B3 títulos, Tesouro Direto nos buracos", "dados/mercado/breakeven.csv",
       len(riv), str(riv.data.min().date()), str(riv.data.max().date()),
       ", ".join(f"{k}: {v}" for k, v in riv.fonte.value_counts().items()))
    return pd.DataFrame(status)


def salvar_breakeven(b3_diario: pd.DataFrame, td_diario: pd.DataFrame, horizonte: str = "5a") -> pd.DataFrame:
    """``dados/mercado/breakeven.csv`` (data, valor, fonte) para ``validacao.rivais``.

    Preferência: implícita de títulos da B3 (LTN × NTN-B, reproduz a ETTJ
    ANBIMA com erro de centésimos); dias sem ela usam o Tesouro Direto.
    """
    b = b3_diario[["data", f"implicita_titulos_{horizonte}"]].rename(columns={f"implicita_titulos_{horizonte}": "b3"})
    t = td_diario[["data", f"implicita_{horizonte}"]].rename(columns={f"implicita_{horizonte}": "td"})
    j = b.merge(t, on="data", how="outer").sort_values("data")
    j["valor"] = j["b3"].combine_first(j["td"])
    j["fonte"] = np.where(j["b3"].notna(), "b3_titulos", np.where(j["td"].notna(), "tesouro_direto", None))
    out = j.dropna(subset=["valor"])[["data", "valor", "fonte"]]
    out.to_csv(b3_taxas.DIR_MERCADO / "breakeven.csv", index=False, date_format="%Y-%m-%d")
    return out


def main() -> None:  # pragma: no cover
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--atualizar", action="store_true")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    st = rodar(atualizar=a.atualizar)
    print(st.to_markdown(index=False))


if __name__ == "__main__":  # pragma: no cover
    main()

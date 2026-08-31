# %% Diagnóstico — a coleta cobriu mesmo o período?

import glob
import os

import pandas as pd

import configuracao as cfg
from transporte import CONTADOR

# %% Cobertura

def coberturaMensal(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Meses zerados indicam falha de coleta, não ausência de notícia — o Copom
    se reúne oito vezes por ano, sem exceção."""
    mensal = (dataframe.set_index("data").groupby("veiculo").resample("MS").size()
              .unstack(0).fillna(0).astype(int))
    vazios = {c: int((mensal[c] == 0).sum()) for c in mensal.columns}
    print("Meses sem nenhuma notícia, por veículo:")
    for k, v in sorted(vazios.items(), key=lambda x: -x[1]):
        print(f"  {k:16} {v}")
    return mensal


def testeCopom(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Cada decisão do Copom teve cobertura na janela de dois dias?"""
    linhas = []
    for veiculo, g in dataframe.groupby("veiculo"):
        for ano, datas in cfg.COPOM.items():
            for dt in datas:
                ref = pd.Timestamp(dt)
                n = int(((g["data"] >= ref) &
                         (g["data"] < ref + pd.Timedelta(days=cfg.JANELA_COPOM))
                         ).sum())
                linhas.append({"veiculo": veiculo, "ano": ano, "reuniao": dt,
                               "noticias": n, "coberta": n > 0})
    cobertura = pd.DataFrame(linhas)
    if cobertura.empty:
        return cobertura
    print(cobertura.groupby(["veiculo", "ano"]).agg(
        cobertas=("coberta", "sum"), taxa=("coberta", "mean"),
        noticias=("noticias", "sum")).to_string())
    return cobertura

# %% Relatório

def relatorio(dataframe: pd.DataFrame) -> pd.DataFrame:
    print("\n" + "═" * 76)
    print("VOLUME POR VEÍCULO E ANO")
    print("═" * 76)
    print(dataframe.assign(ano=dataframe["data"].dt.year).pivot_table(
        index="ano", columns="veiculo", values="url", aggfunc="size",
        fill_value=0).to_string())

    print("\n" + "═" * 76)
    print("COMPLETUDE E CUSTO")
    print("═" * 76)
    for v, g in dataframe.groupby("veiculo"):
        req = CONTADOR.get(v, 0)
        taxa = f"{req / len(g):.2f}" if len(g) else "—"
        print(f"  {v:16} n={len(g):6} | subtítulo={g['subtitulo'].notna().mean():.2f}"
              f" | p2={g['p2'].notna().mean():.2f} | {req} req ({taxa} req/notícia)")

    print("\n" + "═" * 76)
    print("COBERTURA DO COPOM (anos com calendário conferido)")
    print("═" * 76)
    testeCopom(dataframe)
    return dataframe


def consultasTruncadas() -> pd.DataFrame:
    """Consulta marcada como TRUNCADO no plano não alcançou o início da série.
    Se aparecer alguma, acrescente divisores em DIVISORES_2 e rode coletarTudo
    com replanejar=True."""
    planos = [pd.read_csv(p)
              for p in glob.glob(os.path.join(cfg.PASTA_PLANOS, "plano_*.csv"))]
    if not planos:
        print("Nenhum plano em disco ainda.")
        return pd.DataFrame()
    todos = pd.concat(planos, ignore_index=True)
    truncadas = todos[todos["status"] == "TRUNCADO"]
    print(truncadas[["veiculo", "consulta", "total"]].to_string(index=False))
    print(f"{len(truncadas)} truncada(s) de {len(todos)}")
    return truncadas

# %% Leitura manual

def amostra(dataframe: pd.DataFrame, n: int = 4, semente: int = 1) -> None:
    """Nenhum diagnóstico automático substitui ler algumas matérias inteiras."""
    for _, r in dataframe.sample(min(n, len(dataframe)),
                                 random_state=semente).iterrows():
        print(f"\n{'=' * 76}\n{r['veiculo']} | {r['data']:%d/%m/%Y} | {r['secao']}"
              f"\n{'=' * 76}")
        print(r["texto_llm"])


def graficoCobertura(mensal: pd.DataFrame):
    import matplotlib.pyplot as plt
    ax = mensal.plot(figsize=(14, 5), linewidth=1)
    ax.set_title("Notícias sobre política monetária por mês")
    ax.set_xlabel("")
    ax.set_ylabel("nº de notícias")
    ax.legend(fontsize=8, ncol=4)
    plt.tight_layout()
    plt.show()
    return ax

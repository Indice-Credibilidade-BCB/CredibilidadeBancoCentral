# %% Planejamento — subdividir consultas até caberem no teto de paginação

import os

import pandas as pd

import configuracao as cfg
from sondagem import medirTermo
from utilitarios import log, norm, slug

# %% Expansão recursiva

def expandir(termo, tenant, veiculo, ini, fim, prof=0, max_prof=2, _visto=None) -> list:
    """Subdivide a consulta até cada pedaço caber no teto de paginação.

    A consulta "cabe sem subdividir" se a paginação profunda (posição
    TETO_FROM-100, ver medirTermo) já alcança uma data ANTERIOR ao INÍCIO
    da janela desejada (`limite < ini`) — é isso que garante que nada entre
    `ini` e `fim` fica fora do alcance dos 10 mil resultados. Comparar com
    `fim` (como uma versão anterior fazia) está errado: `fim` quase sempre
    já é passado, então a comparação seria quase sempre verdadeira e a
    consulta NUNCA seria subdividida — para termos muito cobertos (ex.:
    "Copom" isolado), os 10 mil resultados mais recentes não chegam nem
    perto do início da janela, e a varredura trunca silenciosamente sem que
    o plano tenha avisado (visto na prática: "Copom" na Valor truncou em
    2019-03, sem cobrir nada de 2016 a começo de 2019)."""
    _visto = _visto if _visto is not None else set()
    if termo in _visto:
        return []
    _visto.add(termo)

    total, limite = medirTermo(termo, tenant, veiculo)
    if not isinstance(total, int) or total == 0:
        return [{"consulta": termo, "total": total, "alcance": None,
                 "status": "sem resultados", "nivel": prof}]
    if total < cfg.TETO_FROM:
        return [{"consulta": termo, "total": total, "alcance": "completo",
                 "status": "enumerável", "nivel": prof}]
    if limite is not None and limite < ini:
        return [{"consulta": termo, "total": total, "alcance": str(limite.date()),
                 "status": "alcança a janela", "nivel": prof}]
    if prof >= max_prof:
        return [{"consulta": termo, "total": total,
                 "alcance": str(limite.date()) if limite is not None else None,
                 "status": "TRUNCADO", "nivel": prof}]

    divisores = cfg.DIVISORES if prof == 0 else cfg.DIVISORES_2
    log(f"    {termo!r} trava em "
        f"{limite.strftime('%Y-%m') if limite is not None else '?'} — subdividindo")
    saida = []
    for d in divisores:
        if norm(d) in norm(termo):
            continue
        saida += expandir(f"{termo} {d}", tenant, veiculo, ini, fim,
                          prof + 1, max_prof, _visto)
    return saida

# %% Plano por veículo

def planejar(veiculo, tenant, termos=None, ini=None, fim=None, max_prof=2,
             usarCache=True) -> pd.DataFrame:
    """Monta (ou completa) o plano de consultas do veículo. O plano fica em disco
    e é compartilhado no repositório: numa retomada ele é lido, não refeito.
    Termo NOVO — que ninguém planejou ainda — é acrescentado ao plano existente,
    então dá para ampliar o repertório sem jogar fora o trabalho anterior."""
    termos = termos or cfg.TERMOS
    ini = ini or cfg.INICIO
    fim = fim or cfg.FIM
    os.makedirs(cfg.PASTA_PLANOS, exist_ok=True)
    cache = os.path.join(cfg.PASTA_PLANOS, f"plano_{slug(veiculo)}.csv")

    plano = pd.DataFrame()
    if usarCache and os.path.exists(cache):
        plano = pd.read_csv(cache)

    def coberto(t):
        if plano.empty:
            return False
        c = plano["consulta"].astype(str)
        return bool((c == t).any() or c.str.startswith(t + " ").any())

    faltando = [t for t in termos if not coberto(t)]
    if not faltando:
        log(f"  plano em cache: {int(plano['usar'].sum())} consulta(s)")
        return plano

    linhas = []
    for t in faltando:
        log(f"  planejando {t!r}")
        linhas += expandir(t, tenant, veiculo, ini, fim, max_prof=max_prof)

    novo = pd.DataFrame(linhas)
    novo["veiculo"] = veiculo
    plano = (pd.concat([plano, novo], ignore_index=True)
             if not plano.empty else novo).drop_duplicates(subset="consulta")
    plano["usar"] = plano["status"].isin(["enumerável", "alcança a janela"])
    plano.to_csv(cache, index=False, encoding="utf-8-sig")

    truncadas = int((plano["status"] == "TRUNCADO").sum())
    print(f"  {int(plano['usar'].sum())} consulta(s) utilizáveis"
          + (f", {truncadas} truncada(s)" if truncadas else ""))
    return plano

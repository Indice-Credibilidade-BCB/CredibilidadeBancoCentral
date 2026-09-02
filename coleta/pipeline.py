# %% Pipeline — orquestração da coleta e consolidação da base

import json
import os
import re
from datetime import datetime

import pandas as pd

import configuracao as cfg
from armazenamento import carregarFeitas, gravar, marcarFeita
from planejamento import planejar
from sincronizacao import gitEnviar, gitPuxar
from utilitarios import desembrulharUrl, log, norm, slug
from varredura import varrerGlobo, varrerWp

# %% Divisão do trabalho

def dividirTrabalho(pessoas, termos=None) -> dict:
    """Reparte os termos entre as pessoas de forma determinística: cada uma roda
    a sua fatia e ninguém duplica esforço mesmo trabalhando ao mesmo tempo.
    O registro compartilhado ainda protege contra sobreposição acidental."""
    termos = termos or cfg.TERMOS
    pessoas = sorted(pessoas)
    lotes = {p: [] for p in pessoas}
    for i, t in enumerate(termos):
        lotes[pessoas[i % len(pessoas)]].append(t)
    for p, ts in lotes.items():
        print(f"  {p:12} -> {ts}")
    return lotes

# %% Coleta

def coletarTudo(veiculos=None, termos=None, ini=None, fim=None, sondagem=None,
                max_prof=2, replanejar=False, sincronizar=None) -> pd.DataFrame:
    """Percorre os veículos Faixa A. Cada consulta concluída é gravada, marcada
    e (se houver git) publicada periodicamente. Consulta já feita por QUALQUER
    colaborador é pulada — se cair, é só rodar de novo."""
    ini = ini or cfg.INICIO
    fim = fim or cfg.FIM
    termos = termos or cfg.TERMOS
    sincronizar = cfg.SINCRONIZAR_GIT if sincronizar is None else sincronizar
    if sondagem is not None:
        nomes = sondagem[sondagem["faixa_a"]]["veiculo"].tolist()
        veiculos = {k: v for k, v in cfg.VEICULOS.items() if k in nomes}
    veiculos = veiculos or cfg.VEICULOS

    if sincronizar:
        gitPuxar()
    feitas = carregarFeitas()
    log(f"{len(feitas)} consulta(s) já concluída(s) (todos os colaboradores).")
    log(f"Gravando como {cfg.COLABORADOR!r}.")

    resumo, desdePush = [], 0

    def talvezPublicar(forcar=False):
        nonlocal desdePush
        if not sincronizar:
            return
        if forcar or desdePush >= cfg.SINCRONIZAR_A_CADA:
            gitEnviar(f"coleta: +{desdePush} consulta(s)")
            desdePush = 0

    for nome, conf in veiculos.items():
        log(f"═══ {nome} ({conf['motor']})")

        if conf["motor"] == "globo":
            plano = planejar(nome, conf["tenant"], termos, ini, fim, max_prof,
                             usarCache=not replanejar)
            for _, linha in plano[plano["usar"]].iterrows():
                # A chave PRECISA incluir a janela de datas: o texto da
                # consulta (ex.: "Selic Tombini") se repete entre rodadas
                # com ini/fim diferentes (backfill de outro período), e sem
                # a janela aqui a segunda rodada pula a consulta inteira
                # pensando que já foi feita — vazio silencioso (visto na
                # prática: Valor não coletou nada numa rodada de backfill
                # porque as mesmas consultas por presidente já estavam no
                # ledger da rodada anterior). O motor wordpress já inclui o
                # ano na chave por outro motivo e não tem esse problema.
                chave = f"{nome}||{linha['consulta']}||{ini:%Y%m%d}-{fim:%Y%m%d}"
                if chave in feitas:
                    continue
                registros, info = varrerGlobo(linha["consulta"], nome,
                                              conf["tenant"], ini, fim)
                gravar(nome, registros)
                marcarFeita(chave)
                feitas.add(chave)
                desdePush += 1
                log(f"  {linha['consulta']!r}: {len(registros)} notícias | "
                    f"chegou em {info['chegou_em']}"
                    + ("  [TRUNCADA]" if info["truncou"] else ""))
                resumo.append({"veiculo": nome, "consulta": linha["consulta"],
                               "n": len(registros), "truncou": info["truncou"]})
                talvezPublicar()
        else:
            for termo in termos:
                for ano in range(ini.year, fim.year + 1):
                    # Ano de borda (ex.: fim=2020-01-01 inclui ano=2020 no
                    # range, mas a fatia real [max(ano,ini), min(ano+1,fim))
                    # fica vazia): NÃO marcar o ledger como feito. Sem esta
                    # guarda, uma rodada FUTURA cuja janela desloque esse
                    # mesmo ano para dentro do intervalo útil pula ele
                    # pensando que já foi coletado — vazio silencioso (visto
                    # na prática: InfoMoney/Money Times/Poder360 perderam
                    # 2020 inteiro numa rodada de backfill por causa disso).
                    a = max(datetime(ano, 1, 1), ini)
                    b = min(datetime(ano + 1, 1, 1), fim)
                    if a >= b:
                        continue
                    chave = f"{nome}||{termo}||{ano}"
                    if chave in feitas:
                        continue
                    registros, info = varrerWp(termo, nome, conf["base"], ano,
                                               ini, fim)
                    gravar(nome, registros)
                    marcarFeita(chave)
                    feitas.add(chave)
                    desdePush += 1
                    if registros:
                        log(f"  {termo!r} {ano}: {len(registros)} notícias "
                            f"(busca achou {info['total']})")
                    resumo.append({"veiculo": nome, "consulta": f"{termo} [{ano}]",
                                   "n": len(registros), "truncou": False})
                    talvezPublicar()

    talvezPublicar(forcar=True)
    resumo = pd.DataFrame(resumo)
    if not resumo.empty:
        print("\n" + resumo.groupby("veiculo")["n"].agg(["sum", "size"]).to_string())
    return resumo

# %% Consolidação

def consolidar(exigirP2=True, puxar=True) -> pd.DataFrame:
    """Junta os arquivos brutos de TODOS os colaboradores e monta a base final:
    dados/noticias.csv e dados/para_llm.jsonl."""
    if puxar:
        gitPuxar()
    arquivos = ([os.path.join(cfg.PASTA_BRUTO, f)
                 for f in os.listdir(cfg.PASTA_BRUTO) if f.endswith(".jsonl")]
                if os.path.isdir(cfg.PASTA_BRUTO) else [])
    registros = []
    for a in arquivos:
        with open(a, encoding="utf-8") as f:
            for linha in f:
                try:
                    registros.append(json.loads(linha))
                except json.JSONDecodeError:
                    pass
    if not registros:
        print("Nada coletado ainda.")
        return pd.DataFrame()
    colaboradores = {r.get("colaborador") for r in registros}
    print(f"{len(arquivos)} arquivo(s) de {len(colaboradores)} colaborador(es)")

    dataframe = pd.DataFrame(registros)
    n0 = len(dataframe)

    # A busca da Globo devolve um REDIRECIONADOR de clique
    # (measures.globo.com/v1/click?...&u=<url real>) cujo path é idêntico
    # para toda matéria — normalizar sem desembrulhar primeiro colapsaria
    # TODO o veículo num único chave_url (visto na prática: reduziu 5.262
    # brutos da Valor a 1 registro). Desembrulha ANTES de normalizar, e
    # substitui `url` pela URL real: o link de tracking expira e não serve
    # para citar a fonte no paper nem para reauditar o item depois.
    dataframe["url"] = dataframe["url"].map(desembrulharUrl)
    # a mesma notícia chega por várias consultas — dedup por URL normalizada
    dataframe["chave_url"] = (dataframe["url"].astype(str)
                              .str.replace(r"[?#].*$", "", regex=True)
                              .str.rstrip("/").str.lower())
    dataframe = dataframe.drop_duplicates(subset="chave_url")

    dataframe["data"] = pd.to_datetime(dataframe["data"], errors="coerce",
                                       utc=True, format="mixed")
    dataframe = dataframe[dataframe["data"].notna()]
    dataframe["data"] = (dataframe["data"].dt.tz_convert("America/Sao_Paulo")
                         .dt.tz_localize(None))

    dataframe = dataframe[dataframe["titulo"].notna() & dataframe["p1"].notna()]
    if exigirP2:
        dataframe = dataframe[dataframe["p2"].notna()]

    # matéria de agência republicada: mesmo título em veículos diferentes
    dataframe["chave_tit"] = dataframe["titulo"].map(
        lambda t: re.sub(r"[^a-z0-9 ]", " ", norm(t)))
    dataframe = dataframe.sort_values("data")
    dataframe["n_replicacoes"] = (dataframe.groupby("chave_tit")["chave_tit"]
                                  .transform("size"))
    dataframe["replicada"] = dataframe.duplicated(subset="chave_tit", keep="first")

    dataframe["texto_llm"] = dataframe.apply(lambda r: "\n\n".join(x for x in [
        f"TÍTULO: {r['titulo']}",
        f"SUBTÍTULO: {r['subtitulo']}" if pd.notna(r["subtitulo"]) else None,
        f"TEXTO: {r['p1']}",
        r["p2"] if pd.notna(r["p2"]) else None] if x), axis=1)

    colunas = ["veiculo", "data", "url", "titulo", "subtitulo", "p1", "p2",
               "secao", "n_paragrafos", "consulta", "n_replicacoes", "replicada",
               "texto_llm"]
    dataframe = (dataframe[colunas].sort_values(["data", "veiculo"])
                 .reset_index(drop=True))

    os.makedirs(cfg.PASTA, exist_ok=True)
    dataframe.to_csv(os.path.join(cfg.PASTA, "noticias.csv"), index=False,
                     encoding="utf-8-sig")
    unicas = dataframe[~dataframe["replicada"]]
    with open(os.path.join(cfg.PASTA, "para_llm.jsonl"), "w",
              encoding="utf-8") as f:
        for i, r in unicas.iterrows():
            f.write(json.dumps({"id": f"{slug(r['veiculo'])[:4]}-{i:06d}",
                                "veiculo": r["veiculo"],
                                "data": r["data"].strftime("%Y-%m-%d"),
                                "url": r["url"], "texto": r["texto_llm"]},
                               ensure_ascii=False) + "\n")
    print(f"{n0} brutos -> {len(dataframe)} após dedup e filtros -> "
          f"{len(unicas)} sem replicação de agência")
    gitEnviar("consolidação da base")
    return dataframe

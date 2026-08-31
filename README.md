# Credibilidade do Banco Central

Base para quantificar a percepção pública sobre a atuação do Banco Central.

## Estrutura

    source/scrappingDI.py       swap DI por vértice, via SGS do BCB
    source/extracaoNoticias/    coleta de notícias sobre política monetária
    dados/bruto/                registros crus, um arquivo por veículo por pessoa
    dados/concluidas/           o que cada pessoa já varreu
    dados/planos/               partições planejadas por veículo (compartilhado)
    dados/noticias.csv          base consolidada (gerada por consolidar())
    dados/para_llm.jsonl        mesma base, sem replicação de agência

## Extração de notícias

Pipeline em `source/extracaoNoticias/`, dividido por etapa:

    configuracao.py   período, termos, veículos, calendário do Copom
    utilitarios.py    log, normalização sem acento, filtro temático
    transporte.py     sessão HTTP, busca da Globo, leitura do Elasticsearch
    extracao.py       do JSON cru ao registro (título, linha fina, p1, p2)
    sondagem.py       quem é Faixa A; mede o tamanho de cada consulta
    planejamento.py   subdivide consultas que estouram o teto de paginação
    varredura.py      percorre uma consulta até o fim (globo e wordpress)
    armazenamento.py  arquivos brutos e registro de consultas concluídas
    sincronizacao.py  pull no início, push a cada 5 consultas
    pipeline.py       coletarTudo() e consolidar()
    diagnostico.py    cobertura mensal, teste do Copom, relatório
    main.py           o roteiro, em células `# %%`

### Como rodar

1. `pip install -r requirements.txt`
2. Em `main.py`, troque o nome em `cfg.definirColaborador("enzo")` — ou defina
   a variável de ambiente `COLETA_USER`.
3. Rode `main.py` inteiro ou célula a célula.

Só entram na coleta os veículos de **Faixa A**: aqueles cuja API devolve título,
linha fina e corpo na mesma requisição da descoberta, sem precisar baixar a
página do artigo. Quem é Faixa A é decidido por `sondarVeiculos()`, não por
suposição.

O motor da Globo trava em `from=10.000`, então cada termo que não alcança o
início da série é subdividido cruzando com os presidentes do BC — que recortam
o período por época. Os presidentes são apenas divisores: não entram na
definição do corpus, dada só pelos termos temáticos.

### Trabalho em grupo

Cada pessoa grava nos próprios arquivos (`dados/bruto/<veiculo>__<pessoa>.jsonl`),
então ninguém sobrescreve o trabalho de ninguém. O registro de consultas
concluídas é compartilhado: o que um já coletou, o outro pula. A sincronização
com o repositório é automática — `pull` no início, `push` a cada 5 consultas.

Se forem coletar ao mesmo tempo, dividam os termos antes com
`dividirTrabalho(["enzo", "amigo"])`. Em horários diferentes não precisa.

A coleta é compartimentada: cada par (veículo, consulta) é gravado assim que
termina e nunca é refeito. Pode interromper e retomar quantas vezes quiser.

## Aviso

O repositório armazena título, linha fina e os dois primeiros parágrafos de
matérias de terceiros. Mantenha o repositório **privado**: redistribuir texto
jornalístico publicamente esbarra em direito autoral e nos termos de uso dos
veículos.

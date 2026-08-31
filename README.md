# Coleta de notícias sobre política monetária

Base para quantificar a percepção pública sobre a atuação do Banco Central.

## Como participar

1. `pip install -r requirements.txt`
2. Abra `coleta.ipynb` e defina `COLABORADOR = "seunome"` na célula de configuração.
3. Rode a sondagem, depois `coletar_tudo()`.

Cada pessoa grava nos próprios arquivos (`dados/bruto/<veiculo>__<pessoa>.jsonl`),
então ninguém sobrescreve o trabalho de ninguém. O registro de consultas
concluídas é compartilhado: o que um já coletou, o outro pula.

Se forem coletar ao mesmo tempo, dividam os termos antes com
`dividir_trabalho(["enzo", "amigo"])`.

## Estrutura

    dados/bruto/        registros crus, um arquivo por veículo por pessoa
    dados/concluidas/   o que cada pessoa já varreu
    dados/planos/       partições planejadas por veículo (compartilhado)
    dados/noticias.csv  base consolidada (gerada por consolidar())

## Aviso

O repositório armazena título, linha fina e os dois primeiros parágrafos de
matérias de terceiros. Mantenha o repositório **privado**: redistribuir texto
jornalístico publicamente esbarra em direito autoral e nos termos de uso dos
veículos.

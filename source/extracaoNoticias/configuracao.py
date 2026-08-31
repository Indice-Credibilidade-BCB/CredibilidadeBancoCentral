# %% Configuração — mexa aqui

import os
from datetime import datetime

# %% Período e caminhos

INICIO = datetime(2011, 1, 1)      # o arquivo da busca da Globo chega a 2011
FIM = datetime(2026, 9, 1)

# Os dados ficam na raiz do repositório, não ao lado do código: assim o
# caminho não depende de onde o script foi disparado.
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

PASTA = os.path.join(RAIZ, "dados")             # versionado
PASTA_BRUTO = os.path.join(PASTA, "bruto")
PASTA_LEDGER = os.path.join(PASTA, "concluidas")
PASTA_PLANOS = os.path.join(PASTA, "planos")

# %% Colaborador e sincronização

# Quem está rodando. Cada pessoa grava nos SEUS arquivos — é isso que evita
# conflito de merge quando várias fazem push. Defina antes de coletar, por
# variável de ambiente COLETA_USER ou por definirColaborador("seunome").
COLABORADOR = (os.environ.get("COLETA_USER")
               or os.environ.get("USER")
               or os.environ.get("USERNAME")
               or "anonimo")

SINCRONIZAR_GIT = True             # commit+push automático durante a coleta
SINCRONIZAR_A_CADA = 5             # consultas concluídas entre cada push


def definirColaborador(nome: str) -> str:
    """Os outros módulos leem configuracao.COLABORADOR em tempo de chamada,
    então trocar aqui vale para o pipeline inteiro."""
    global COLABORADOR
    COLABORADOR = nome
    print("gravando como", COLABORADOR)
    return COLABORADOR

# %% Repertório temático

# Termos específicos de política monetária. Deliberadamente fora: "taxa de
# juros", "inflação", "economia" — amplos demais, trazem crédito bancário,
# juro de cartão e preço de supermercado.
TERMOS = [
    "Copom",
    "Selic",
    "ata do Copom",
    "política monetária",
    "meta de inflação",
    "Relatório de Inflação",
    "Banco Central",
]

# Divisores para subdividir consultas que estouram o teto de paginação.
# Presidentes do BC recortam a série por época — não fazem parte do corpus.
DIVISORES = ["Tombini", "Ilan Goldfajn", "Roberto Campos Neto", "Galípolo"]
DIVISORES_2 = ["Copom", "Selic", "inflação", "reunião", "comunicado"]

# Filtro LOCAL de tema, sobre o texto já baixado (sem acento).
TERMOS_FILTRO = ["banco central", "copom", "selic", "politica monetaria",
                 "meta de inflacao", "relatorio de inflacao", "bacen"]

# %% Veículos candidatos a Faixa A

# Faixa A: a API devolve título, linha fina e corpo na mesma requisição da
# descoberta. sondarVeiculos() confirma quais realmente respondem.
VEICULOS = {
    "Valor":          {"motor": "globo", "tenant": "valor"},
    "G1":             {"motor": "globo", "tenant": "g1"},
    "O Globo":        {"motor": "globo", "tenant": "oglobo"},
    "Poder360":       {"motor": "wordpress", "base": "https://www.poder360.com.br"},
    "InfoMoney":      {"motor": "wordpress", "base": "https://www.infomoney.com.br"},
    "Money Times":    {"motor": "wordpress", "base": "https://www.moneytimes.com.br"},
    "Agência Brasil": {"motor": "wordpress", "base": "https://agenciabrasil.ebc.com.br"},
}

# %% Calendário do Copom e limites de requisição

# Reuniões do Copom (2ª sessão). 2016-2017 conferido; demais anos: CONFERIR
# no bcb.gov.br antes de usar no diagnóstico.
COPOM = {
    2016: ["2016-01-20", "2016-03-02", "2016-04-27", "2016-06-08",
           "2016-07-20", "2016-08-31", "2016-10-19", "2016-11-30"],
    2017: ["2017-01-11", "2017-02-22", "2017-04-12", "2017-05-31",
           "2017-07-26", "2017-09-06", "2017-10-25", "2017-12-06"],
}
JANELA_COPOM = 2

PAUSA = 3.0
TIMEOUT = 45
TETO_FROM = 10000

# %% Coleta de notícias sobre política monetária — roteiro
"""
Ordem: preparação → sondagem → conjunção → coleta → consolidação → diagnóstico.

Rode célula a célula (# %%) ou o arquivo inteiro. A coleta é compartimentada:
cada par (veículo, consulta) é gravado assim que termina e nunca é refeito, então
pode interromper à vontade e rodar de novo.

O texto das matérias (dados/bruto/, dados/noticias.csv) fica fora do Git — o
.gitignore da raiz nega dados/ por padrão. Ver a regra de dados no README.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import configuracao as cfg
from armazenamento import prepararPastas
from diagnostico import (amostra, coberturaMensal, consultasTruncadas,
                         graficoCobertura, relatorio)
from pipeline import coletarTudo, consolidar, dividirTrabalho
from sondagem import sondarVeiculos, testarConjuncao

# %% 1. Quem está rodando

# Cada pessoa grava nos próprios arquivos — é isso que evita conflito de merge.
cfg.definirColaborador("enzo")      # <<< TROQUE PELO SEU NOME

# %% 2. Preparar as pastas de dados (só na primeira vez)

prepararPastas()

# %% 3. Dividir o trabalho

# Só é preciso se forem coletar ao MESMO tempo. Em horários diferentes o
# registro compartilhado já evita retrabalho.
lotes = dividirTrabalho(["enzo", "amigo"])

# %% 4. Quem é Faixa A?

# Uma requisição por veículo. faixa_a = True exige que a resposta traga corpo de
# texto — é isso que dispensa baixar a página do artigo. Os tenants de G1 e
# O Globo são inferidos por analogia com o do Valor; se vierem reprovados,
# capture o endpoint real pelo DevTools (F12 → Network → Fetch/XHR → "Copom")
# e ajuste VEICULOS em configuracao.py.
sondagem = sondarVeiculos()

# %% 5. A busca combina palavras com E?

# Se sim, subdividir consultas grandes reduz o conjunto. Três requisições.
testarConjuncao("valor", "Valor", "Copom", "Tombini")

# %% 6. Coleta

# A parte longa: planeja as partições de cada veículo do motor globo, subdivide
# o que não alcança o início da série e varre tudo. Conte algumas horas para a
# série de 2011 a 2026 — para testar antes, reduza cfg.FIM ou passe
# termos=["Copom"]. Se cair, rode esta célula de novo: nada é refeito.
resumo = coletarTudo(sondagem=sondagem)

# Rodando apenas o seu lote, se dividiram o trabalho:
# resumo = coletarTudo(sondagem=sondagem, termos=lotes[cfg.COLABORADOR])

# Um veículo de cada vez, se preferir:
# resumo = coletarTudo(veiculos={"Valor": cfg.VEICULOS["Valor"]})

# %% 7. Consolidação

# Junta os brutos, remove duplicatas por URL, marca matéria de agência replicada
# entre veículos e grava dados/noticias.csv e dados/para_llm.jsonl.
noticias = consolidar(exigirP2=True)
print(noticias.head(3).to_string())

# %% 8. Diagnóstico

relatorio(noticias)

# %% 9. Cobertura mensal

# Mês zerado é falha de coleta, não ausência de notícia. Investigue qualquer
# buraco antes de seguir para a análise.
mensal = coberturaMensal(noticias)
graficoCobertura(mensal)

# %% 10. Consultas truncadas e leitura manual

consultasTruncadas()
amostra(noticias, n=4)

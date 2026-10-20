# Índice de Credibilidade do Banco Central do Brasil

Projeto de pesquisa (Iniciação Científica, FEA-USP) que mede a credibilidade
percebida do BCB a partir do que a imprensa escreve sobre ele. Cada notícia é
lida por um LLM, uma por chamada, com um instrumento fixo (prompt v1.1); o
índice mensal e diário sai da dimensão D1 (a meta é crível?). O artigo é de
medição: constrói o índice, testa o vazamento temporal do modelo e defende a
validade de construto (convergente, discriminante, preditiva, encompassing
contra o latente do Kalman e tempo real), com um estudo de eventos do Copom
como aplicação.

Desenho, decisões e auditorias ficam no documento de contexto do projeto,
fora do repositório (`docs/local/`, não versionado).

## Mapa do repositório

| Pasta | O que é |
|---|---|
| [`coleta/`](coleta/) | Coleta do corpus de imprensa: busca da Globo, WordPress REST, sitemaps. Multi-colaborador, retomável. |
| [`llm/`](llm/) | Índice: prompt, provedores (Sabiá, Gemini e outros), pré-filtro BERTimbau com auditoria aleatória, bateria anti-vazamento (T0–T6), agregação, robustez e figuras do índice. |
| [`mercado/`](mercado/) | Séries públicas: BCB (SGS, Focus, Copom), curvas da B3, Tesouro Direto, ANBIMA, breakeven. |
| [`validacao/`](validacao/) | Validade de construto, encompassing, estudo de eventos e figuras do artigo. |
| [`docs/`](docs/) | Guia de anotação. Contexto, decisões e auditorias ficam em `docs/local/` (não versionado). |
| `dados/` | Parcialmente versionado (ver abaixo): séries públicas e agregados sim, notícias não. |

As pastas usam nomes importáveis em Python (sem prefixo numérico) porque os
módulos se importam entre si; a correspondência com as Etapas está na tabela.

## Regra de dados (leia antes do primeiro push)

O corpus guarda título, linha fina e os dois primeiros parágrafos de matérias
de terceiros. **Isso não vai para o Git.** O `.gitignore` nega tudo dentro de
`dados/` e libera só o que pode ser publicado:

- ✅ `dados/concluidas/`, `dados/planos/` — coordenação da coleta, só chaves de
  consulta. É o que faz dois colaboradores não repetirem trabalho.
- ✅ `dados/mercado/` — séries numéricas públicas já tratadas (curvas B3,
  ETTJ ANBIMA, inflação implícita do Tesouro Direto).
- ✅ `dados/macro/` — séries brutas como foram baixadas (BCB SGS/Focus/Copom,
  Tesouro Direto, B3 TaxaSwap). Versionadas para a reprodução não depender de
  as fontes continuarem no ar.
- ✅ `dados/derivados/` — índice mensal, diário e trimestral, contagens,
  resultados da validação: agregados que não permitem reconstruir os textos.
- ❌ `dados/terceiros/` — séries de fornecedor (CDS, EMBI+ e outras) que não
  podem ser redistribuídas; os CSVs gravados pela validação saem sem elas.
- ❌ `dados/bruto/`, `dados/noticias.csv`, `dados/llm/` — texto de terceiros.

Se o repositório for público, isso é obrigatório. Se for privado, continua
sendo a postura certa: um repositório muda de visibilidade com dois cliques, e
o histórico do Git não esquece.

## Começando

```bash
git clone https://github.com/Indice-Credibilidade-BCB/CredibilidadeBancoCentral.git
cd CredibilidadeBancoCentral
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # ou o requirements.txt da pasta que for usar
```

Fluxo de ponta a ponta:

```bash
# 1) Coletar (cada pessoa nos próprios arquivos) — ver coleta/README.md
cd coleta && python main.py       # ou célula a célula (# %%); consolidar()
                                  # gera dados/noticias.csv e dados/para_llm.jsonl

# 2) Corpus, notas do LLM e índice — ver llm/README.md
cd ../llm
python corpus/from_coleta.py
python producao_v11.py            # pontua e agrega -> dados/derivados/indice_*_v11_*.csv

# 3) Séries públicas e validação (rodar da raiz)
cd ..
python -m mercado.bcb             # SGS/Focus/Copom -> dados/macro/
python -m mercado.lista2          # curvas, ETTJ, implícita -> dados/mercado/
python -m validacao.artigo        # bateria + relatório + figuras -> dados/derivados/validacao/artigo/
```

# Índice de Credibilidade do Banco Central do Brasil

Projeto de pesquisa (Iniciação Científica, FEA-USP) que constrói um índice de
credibilidade do BCB extraído por LLM da **percepção de terceiros** (imprensa e
research) e o testa em duas frentes: se rastreia a credibilidade latente
implícita em expectativas e preços (**validade**) e se explica a heterogeneidade
na transmissão de choques de política monetária (**utilidade**).

O desenho completo — pergunta de pesquisa, sistema de equações (Blocos 1–6),
ressalvas metodológicas e plano de publicação — está em
[`docs/CONTEXTO_Projeto_Indice_Credibilidade_BCB.md`](docs/CONTEXTO_Projeto_Indice_Credibilidade_BCB.md).

## Mapa do repositório

| Pasta | Etapa | O que é |
|---|---|---|
| [`coleta/`](coleta/) | 0 | Scraping do corpus de imprensa (busca da Globo + WordPress). Modular, multi-colaborador. |
| [`mercado/`](mercado/) | 0 | Séries de mercado: curva DI, ETTJ, breakeven, CDS. |
| [`llm/`](llm/) | 1–3 | Índice $\hat{C}^{LLM}_t$: prompts, provedores, piloto de anotação, bateria anti-vazamento, agregação. |
| [`validacao/`](validacao/) | 4 | Kalman ($\hat{C}^{KF}_t$) e encompassing contra rivais → **Paper 1**. |
| [`modelo/`](modelo/) | 5–7 | NK de 3 equações, projeções locais (Jordà), contrafactuais → **Paper 2**. |
| [`docs/`](docs/) | — | Contexto, decisões travadas, guia de anotação, auditorias. |
| `dados/` | — | **Não versionado** (ver abaixo). Criado localmente por quem roda. |

As pastas usam nomes importáveis em Python (sem prefixo numérico) porque os
módulos se importam entre si; a correspondência com as Etapas está na tabela.

## Regra de dados (leia antes do primeiro push)

O corpus guarda título, linha fina e os dois primeiros parágrafos de matérias
de terceiros. **Isso não vai para o Git.** O `.gitignore` nega tudo dentro de
`dados/` e libera só o que pode ser publicado:

- ✅ `dados/concluidas/`, `dados/planos/` — coordenação da coleta, só chaves de
  consulta. É o que faz dois colaboradores não repetirem trabalho.
- ✅ `dados/mercado/` — séries numéricas públicas (B3/ANBIMA/BCB).
- ✅ `dados/derivados/` — índice mensal, bandas, contagens: agregados que não
  permitem reconstruir os textos. É o que acompanha o paper.
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

# 2) Converter para o schema do índice e rodar o piloto — ver llm/README.md
cd ../llm
python corpus/from_coleta.py
python sample_pilot.py
```

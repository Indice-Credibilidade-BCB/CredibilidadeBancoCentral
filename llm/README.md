# `llm/` — Índice de credibilidade $\hat{C}^{LLM}_t$ (Etapas 1–3)

Pontua, via LLM, a percepção de terceiros sobre o BCB em três dimensões e
agrega numa série mensal em [0,1]. Free-first (roda em tier gratuito),
retomável (cache = checkpoint) e agnóstico de provedor.

Decisões travadas: [`../docs/Etapa2_Piloto_e_Implementacao_DECIDIDO.md`](../docs/Etapa2_Piloto_e_Implementacao_DECIDIDO.md)
· Auditoria de código e vieses: [`../docs/AUDITORIA_2026-08-18.md`](../docs/AUDITORIA_2026-08-18.md)
· Guia do anotador: [`../docs/Guia_Anotacao_v1.md`](../docs/Guia_Anotacao_v1.md)

## Estrutura

```
config.yaml            provedores, estratos do piloto, listas de anonimização
prompts.py             prompts v1.0 (fonte única de verdade; versionados)
corpus/from_coleta.py  adaptador: saída da coleta -> schema do índice
schema.py              validação do corpus, dedup, clusters de wire
relevance.py           filtro de relevância (regex; gate LLM opcional)
providers/             camada de abstração (Maritaca, Groq, Gemini)
scorer.py              pontuação em lote com rate limit e cache
reliability.py         kappa ponderado, alfa de Krippendorff, halo
sample_pilot.py        amostra estratificada + planilhas cegas + T2-H
diagnostics/leakage.py bateria anti-vazamento T2–T5
aggregate.py           série mensal com FE de veículo e bandas
fixtures/              sintéticos do T5 (versionados: não têm copyright)
tests/                 suíte + regressões da auditoria
```

Rode sempre a partir de `llm/`, com `PYTHONPATH=.` — os módulos se importam
pelo nome curto.

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...     # aistudio.google.com (free, sem cartão)
export GROQ_API_KEY=...       # console.groq.com  (free, sem cartão)
export MARITACA_API_KEY=...   # plataforma.maritaca.ai (pedir créditos acadêmicos)
```

## Fluxo

```bash
# 0) Corpus: converte dados/noticias.csv (saída de coleta.consolidar())
python corpus/from_coleta.py

# 1) Amostra do piloto: 50 itens estratificados + 10 de borda + 15 do T2-H
python sample_pilot.py

# 2) Anotação humana dupla e cega (../docs/Guia_Anotacao_v1.md) -> gate
python reliability.py ../dados/llm/piloto/anotacao_consolidada.csv

# 3) Pontuar o piloto nos 3 provedores
python scorer.py --provider sabia             --input ../dados/llm/piloto/pilot_items.csv --mode piloto --out ../dados/llm/scores/pilot_sabia.jsonl
python scorer.py --provider gemini_flash_lite --input ../dados/llm/piloto/pilot_items.csv --mode piloto --out ../dados/llm/scores/pilot_gemini.jsonl
python scorer.py --provider groq_llama        --input ../dados/llm/piloto/pilot_items.csv --mode piloto --out ../dados/llm/scores/pilot_groq.jsonl

# 4) Bateria anti-vazamento no melhor provedor
python scorer.py --provider sabia --input ../dados/llm/piloto/pilot_items.csv --mode piloto --date-mode omitida --out ../dados/llm/scores/t2_omitida.jsonl
python -c "import pandas as pd; from diagnostics.leakage import gerar_variantes_data as g; g(pd.read_csv('../dados/llm/piloto/pilot_items.csv')).to_csv('../dados/llm/piloto/pilot_t2.csv', index=False)"
python scorer.py --provider sabia --input ../dados/llm/piloto/pilot_t2.csv --mode piloto --date-mode trocada --out ../dados/llm/scores/t2_trocada.jsonl
python scorer.py --provider sabia --input ../dados/llm/piloto/pilot_items.csv --mode piloto --anonimizacao L2 --out ../dados/llm/scores/t3_L2.jsonl
python scorer.py --provider sabia --input fixtures/sinteticos_T5.csv --mode piloto --out ../dados/llm/scores/t5.jsonl

# 5) Série mensal
python aggregate.py --scores ../dados/llm/scores/producao.jsonl --corpus ../dados/llm/corpus.parquet --out ../dados/derivados/indice_mensal.csv

# Testes
PYTHONPATH=. python tests/test_reliability.py && PYTHONPATH=. python tests/test_auditoria.py
```

## Notas operacionais

- **Retomada:** linhas com `erro` são reprocessadas ao reexecutar o mesmo
  comando; a agregação deduplica por `cache_key` mantendo o último sucesso.
  Ao bater o teto diário (RPD), o job encerra limpo e retoma no dia seguinte.
- **Troca de modelo OU de prompt em produção = potencial quebra estrutural.**
  Exige janela de sobreposição; `PROMPT_VERSION` e o modelo ficam gravados em
  cada linha de escore.
- **Índice mensal:** use `c_llm` (cru) nos Blocos 2/3/6 — `c_llm_trunc` é só
  para figuras. `ep` é clusterizado por dia; `ep_iid` fica como referência.
- **Não use a coluna `texto_llm` da coleta.** Ela já vem formatada e sem data,
  o que impede o date-swap do teste T2. O prompt monta a mensagem sozinho.
- **Saídas com texto de terceiros não são versionadas** (`../dados/llm/`).
  Só `../dados/derivados/` entra no Git.

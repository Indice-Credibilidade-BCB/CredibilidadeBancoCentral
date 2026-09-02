# `llm/` — Índice de credibilidade $\hat{C}^{LLM}_t$ (Etapas 1–3)

Pontua, via LLM, a percepção de terceiros sobre o BCB em três dimensões e
agrega numa série mensal em [0,1]. Free-first (roda em tier gratuito),
retomável (cache = checkpoint) e agnóstico de provedor.

Decisões travadas: [`../docs/Etapa2_Piloto_e_Implementacao_DECIDIDO.md`](../docs/Etapa2_Piloto_e_Implementacao_DECIDIDO.md)
(D1–D10) e [`../docs/CONTEXTO_Projeto_Indice_Credibilidade_BCB.md`](../docs/CONTEXTO_Projeto_Indice_Credibilidade_BCB.md#42-arquitetura-interna-do-llm-resolvida--implementada-em-llm)
(Seção 4.2, D11–D15: vazamento temporal, T0, V-max/V-min, quarentena do
pesquisador, braço local) · Auditorias: [`../docs/AUDITORIA_2026-08-18.md`](../docs/AUDITORIA_2026-08-18.md),
[`../docs/AUDITORIA_2026-09-01.md`](../docs/AUDITORIA_2026-09-01.md)
· Guia do anotador: [`../docs/Guia_Anotacao_v1.md`](../docs/Guia_Anotacao_v1.md)

## Estrutura

```
config.yaml               provedores, estratos do piloto, listas de anonimização
prompts.py                prompts v1.0 (fonte única) + PROMPT_HASH (D13) + T0
corpus/from_coleta.py     adaptador: saída da coleta -> schema do índice
schema.py                 validação do corpus, dedup, clusters de wire
relevance.py              filtro de relevância (regex; gate LLM opcional)
providers/                camada de abstração (Sabiá/Groq via openai_compat,
                          Gemini, Claude/Anthropic — providers/anthropic_provider.py)
verificar_provedores.py   checa chave + 1 chamada mínima, por provedor
scorer.py                 pontuação em lote; --dupla-vmax-vmin (D12)
reliability.py            kappa ponderado, alfa de Krippendorff, halo
sample_pilot.py           amostra estratificada + planilhas cegas + T2-H
sandbox.py                quarentena de desenvolvimento: 10% do corpus (D13)
diagnostics/leakage.py    bateria anti-vazamento T2–T6; escada L1–L4
diagnostics/temporal_probe.py  T0: EAM + acurácia de episódio (D11)
t0_probe.py               round-trip do T0 com o provedor (4 níveis)
aggregate.py              série mensal; agregar_vmax_vmin + delta_t (D12)
local_encoder/            braço local (D7): BERTimbau + CORAL
  coral.py                 codificação/decodificação ordinal (puro numpy)
  dataset.py               exemplos de treino (L1) + blocos temporais (D7-ii)
  model.py                 BERTimbau + cabeça CORAL (torch/transformers)
  train.py                 fine-tuning (destilação prata+ouro)
  infer.py                 inferência no schema do scorer (plaga em aggregate.py)
fixtures/                 sintéticos do T5 (versionados: não têm copyright)
tests/                    suíte + regressões de auditoria + D11-D15 + braço local
```

Rode sempre a partir de `llm/`, com `PYTHONPATH=.` — os módulos se importam
pelo nome curto.

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=...     # aistudio.google.com (free, sem cartão)
export GROQ_API_KEY=...       # console.groq.com  (free, sem cartão)
export MARITACA_API_KEY=...   # plataforma.maritaca.ai (pedir créditos acadêmicos)
export ANTHROPIC_API_KEY=...  # console.anthropic.com (pago; custo do corpus é trivial, ver D5)

# confirma que as chaves configuradas realmente autenticam (1 chamada mínima cada)
python verificar_provedores.py
```

Braço local (`local_encoder/`, opcional — só quem for treinar/rodar o
BERTimbau precisa): `pip install torch transformers` (comentado no fim de
`requirements.txt`; pesado, por isso fora do install padrão).

## Fluxo

```bash
# 0) Corpus: converte dados/noticias.csv (saída de coleta/pipeline.consolidar())
python corpus/from_coleta.py

# 1) Amostra do piloto: 50 itens estratificados + 10 de borda + 15 do T2-H
python sample_pilot.py

# 2) Anotação humana dupla e cega (../docs/Guia_Anotacao_v1.md) -> gate
python reliability.py ../dados/llm/piloto/anotacao_consolidada.csv

# 3) Pontuar o piloto nos 4 provedores
python scorer.py --provider sabia             --input ../dados/llm/piloto/pilot_items.csv --mode piloto --out ../dados/llm/scores/pilot_sabia.jsonl
python scorer.py --provider gemini_flash_lite --input ../dados/llm/piloto/pilot_items.csv --mode piloto --out ../dados/llm/scores/pilot_gemini.jsonl
python scorer.py --provider groq_llama        --input ../dados/llm/piloto/pilot_items.csv --mode piloto --out ../dados/llm/scores/pilot_groq.jsonl
python scorer.py --provider claude            --input ../dados/llm/piloto/pilot_items.csv --mode piloto --out ../dados/llm/scores/pilot_claude.jsonl

# 4) T0 — sonda de identificabilidade temporal, escada L1-L4, no provedor líder
python t0_probe.py rodar --provider sabia --input ../dados/llm/piloto/pilot_items.csv --out ../dados/llm/piloto/t0_respostas.jsonl
python t0_probe.py relatorio --respostas ../dados/llm/piloto/t0_respostas.jsonl
# -> imprime EAM/acurácia por nível e o NÍVEL MÍNIMO que cega o modelo (vira --nivel-vmin abaixo)

# 5) Bateria anti-vazamento no melhor provedor (T2, T3, T5)
python scorer.py --provider sabia --input ../dados/llm/piloto/pilot_items.csv --mode piloto --date-mode omitida --out ../dados/llm/scores/t2_omitida.jsonl
python -c "import pandas as pd; from diagnostics.leakage import gerar_variantes_data as g; g(pd.read_csv('../dados/llm/piloto/pilot_items.csv')).to_csv('../dados/llm/piloto/pilot_t2.csv', index=False)"
python scorer.py --provider sabia --input ../dados/llm/piloto/pilot_t2.csv --mode piloto --date-mode trocada --out ../dados/llm/scores/t2_trocada.jsonl
python scorer.py --provider sabia --input ../dados/llm/piloto/pilot_items.csv --mode piloto --anonimizacao L4 --out ../dados/llm/scores/t3_L4.jsonl
python scorer.py --provider sabia --input fixtures/sinteticos_T5.csv --mode piloto --out ../dados/llm/scores/t5.jsonl

# 6) Antes de olhar a série agregada de verdade: congela a quarentena (D13)
python -c "import pandas as pd, sandbox; sandbox.congelar_manifesto(pd.read_parquet('../dados/llm/corpus.parquet'))"

# 7) Produção: escore duplo V-max/V-min (nível de 4) no provedor aprovado
python scorer.py --provider sabia --input ../dados/llm/corpus.parquet --mode producao \
    --dupla-vmax-vmin --nivel-vmin L2 --out ../dados/llm/scores/producao.jsonl

# 8) Série mensal (detecta sozinho se scores tem variante_vazamento dupla)
python aggregate.py --scores ../dados/llm/scores/producao.jsonl --corpus ../dados/llm/corpus.parquet --out ../dados/derivados/indice_mensal.csv

# 9) Braço local (D7), se D6 reprovar a API ou para robustez do Paper 1
python -m local_encoder.train --corpus ../dados/llm/corpus.parquet \
    --rotulos-prata ../dados/llm/scores/producao.jsonl \
    --rotulos-ouro ../dados/llm/piloto/gabarito_consenso.csv \
    --out-checkpoint ../dados/llm/checkpoints/bertimbau_coral_v1
python -m local_encoder.infer --checkpoint ../dados/llm/checkpoints/bertimbau_coral_v1 \
    --input ../dados/llm/corpus.parquet --out ../dados/llm/scores/bertimbau_local.jsonl
# -> aggregate.py na série local + diagnostics.leakage.comparar_t6(api, local) — só pós-2019 (D14)

# Testes
PYTHONPATH=. python -m pytest tests/ -q
```

## Notas operacionais

- **Retomada:** linhas com `erro` são reprocessadas ao reexecutar o mesmo
  comando; a agregação deduplica por `cache_key` mantendo o último sucesso.
  Ao bater o teto diário (RPD), o job encerra limpo e retoma no dia seguinte.
- **Troca de modelo OU de prompt em produção = potencial quebra estrutural.**
  Exige janela de sobreposição; `PROMPT_VERSION`, `PROMPT_HASH` (D13) e o
  modelo ficam gravados em cada linha de escore.
- **Claude/Anthropic não usa `temperature`.** A partir de Opus 5, "thinking"
  vem ligado por padrão e os parâmetros de amostragem são removidos da API —
  `providers/anthropic_provider.py` não passa `temperature`; determinismo
  vem de `effort` baixo + prompt restrito, não de amostragem. Os outros três
  provedores continuam usando `request.temperature=0.0` do config.
- **Índice mensal:** use `c_llm` (cru) nos Blocos 2/3/6 — `c_llm_trunc` é só
  para figuras. `ep` é clusterizado por dia; `ep_iid` fica como referência.
  Com `--dupla-vmax-vmin`, `c_llm` é alias de `c_llm_vmax` (série principal,
  D12); `c_llm_vmin` e `delta_t` são a robustez obrigatória.
- **Não use a coluna `texto_llm` da coleta.** Ela já vem formatada e sem data,
  o que impede o date-swap do teste T2. O prompt monta a mensagem sozinho.
- **A quarentena de desenvolvimento (D13) só protege se rodar ANTES de olhar
  a série agregada.** `sandbox.congelar_manifesto` é por hash de `item_id`
  (estável quando o corpus cresce) — nunca calibrar prompt, regra de
  agregação ou anonimização olhando os itens em `dados/derivados/sandbox_ids.csv`.
- **T6 (braço local vs. API) só é informativo pós-2019 (D14).** O pré-treino
  do BERTimbau cobre até ~2019; `comparar_t6` já aplica o corte.
- **Saídas com texto de terceiros não são versionadas** (`../dados/llm/`).
  Só `../dados/derivados/` entra no Git (inclui `sandbox_ids.csv`: só ids
  opacos, não reconstrói texto).

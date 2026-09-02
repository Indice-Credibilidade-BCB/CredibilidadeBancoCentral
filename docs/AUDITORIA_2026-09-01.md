# Auditoria de 2026-09-01 — D11-D15, braço local, provedor Claude, coleta/

Escopo: implementação das pendências D11–D15 (Seção 4.2.9 do doc de
contexto), braço local BERTimbau (D7), provedor Anthropic/Claude, utilitário
de verificação de chaves, e releitura de `coleta/` (que não tinha auditoria
própria até agora). Método: implementação + teste automatizado para cada
peça nova (`llm/tests/test_d11_d15.py`, `llm/tests/test_local_encoder.py`),
suíte completa (`pytest tests/ -q`: 28 passam, 1 pula por dependência
opcional ausente), smoke test ponta a ponta do braço local com o BERTimbau
real (não só sintético) e do provedor Claude contra a API real (chave
inválida de propósito, para confirmar que o request chega bem-formado ao
servidor).

---

## A. Bugs encontrados e corrigidos

**A1. [GRAVE] `diagnostics.leakage.anonimizar` quebrava com `NaN`.**
`t = texto or ""` não cobre `float('nan')`: NaN é *truthy* em Python, então
a linha mantinha `t = nan` e `_RE_DATAS.sub(...)` lançava `TypeError`. Em
produção, qualquer item com `lead` ou `paragrafo_1` faltante (`NaN`, comum
em CSV/parquet lido com pandas) quebraria `aplicar_anonimizacao` inteiro —
ou seja, T3, T0, o scorer com `--dupla-vmax-vmin` e o braço local (que
mascara em L1 antes de treinar) todos dependiam de um corpus sem nenhum
campo faltante para não crashar no meio da execução. Corrigido com
`pd.isna(texto)`, que cobre `None`, `NaN` e `NaT`. Teste de regressão:
`test_anonimizar_aceita_nan`.

**A2. [GRAVE] Prints com símbolo fora de cp1252 derrubavam o script no
Windows.** `coleta/diagnostico.py` (separador `"═" * 76`) e
`coleta/pipeline.py` (seta `→` em `dividirTrabalho`/`consolidar`) usam
caracteres que **não existem** no code page 1252 — o padrão de console do
Windows em português/inglês dos EUA. `print()` desses caracteres lança
`UnicodeEncodeError` e mata o processo no meio de uma coleta ou de um
relatório, depois de já ter feito trabalho (requisições pagas/gratuitas
consumidas, arquivos parcialmente gravados). Não é hipotético: reproduzido
neste ambiente (`sys.stdout.encoding == 'cp1252'`). Corrigido trocando por
ASCII (`"="`, `"->"`). Mesma correção aplicada preventivamente em
`local_encoder/train.py` (símbolo "κ" no print de progresso — nunca chegou
a ser commitado sem a correção) e em `verificar_provedores.py` (✓/✗/·).
Presente só em COMENTÁRIOS/docstring (nunca em `print()` de verdade) segue
inofensivo — não mexido.
*Limitação residual:* não foi feita uma varredura de todo o repositório
fora de `coleta/` e `llm/` (não havia mais nenhuma outra pasta com `.py`
além de `mercado/scrappingDI.py`, que já foi conferido e não imprime nada
problemático).

**A3. [GRAVE] Provedor Claude/Anthropic passava `temperature`, que o SDK
nem aceita.** A partir de Claude Opus 5, "thinking" adaptativo vem ligado
por padrão e os parâmetros de amostragem (`temperature`/`top_p`/`top_k`)
foram **removidos** da assinatura de `messages.create()` — não é um erro
HTTP 400 do servidor, é `TypeError` do próprio cliente Python, então
qualquer chamada quebraria antes de sair da máquina. Descoberto rodando
`verificar_provedores.py` contra a API real (com chave inválida de
propósito, só para confirmar a forma do request). Corrigido removendo
`temperature` da chamada; documentado no docstring do provedor e no README
do `llm/` para não confundir quem comparar as saídas dos 4 provedores (os
outros 3 continuam determinísticos por `temperature=0.0`; o Claude é
determinístico por `effort` baixo + prompt restrito).

**A4. [MENOR] `torch.load` sem `weights_only=True` no braço local.**
`local_encoder/infer.py` carregava o checkpoint com unpickling irrestrito
(aviso do próprio PyTorch: permite execução de código arbitrário se o
arquivo for adulterado). Nosso checkpoint só tem tensores + primitivos
(`modelo_base`, `num_classes`), então `weights_only=True` funciona sem
mudar nada — corrigido.

---

## B. Novidades desta sessão (não são bugs; registradas para o pré-registro)

- **D11 (T0):** `diagnostics/temporal_probe.py` (lógica pura, testada com
  casos sintéticos de modelo "cego" e "vidente") + `t0_probe.py` (round-trip
  real com provedor). L4 acrescentado à escada de anonimização
  (`diagnostics/leakage.py`): mascara Selic/IPCA/câmbio/PIB preservando
  palavras de direção ("subiu", "recuou").
- **D12 (V-max/V-min):** `scorer.py --dupla-vmax-vmin` roda as duas
  variantes na mesma passagem, cache com sufixo `|vmax`/`|vmin`;
  `aggregate.agregar_vmax_vmin` publica as duas séries + `delta_t`.
  `aggregate.agregar` ganhou uma guarda: recusa (com `ValueError`) scores
  com mais de uma `variante_vazamento` misturada, para não silenciosamente
  dobrar a contagem de itens numa média sem sentido.
- **D13 (quarentena):** `prompts.PROMPT_HASH` gravado em cada escore;
  `sandbox.py` separa 10% do corpus por hash do `item_id` (estável ao
  corpus crescer — testado explicitamente: itens em sandbox não trocam de
  lado quando o corpus dobra de tamanho).
- **D14/T6:** `diagnostics.leakage.comparar_t6` descarta (não só esconde)
  meses anteriores a 2019-01-01 antes de comparar API vs. braço local.
- **Tendência em t (T2/T3):** `comparar_variantes` ganhou parâmetro `datas`
  opcional; reporta correlação de `|delta|` com o tempo — diagnóstico
  auxiliar, não critério de reprovação.
- **Braço local (D7), de verdade:** `local_encoder/` — CORAL (`coral.py`,
  puro numpy), dataset com anonimização L1 e validação cruzada por BLOCOS
  TEMPORAIS (não aleatória — `dividir_blocos_temporais`), fine-tuning
  (`train.py`) e inferência no schema do scorer (`infer.py`). Testado
  ponta a ponta baixando e treinando o BERTimbau real (`neuralmind/
  bert-base-portuguese-cased`) sobre um corpus sintético de 24 itens: o
  treino roda, a validação por bloco temporal futuro funciona, o checkpoint
  salva e recarrega, e a inferência reproduz o padrão aprendido.
- **Provedor Claude** (`providers/anthropic_provider.py`): 4ª medida
  independente (D5), efeito colateral útil para a tese de robustez à troca
  de modelo. Custo do corpus inteiro é trivial mesmo no modelo mais caro.
- **`verificar_provedores.py`:** checa os 4 provedores (chave configurada +
  1 chamada mínima real) antes de rodar o piloto de verdade.

---

## C. Releitura de `coleta/` (não tinha auditoria própria)

Nenhum bug de lógica encontrado além do A2 (encoding de print). Pontos
conferidos e OK: `armazenamento.py` grava um arquivo por veículo POR PESSOA
(evita conflito de merge); `sincronizacao.py` usa `cwd=cfg.RAIZ` em todo
comando git, então funciona independente de onde o script é chamado;
`configuracao.RAIZ` resolve a partir de `__file__`, não do diretório de
trabalho; `pipeline.consolidar` deduplica por URL normalizada e marca wire
por título+lead — comportamento coerente com o que `llm/schema.py` espera
receber depois. `.gitignore` da raiz nega `dados/*` por padrão e libera só
o que não reconstrói texto — conferido caractere por caractere, correto.

---

## D. Limitações residuais conhecidas (monitorar, não corrigir agora)

- **T0 com poucos itens pode dar acurácia de episódio como `NaN`** quando
  NENHUM palpite de ano cai em qualquer estrato do piloto (ex.: modelo
  chuta um ano muito fora da faixa 2000-2026). `avaliar_t0` trata `NaN`
  como compatível com cegueira (`cego = eam>=4 and (isna(acc) or acc<=0,25)`)
  — decisão deliberada (não localizar nem um episódio plausível é sinal
  mais forte de cegueira, não uma lacuna do critério), mas vale conferir
  com dados reais do piloto se isso não mascara um caso diferente.
- **L4 (mascarar numéricos) só cobre número que vem DEPOIS do indicador**
  numa janela curta (`"Selic ... 14,25%"` funciona; `"14,25% de alta da
  Selic"` escapa). Mesma classe de limitação documentada para a máscara de
  nomes (fronteira de palavra) desde a auditoria de 2026-08-18.
- **CORAL sem a restrição de bias estritamente decrescente** do paper
  original — na implementação atual (`local_encoder/model.py`), a
  monotonicidade dos limiares é aproximada, não garantida algebricamente.
  Na prática (testado com gradiente descendente simples) não impediu o
  aprendizado nem gerou decodificação inconsistente nos casos testados,
  mas não foi estressado com dados reais em escala.
- **Provedor Claude não testado com chave real** (só com chave inválida,
  para confirmar a forma do request). O comportamento além de
  "autentica/não autentica" — parsing da resposta JSON de verdade, latência,
  taxa de refusal — só será conhecido rodando `verificar_provedores.py` e
  depois o piloto com uma chave válida.

---

## E. Achados da primeira coleta e teste de LLM reais (mesmo dia, sessão seguinte)

Escopo: primeira coleta de verdade (2016-2019, depois expandida), primeiro
teste real dos provedores LLM com chaves válidas (Gemini, Maritaca). Método:
rodar de ponta a ponta e investigar qualquer número que não batesse com a
expectativa antes de seguir — os quatro achados abaixo só apareceram assim,
nenhum teria sido pego por revisão de código estática.

**E1. [CRÍTICO] `coleta/pipeline.consolidar()` reduzia a Valor a ~1
registro.** A busca da Globo devolve um redirecionador de clique
(`measures.globo.com/v1/click?...&u=<url real>`) cujo *path* é idêntico
para toda matéria — só a query string muda. `consolidar()` normalizava a
URL removendo a query ANTES de deduplicar, então todo artigo da Valor
colapsava na mesma chave. Rodando a coleta real de 2016-2019: 5.262 brutos
da Valor viraram 1 registro no `noticias.csv` — o bug já tinha sido
corrigido no adaptador `llm/corpus/from_coleta.py` (que desembrulha a URL
antes de gerar `item_id`), mas nunca tinha sido portado para `coleta/`, que
é onde o dano acontece primeiro (o adaptador nunca via os outros 5.261
registros, porque já tinham sido descartados). Corrigido: `utilitarios.
desembrulharUrl()` (nova função) aplicada em `consolidar()` ANTES de montar
`chave_url`, e a URL real substitui a de tracking no dataset final (a de
tracking expira; não serve pra citar fonte). Resultado antes/depois no
mesmo dataset: 6.882 → 8.756 registros após dedup, 6.661 → 8.450 sem
replicação de agência. Sem este achado, o corpus do índice teria ~22% menos
itens, com um viés sistemático deletando quase toda a Valor — um dos
veículos mais importantes do projeto.

**E2. [GRAVE] Bug de planejamento: comparação com `fim` em vez de `ini`.**
`planejamento.expandir()` decidia se uma consulta precisa ser subdividida
comparando o alcance da paginação profunda com o `fim` da janela — quase
sempre uma data passada, então a comparação era quase sempre verdadeira e a
consulta nunca subdividia. Pego na prática: a consulta "Copom" (sem
divisor) na Valor truncou em 2019-03, sem cobrir nada de 2016 até
início-2019. Corrigido: comparação agora é com `ini` (o que de fato precisa
alcançar). Validado tanto isoladamente (`expandir()` sozinho) quanto na
coleta real — as sub-consultas geradas pelo fix se revelaram 100%
duplicatas por URL de artigos já achados por outras consultas (Selic,
política monetária etc., também subdivididas por presidente), confirmando
que NENHUMA notícia única tinha sido perdida por esse bug especificamente
nesta janela — mas o bug em si é real e teria causado perda de dado em
janelas/termos onde a sobreposição fosse menor. Vale para qualquer coleta
futura, não só a de 2016-2019.

**E3. [MODERADO] Modelo `gemini-2.5-flash-lite` foi descontinuado para
novos usuários.** `verificar_provedores.py` (chave real, 01/09/2026) deu
404 "This model ... is no longer available to new users". Trocado para
`gemini-3.1-flash-lite` (testado e funcionando com a chave real). Ilustra
por que o README já avisa "conferir modelo free vigente" — não é
hipotético, o modelo mudou entre a sessão que escreveu o config e a sessão
que testou a chave, no mesmo dia.

**E4. [MODERADO] Sabiá devolve `d1: null` em vez de nota 3.** Rodando 5
itens reais do corpus: 2 de 5 (40%, amostra pequena) voltaram com
`"d1": null` quando o modelo não via nenhuma menção ao BCB/meta no texto —
apesar do prompt instruir explicitamente "D1 sempre pontuada... 3 = neutro,
incerto, ou sem sinal claro". `scorer.parse_json_resposta` tratava `d1`
nulo como falha de parse total, descartando o item. Corrigido: `d1` nulo ou
ausente agora é coagido para 3 (o "sem sinal" que o próprio prompt já
define), preservando o dado em vez de perdê-lo e gastar retry. `d1` fora da
escala 1-5 (resposta de fato garbled) continua sendo tratado como falha
real. Teste de regressão: `test_parser_d1_nulo_vira_neutro`. Observação
para a Etapa 2: esse comportamento do Sabiá é ele mesmo um dado sobre
aderência ao prompt — vale registrar a taxa de `d1=null`-antes-da-coerção
por provedor quando o piloto rodar de verdade, é um segundo sinal de
qualidade além do κ_qw contra o ouro.

**Chaves testadas nesta sessão:** Gemini e Maritaca autenticam e pontuam
com sucesso (chaves reais do usuário). Groq e Claude ainda não têm chave
cadastrada. Custo de crédito da Maritaca: usuário confirmou R$70 de saldo
ativo — suficiente para o piloto inteiro e uma fração relevante da
produção (ver estimativa de custo em D5, Etapa2_Piloto..._DECIDIDO.md).

---

## F. Expansão da coleta (2011–2026) e dois bugs de ledger encontrados em produção

Escopo: expansão autônoma da coleta de 2016-2019 para 2011–2026 (hoje), em
janelas de ~2 anos (2020-2022, 2022-2024, 2024-hoje, 2011-2013, 2013-2015,
2015-2016), a pedido do usuário. Achados só visíveis rodando o pipeline de
verdade contra janelas diferentes — nenhum apareceria em revisão de código.

**F1. [CRÍTICO] Ledger do motor Globo não distinguia janela de datas.**
`coletarTudo()` usava `chave = f"{veiculo}||{consulta}"` para marcar consulta
concluída. Termos subdivididos por presidente (ex.: "Selic Tombini") geram o
MESMO texto de consulta em janelas diferentes — rodar 2020-2022 depois de
2016-2019 fez a Valor pular TODAS as 22 consultas do motor Globo, achando
que já tinham sido feitas (mesmo texto), quando na verdade precisavam de
varredura nova para o período novo. Resultado: primeira tentativa de
2020-2022 voltou com **0 registros da Valor**. Corrigido: chave passou a
incluir a janela (`||{ini:%Y%m%d}-{fim:%Y%m%d}`). O motor WordPress já
incluía o ano na chave por outro motivo e nunca teve esse problema.

**F2. [CRÍTICO] Ano de borda do motor WordPress marcado como feito sem
nunca ter sido buscado.** `range(ini.year, fim.year + 1)` inclui o ano de
`fim` mesmo quando `fim` é exatamente 1º de janeiro (ex.: fim=2020-01-01
inclui ano=2020, mas a fatia real de datas fica vazia — `a >= b`). O código
antigo marcava esse ano como concluído mesmo sem fazer nenhuma requisição.
Efeito cascata: a janela 2016-2019 contaminou "2020"; a primeira tentativa
(pré-fix) de 2020-2022 contaminou "2022" da mesma forma. Cada contaminação
só apareceu quando uma janela POSTERIOR tentou coletar aquele ano de
verdade e o achou "já feito" — silenciosamente, sem erro. Detectado
comparando cobertura mensal esperada vs. real (Poder360/InfoMoney/Money
Times com o ano inteiro zerado). Corrigido: o cálculo de `a`/`b` agora roda
ANTES de decidir marcar o ledger, e anos degenerados são pulados sem tocar
no ledger. As 21 entradas contaminadas de "2020" e as 21 de "2022" foram
removidas manualmente de `dados/concluidas/lorenzo.txt` e as janelas
correspondentes foram re-rodadas — confirmado por auditoria completa do
ledger (todo ano real tem exatamente 21 entradas = 7 termos × 3 veículos
wordpress, sem falta nem sobra).

**F3. [GRAVE, só nos meus scripts de verificação] `pd.to_datetime(...,
errors="coerce")` sem `format="mixed"` descarta a maioria das linhas em
silêncio.** As datas no `noticias.csv` vêm de fontes diferentes (API da
Globo, API WordPress) em formatos de string diferentes. `coleta/
pipeline.py` já usa `format="mixed"` internamente (correto). Os scripts
AD-HOC de validação usados ao longo desta sessão (fora do pipeline
versionado) não usavam esse parâmetro — o auto-detector do pandas travava
no primeiro formato que via e devolvia `NaT` pra tudo que não casasse.
Resultado: uma checagem de cobertura reportou o período terminando em
2018-05, com 51 mil de 66 mil linhas silenciosamente viradas `NaT` — os
dados estavam certos o tempo todo, só a checagem estava errada. Lição
registrada: qualquer script (mesmo descartável) que releia `noticias.csv`
tem que usar `format="mixed"`, igual o pipeline.

**Resultado final:** dataset consolidado cresceu de 6.882 (só 2016-2019,
com o bug da Valor) para **66.379 brutos / 64.838 sem replicação de
agência**, cobrindo **2011-01 a 2026-09 (hoje) sem nenhum mês zerado no
total geral**. Gaps que restam são todos por veículo e têm explicação
estrutural conhecida: Valor (6 meses, jan-jun/2011 — arquivo da Globo não
alcança); Money Times/Poder360 (~70 meses cada, antes da fundação em 2016);
O Globo (139 meses, antes de out/2022 — limite do índice de busca do
tenant, ver Seção E deste documento). `dados/llm/corpus.parquet`
reconstruído: 66.204 itens.

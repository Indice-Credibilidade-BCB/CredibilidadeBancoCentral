# Etapa 2 — Piloto e Implementação (DECIDIDO)

> **Documento de decisões — sessão de 17/08/2026 (decisão autônoma).**
> Complementa `Secao_4.2_Arquitetura_LLM_RESOLVIDA.md` e o documento de
> contexto. Fecha a pendência única que travava a Etapa 2 (nº de anotadores),
> adiciona cinco melhorias à arquitetura e entrega a implementação: prompts
> v1.0, guia de anotação v1 e pipeline Python testado (`pipeline/`).

---

## 0. Avaliação do estado (17/08/2026)

- **Seção 4.2**: fechada (6 decisões). Nada aqui a contradiz; as decisões
  abaixo estendem ou operacionalizam.
- **Pendência que travava a Etapa 2**: número de anotadores — **fechada (D1)**.
- **Etapa 0 (corpus)**: unidade disponível confirmada = **título + lead +
  1º parágrafo**. Compatível com a decisão travada ("título + até dois
  parágrafos iniciais"); o lead é o que a decisão original chamava de primeiro
  bloco. Nenhuma revisão necessária; o gate de 25% de `contexto_insuficiente`
  segue valendo.
- **Entregue nesta sessão**: prompts v1.0; guia de anotação; pipeline
  (amostragem estratificada, scorer com cache/limites de free tier,
  κ/α validados contra referência externa, agregação com FE de veículo e
  cluster wire, bateria anti-vazamento T2–T5, template de itens sintéticos).
  Suíte de testes passando.

---

## 1. Decisões desta sessão

### D1 — Anotadores: **2**, dupla anotação cega; κ de Cohen quadrático como gate
- 2 anotadores (Berrante + 1 colega a definir; Sebastian é candidato natural),
  anotando os 50 itens de forma **independente e cega**.
- **Gate mantido**: κ_qw(D1) ≥ 0,6 prossegue. **Contingência nova**: κ_qw em
  (0,5; 0,6) aciona um 3º anotador desempatador apenas nos itens discordantes
  e a métrica migra para α de Krippendorff; κ_qw < 0,5 volta à Etapa 1
  (revisão de guia/dimensões).
- **α de Krippendorff (métrica ordinal) é reportado sempre**, junto do κ:
  lida com faltantes (`d2/d3 sem sinal`) e generaliza para 3+ anotadores sem
  mudar de arcabouço.
- **Adjudicação**: κ é o da rodada cega (imutável); depois, reunião única
  discute todas as discordâncias e produz o **rótulo-ouro de consenso**, que é
  a referência para avaliar os LLMs (κ_qw modelo vs. ouro).
- *Racional*: em IC, o recurso escasso é hora de anotador, não API (ver D5:
  pontuar o corpus inteiro custa < R$120 mesmo pagando). Dois anotadores
  preservam o gate pré-registrado (Cohen) e o desenho de contingência cobre o
  caso ambíguo sem custo antecipado.

### D2 — Unidade de anotação: título + lead + 1º parágrafo (confirmada)
Flag `contexto_insuficiente` por item/anotador; gatilho de revisão da unidade
se > 25% (inalterado). O anotador dá a melhor nota mesmo com a flag.

### D3 — **Novo estágio: filtro de relevância antes da anotação/pontuação**
- Estágio 1 (regex, `relevance.py`): mantém itens que mencionam o universo
  BCB/meta/política monetária; descarta procedurais óbvios (agenda,
  calendário de reuniões).
- Estágio 2 (opcional, `PROMPT_RELEVANCIA`): LLM resolve limítrofes.
- O piloto inclui **10 itens de borda extras** (fora da amostra do κ) só para
  validar o filtro.
- *Racional*: forçar nota 1–5 em item sem sinal ("Copom se reúne amanhã")
  injeta ruído no índice e derruba o κ pelo motivo errado. A regra travada
  "sem menção relevante → sem observação" ganha implementação concreta.

### D4 — Escalas ancoradas + tratamento de "sem sinal"
- Âncoras textuais por nível para D1/D2/D3 (idênticas no guia humano e no
  prompt — humano e LLM seguem a mesma régua).
- D1 sempre pontuada (corpus já filtrado; 3 = neutro/sem sinal claro).
- D2/D3 admitem `sem_sinal` (null) quando o texto não aborda a dimensão;
  tratado como **faltante** nas diagnósticas (o α lida com isso nativamente).
  Evita confundir "postura neutra" com "ausência de sinal".

### D5 — Provedores free-first (verificado em 17/08/2026)
Piloto pontua os mesmos 50 itens em **três provedores gratuitos**, cobrindo a
fronteira custo-qualidade:

| Provedor | Modelo | Acesso | Limites free (aprox.; conferir no console) |
|---|---|---|---|
| **Maritaca (primário)** | Sabiá (família atual: Sabiá 4; alternativa barata: sabiazinho-3) | Endpoint OpenAI-compatible `https://chat.maritaca.ai/api`; **pedir créditos acadêmicos** no programa para ensino/pesquisa (formulário no site; projeto de IC/FEA-USP se qualifica) | Depende dos créditos concedidos; novos usuários ganham R$20 |
| **Gemini Flash-Lite (baseline)** | gemini-2.5-flash-lite (ou 3.x Flash-Lite free vigente) | AI Studio, sem cartão | ~15 RPM; ~1.000–1.500 req/dia (houve corte de cotas em dez/2025; teto varia por conta/região) |
| **Groq (open-weights)** | llama-3.3-70b-versatile | `https://api.groq.com/openai/v1`, sem cartão | ~30 RPM; ~1.000 req/dia p/ 70B; gargalo real é TPM/TPD |

- **Produção (Etapa 3)** = provedor com maior κ_qw contra o rótulo-ouro,
  **condicionado à aprovação na bateria anti-vazamento (D6)**.
- **Custo de contingência é trivial**: itens de ~600 tokens de entrada e ~60 de
  saída ⇒ corpus de 30 mil itens ≈ 20 M tokens ⇒ **sabiazinho-3 ≈ R$25–30;
  Sabiá-3 ≈ R$100–120** (preços R$1/R$3 e R$5/R$10 por milhão, in/out). Ou
  seja: free tier é conveniência, não restrição; nunca deixar o teto gratuito
  ditar decisão metodológica.
- Ressalva registrada: no free tier do Gemini, os dados podem ser usados pelo
  Google para melhoria de produto. O corpus é texto público de imprensa, sem
  dado pessoal sensível — aceitável; ainda assim, preferir Maritaca (descarta
  dados após a resposta, segundo a documentação) para a série de produção.
- O trio dá, de graça, o dado que faltava para a tese do projeto sobre robustez
  à troca de modelo: **três medidas independentes do mesmo piloto**.

### D6 — Bateria anti-vazamento formalizada (T1–T6), com critérios de reprovação
O vazamento (look-ahead) é o viés central: LLMs de fronteira "sabem" que 2015
estourou a meta e que 2019 ancorou. Prompt restrito é necessário, não
suficiente — por isso a bateria empírica, pré-registrada aqui:

| Teste | O que faz | Critério de **reprovação** |
|---|---|---|
| **T1** Prompt restrito | Restrição temporal explícita no sistema (v1.0) | — (desenho) |
| **T2** Date-swap | Repontuar subamostra com data **omitida** e **trocada** (±5 anos); Δ = nota_variante − nota_base | corr(Δ, desfecho futuro realizado) significativa a 5% **e** \|ρ\| ≥ 0,25 |
| **T2-H** Look-ahead humano | Reanotar ~15 itens semanas depois, com data e nomes mascarados | inconsistência intra-anotador concentrada em eras "conhecidas" |
| **T3** Anonimização | Mascarar em níveis: L1 datas; L2 +autoridades do BC; L3 +políticos. Se a nota muda ao esconder **quem** é a autoridade, o modelo usa prior de era/pessoa, não o texto | mesmo critério do T2 sobre Δ por nível |
| **T4** Resíduo preditivo | Resíduo do escore LLM (controlando o escore humano) regredido na **surpresa inflacionária futura** (IPCA realizado − Focus na data), erro Newey-West | coeficiente significativo a 5% |
| **T5** Itens sintéticos | ≥10 textos fabricados idênticos, "datados" em era boa vs. ruim (template com 8 pares entregue; expandir a 10) | diferença de médias entre eras significativa a 5% (Welch) |
| **T6** Benchmark de cutoff conhecido | Série do encoder local (D7) vs. série da API; divergências concentradas ao redor de desfechos notórios indicam vazamento da API | inspeção estruturada + eventos |

**Regra de decisão**: reprovação em T2, T4 ou T5 ⇒ a produção migra para o
braço local (D7). Aprovação com ressalvas (efeitos pequenos) ⇒ produção na API
+ T6 contínuo como monitor. Os resultados viram subseção de diagnóstico do
Paper 1 (é força, não fraqueza: nenhum índice textual publicado para o Brasil
reporta isso).

Nota importante: **anotadores humanos também têm look-ahead** (sabem o que
aconteceu). O guia impõe a mesma restrição do prompt e o T2-H mede o resíduo.
O ouro humano não é "verdade sem viés"; é a régua de *percepção-no-texto* que
humano e máquina devem compartilhar.

### D7 — Braço local reaberto: encoder BERTimbau com cutoff conhecido
(Reabre, com desenho e gatilhos, o "fine-tuning pós-Etapa 3" já previsto; a
Seção 6.7 do documento de contexto já apontava "encoder fine-tuned de cutoff
conhecido" como mitigação.)

- **Modelo**: BERTimbau (neuralmind, base ou large), pré-treinado no brWaC
  (corpus ≤ ~2019) ⇒ **cutoff de pré-treino conhecido e anterior a boa parte
  da amostra**; um classificador encoder não faz "recall generativo" de
  desfechos — estruturalmente a opção mais à prova de vazamento.
- **Cabeça**: regressão ordinal (CORAL) ou classificação com perda ponderada
  quadrática (coerente com o κ_qw).
- **Dados de treino**: destilação — rótulos-prata do provedor de API aprovado
  (2–5 mil itens) + rótulos-ouro humanos (piloto + ~300 itens anotados por um
  único anotador depois de κ estabelecido).
- **Anti-contaminação da destilação**: o professor (API) pode vazar; o aluno
  só herda o vazamento que estiver correlacionado a traços textuais de era.
  Mitigações: (i) **entrada de treino em anonimização L1 (sem datas)**;
  (ii) validação cruzada **por blocos temporais** (treina numa era, testa em
  outra); (iii) o ouro humano ancora a calibração.
- **Papéis**: instrumento do T6 desde já; produção se D6 reprovar a API ou se
  houver instabilidade de provedor; robustez do Paper 1. Compute: GPU de
  Colab basta (BERT-base) — custo zero.
- **Gatilhos para virar produção**: reprovação em T2/T4/T5; **ou** κ_qw do
  encoder vs. ouro ≥ κ_qw da melhor API − 0,05 (paridade prática) com a
  vantagem estrutural de cutoff.

### D8 — Esquema de dados + deduplicação wire
- Schema obrigatório (`schema.py`): `item_id, data_publicacao, veiculo,
  tipo_veiculo {imprensa, research}, titulo, lead, paragrafo_1, fonte_ref`.
- Dedup exata por (veículo, título normalizado, data).
- **Novo**: matéria de agência replicada entre veículos (Reuters no Valor, na
  Folha e no Estadão) forma um `wire_cluster` e **conta uma vez por mês** na
  agregação — evita triplicar o mesmo sinal e enviesar meses de notícia quente.

### D9 — Operação sob free tier: cache = checkpoint
- Rate limiter respeita RPM e RPD por provedor; ao bater o teto diário o job
  encerra limpo e **retoma no dia seguinte com o mesmo comando** (cache JSONL
  por `(provedor, modelo, prompt_version, item, variante)`).
- Throughput: piloto (50 itens × 3 provedores) = 1 dia. Corpus de 30 mil no
  Gemini free (~1.000/dia) ≈ 30 dias corridos de batch — ou R$25–30 no
  sabiazinho para fazer em horas. Decidir na Etapa 3 conforme créditos.
- Cada linha de escore registra `provider, model, prompt_version, variante` —
  troca de modelo **ou de prompt** em produção = potencial quebra estrutural
  ⇒ janela de sobreposição (decisão já travada, agora instrumentada).

### D10 — Checagem de halo operacionalizada
Correlação de Spearman entre D1/D2/D3 por fonte (`reliability.
correlacao_dimensoes`). Alerta se corr(LLM) exceder corr(humana) em > 0,20 em
qualquer par — indício de que o modelo não tratou as dimensões como
independentes (revisar prompt antes da Etapa 3).

---

## 2. Prompt v1.0 (piloto — texto integral)

Fonte única: `pipeline/prompts.py`. Produção = idêntico, com saída reduzida a
`{"d1":..., "d2":..., "d3":...}` e sem justificativa.

```
Você é um anotador para pesquisa acadêmica em macroeconomia. Sua tarefa é ler
o trecho de uma notícia ou relatório sobre o Banco Central do Brasil (BCB) e
avaliar EXCLUSIVAMENTE a percepção que o TEXTO transmite, na data de
publicação indicada.

RESTRIÇÃO TEMPORAL ABSOLUTA: comporte-se como se você estivesse na data de
publicação. Não use nenhum conhecimento sobre eventos, dados, decisões ou
desfechos posteriores a essa data. Não use conhecimento externo sobre "o que
aconteceu depois". Baseie-se apenas no que o texto afirma ou implica.

Avalie TRÊS dimensões, de forma INDEPENDENTE (a nota de uma NÃO deve
influenciar a outra):

D1 — Probabilidade percebida de cumprimento da meta de inflação (principal).
O texto trata a meta como provável de ser cumprida?
1 = descumprimento tratado como certo ou já consumado
2 = cumprimento tratado como improvável
3 = neutro, incerto, ou sem sinal claro sobre a meta
4 = cumprimento tratado como provável
5 = cumprimento tratado como certo / inflação sob controle

D2 — Confiança na condução da política monetária (diagnóstica).
[escala 1–5; d2_sem_sinal quando o texto não aborda]

D3 — Autonomia percebida do BCB (diagnóstica).
[escala 1–5; d3_sem_sinal quando o texto não aborda]

REGRAS:
- Percepção, não fato: avalie o que o TEXTO transmite, não a sua própria
  avaliação da economia brasileira.
- Pessimismo macroeconômico (inflação alta, câmbio depreciado, atividade
  fraca) NÃO é, por si só, descrédito na autoridade monetária. Só rebaixe
  D1/D2 se o texto conectar o pessimismo à incapacidade, inação ou falta de
  credibilidade do BCB, ou à improbabilidade da meta.
- Ceticismo implícito, ironia e escolha de fontes céticas contam como sinal.
- Declarações do próprio BCB reproduzidas no texto não são percepção de
  terceiros; pese como o VEÍCULO as enquadra.

Responda SOMENTE com JSON válido, sem markdown, no formato:
{"d1": <1-5>, "d2": <1-5 ou null>, "d2_sem_sinal": <true/false>,
 "d3": <1-5 ou null>, "d3_sem_sinal": <true/false>,
 "justificativa": "<até 30 palavras>"}
```

A mensagem de usuário por item traz `DATA DE PUBLICAÇÃO / VEÍCULO / TÍTULO /
LEAD / PRIMEIRO PARÁGRAFO`; o campo de data é parametrizável (real / omitida /
trocada) para o T2 sem tocar no prompt.

---

## 3. Protocolo do piloto (passo a passo executável)

1. **Corpus** (Etapa 0) entregue em `data/corpus.parquet` no schema de D8.
2. **Chaves**: AI Studio (Gemini) e Groq — imediato, sem cartão; Maritaca —
   enviar o pedido de créditos acadêmicos já (aprovação leva dias; enquanto
   isso, R$20 iniciais cobrem o piloto com folga).
3. `python sample_pilot.py` → 50 itens estratificados (5 episódios de tensão +
   calmaria, ver `config.yaml`) + 10 de validação do filtro + duas planilhas
   de anotação cega.
4. **Anotação humana** (Guia v1; ~2h por anotador) → `reliability.py` →
   κ_qw(D1) e α. Gate de D1.
5. **Adjudicação** → rótulo-ouro.
6. **Pontuar nos 3 provedores** (`scorer.py`, ~10 min cada no free tier) →
   κ_qw(modelo, ouro) por provedor + checagem de halo (D10).
7. **Bateria anti-vazamento** no melhor provedor: T2 (omitida + trocada),
   T3 (L2/L3), T5 (sintéticos — expandir template para 10 pares). T4 exige a
   série de surpresa inflacionária (ver §5).
8. **Decisão de produção** conforme D6/D7 → Etapa 3 (corpus completo, modo
   produção, agregação `aggregate.py`) e início da rotulagem expandida para o
   BERTimbau.

Falha no gate: κ_qw ∈ (0,5; 0,6) → 3º anotador nos discordantes + α;
κ_qw < 0,5 → revisão de guia/dimensões (Etapa 1) antes de reamostrar.

---

## 4. Pendências que dependem de dados (não de decisão)

1. Ajustar os **estratos** do `config.yaml` à cobertura real do corpus
   (início da série; se não houver 2002–03, redistribuir).
2. **Série de desfecho futuro** para T2/T4: surpresa inflacionária 12m
   (IPCA realizado − mediana Focus na data do item). Deriva de SGS/Focus —
   candidata natural para o Sebastian, que já opera os dados de mercado.
3. Nome do **2º anotador** (e do 3º de contingência).
4. Expandir os **itens sintéticos** de 8 para 10+ pares.
5. Confirmar no console os tetos free vigentes na semana do piloto (mudam com
   frequência; o config usa margens conservadoras).

---

## 5. Registro de verificação dos provedores (17/08/2026)

- Maritaca — créditos para ensino/pesquisa e descarte de dados pós-resposta:
  maritaca.ai/research e maritaca.ai/en; endpoint OpenAI-compatible e R$20
  iniciais: github.com/maritaca-ai/maritalk-api; preços (sabiazinho-3 R$1/R$3,
  Sabiá-3 R$5/R$10 por Mtok): docs.maritaca.ai/pt/precos e imprensa (TechTudo,
  jun/2025).
- Gemini free tier — cortes de dez/2025 e tetos por modelo (Flash-Lite ~15 RPM
  / ~1.000–1.500 RPD; variação por conta/região; modelos 3.x Flash-Lite free):
  aifreeapi.com, pecollective.com, yingtu.ai (verificações mar–jul/2026).
- Groq free tier — sem cartão, OpenAI-compatible, ~30 RPM e ~1.000 RPD para
  llama-3.3-70b-versatile, com TPM/TPD como gargalo real:
  klymentiev.com/blog/groq-pricing, grizzlypeaksoftware.com,
  tokenmix.ai (abr–jun/2026).

> Tetos de free tier mudam sem aviso: tratar os números acima como ordem de
> grandeza para planejamento; a fonte operacional é o console de cada
> provedor + os headers de rate limit em tempo de execução.


---

## Apêndice A — Auditoria de 2026-08-18 (pós-implementação, pré-dados)

Auditoria completa de código e vieses em `AUDITORIA_2026-08-18.md`. Efeitos
sobre as decisões D1–D10 (nenhuma decisão revertida; três refinadas):

- **D6/T5 (emenda ao pré-registro):** critério primário passa de Welch para
  **t pareado por `texto_grupo`** (o desenho é pareado por construção). Welch
  vira robustez. Emenda feita antes de qualquer coleta; endurece o teste.
  Sintéticos expandidos para **12 pares** com direção temporal balanceada.
- **D6/T3:** a máscara agora usa fronteira de palavra e é case-sensitive
  (bug do verbo "temer" → `[POLITICO]` corrigido); listas completadas
  (Fraga, Ilan, Malan, Nelson Barbosa). O scorer passa a APLICAR a máscara
  (antes só registrava o nível na proveniência — bug crítico).
- **D6/T2:** datas trocadas refletidas p/ dentro de [1999-07-01, hoje−30d].
- **D6/T2-H:** planilha mascarada (15 itens, L2, sem data) gerada junto com o
  piloto — subamostra pré-registrada antes da anotação.
- **D1 (operacional):** planilhas com ordem embaralhada POR anotador e sem a
  coluna de estrato (o rótulo revelava a era). Relatório passa a incluir
  concordância bruta ao lado do κ (paradoxo do kappa registrado: gate é o κ
  global; κ por estrato é diagnóstico).
- **Agregação (spec 4.2 preservada, estimador corrigido):** FE de tipo por
  projeções alternadas (exata em painel desbalanceado — o demeaning de uma
  passada contaminava o gamma com efeito-época) e normalização ponderada pela
  participação global. `ep` oficial clusterizado por DIA. Série crua NÃO
  truncada em [0,1] (censura mataria variância nos extremos); `c_llm_trunc`
  só p/ figuras. Taxas de `sem_sinal` de D2/D3 viram séries auxiliares
  (MNAR observável).
- **D9:** retomada reprocessa falhas; `mode` entra na chave de cache;
  `thinking_budget: 0` no Gemini 2.5.

Limitações residuais monitoráveis (não bloqueiam o piloto): FE por tipo e não
por veículo; wire com título reescrito escapa do cluster; sobrevivência do
corpus nos anos 2000; sobrenome-substantivo em início de frase escapa da
máscara. Detalhes e racionais na auditoria.

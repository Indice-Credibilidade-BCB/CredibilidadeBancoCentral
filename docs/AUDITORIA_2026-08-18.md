# Auditoria da Etapa 2 — código e vieses (2026-08-18)

Escopo: todo o pipeline (`pipeline/`), prompts, config, sintéticos T5, guia e
doc-mestre. Método: releitura módulo a módulo, testes de regressão novos
(`tests/test_auditoria.py`, 9 testes) e smoke de ponta a ponta com corpus
fictício (amostragem → planilhas → agregação). Estado final: **as duas suítes
passam** e o smoke roda limpo.

---

## A. Bugs corrigidos (com severidade)

**A1. [CRÍTICO] `--anonimizacao` não anonimizava.** O scorer gravava o nível
(L1/L2/L3) na proveniência mas enviava o **texto original** ao provedor. O T3
inteiro rodaria inválido — e *pareceria* válido, porque o registro diria
"anonimizado". Corrigido: a máscara é aplicada de fato a título/lead/1º§ antes
da chamada. Teste de regressão cobre.

**A2. [CRÍTICO] Máscara de nomes por regex case-insensitive sem fronteira de
palavra.** "temer" (verbo) virava `[POLITICO]`; "fragata" virava
`[AUTORIDADE_BC]ta`. Num teste T3 isso adiciona ruído sistemático justamente
nos textos com linguagem de risco ("há razões para temer..."), confundindo o
diagnóstico. Corrigido: fronteira de palavra + case-sensitive (aceitando
ALL-CAPS de títulos). Limitação residual documentada: sobrenome idêntico a
substantivo capitalizado em início de frase.

**A3. [GRAVE] "Fraga" não estava na lista de máscara** (só "Armínio Fraga"
por extenso — a imprensa escreve "Fraga" na maioria das menções). Também
faltavam "Ilan", "Armínio" solto, Pedro Malan (era 2002-03, um dos estratos!) e
Nelson Barbosa. Adicionados. Registrada a ambiguidade Meirelles (BC 2003-10,
Fazenda 2016-18): fica em `autoridades_bc` — o rótulo sai impreciso na era
Fazenda, mas a *identidade*, que é o que o T3 esconde, fica mascarada igual.

**A4. [GRAVE] FE de tipo de veículo estimada com demeaning de uma passada.**
Só é exato em painel balanceado. Como *research* entra tarde no corpus (e há
meses só de imprensa), o efeito de tipo saía contaminado pelo efeito-época —
exatamente o viés de composição que a FE deveria remover. Corrigido: projeções
alternadas até convergência (exato em painel desbalanceado) + normalização
**ponderada pela participação global** de cada tipo (a normalização
equal-weight anterior deslocava o nível do índice quando os tipos têm shares
muito diferentes). Teste de regressão: painel onde research só existe na época
de índice alto recupera o gamma verdadeiro com erro < 0,02.

**A5. [GRAVE] Date-swap podia datar item no futuro ou antes do regime de
metas.** ±5 anos cegos: item de 2024 virava 2029; item de 2002 virava 1997.
"Data impossível" é um sinal espúrio que contamina o próprio teste de
vazamento. Corrigido: reflexão para dentro de [1999-07-01, hoje−30d].

**A6. [GRAVE] T5 testado com Welch ignorando o pareamento.** Os sintéticos são
pares de texto **idêntico** com era trocada — o desenho é pareado por
construção. Welch desperdiça poder (com n=12 pares, muito). Corrigido: teste
primário = t pareado por `texto_grupo` com p-valor (Welch mantido como
robustez). Também faltava o p-valor em si (só saía a estatística t, sem gl de
Welch–Satterthwaite); corrigido, `scipy` adicionado aos requirements com
fallback manual.

**A7. [GRAVE] Retomada nunca reprocessava falhas.** Item com `parse_falhou`
entrava no conjunto "já feito" — ficava permanentemente sem nota, silencioso.
Corrigido: só escores válidos pulam; a agregação deduplica por `cache_key`
mantendo o último sucesso.

**A8. [MODERADO] Planilhas de anotação idênticas e com coluna `estrato`.**
(i) Mesma ordem para os dois anotadores correlaciona fadiga/ancoragem
sequencial e infla o κ; (ii) o rótulo "2008-09 crise global" revela a era —
contaminando a anotação principal e destruindo o T2-H (que mascara datas).
Corrigido: ordem embaralhada independentemente por anotador; `estrato` só em
`pilot_items.csv` (gabarito), nunca nas planilhas.

**A9. [MODERADO] T2-H não tinha gerador.** O guia previa reanotação mascarada
mas nenhum código a produzia. Agora `sample_pilot.py` gera `anotacao_T2H.csv`
(15 itens, data omitida, máscara L2) **junto com o piloto** — a subamostra fica
pré-registrada antes de qualquer anotação.

**A10. [MODERADO] Itens de validação do filtro sorteados ao acaso entre os
rejeitados.** Rejeitado aleatório é esporte/polícia — não testa o filtro.
Agora prioriza rejeitados *limítrofes* (mencionam juros/inflação/câmbio/PIB
sem os termos do INCLUIR), que é onde falso-negativo mora.

**A11. [MODERADO] Índice mensal podia sair de [0,1] silenciosamente.** O
ajuste aditivo de FE extrapola em meses ralos (no smoke: −0,09 a 1,16 com 1
item/mês). Decisão registrada: **não truncar** a série dos Blocos 2/3/6
(censura nas bordas atenuaria a variância justamente nos episódios extremos,
que são o sinal; a logística Λ do projeto vive no estado latente do Kalman,
não neste proxy). `c_llm_trunc` adicionada só para leitura/figuras.

**A12. [MODERADO] `relatorio_piloto` quebrava com planilha real.** Células
vazias, "sem_sinal" escrito à mão ou nota "6" derrubavam o cálculo com erro
críptico. Agora: coerção numérica, valores fora de 1–5 viram faltantes com
aviso nominal por linha, flags booleanas aceitam TRUE/sim/x, e sai também a
**concordância bruta** (contexto para o paradoxo do κ — ver B4).

**A13. [MENOR] Parser rejeitava nota `4.0`** (float integral, comum em JSON de
LLM). Aceita int ou float integral; `4.5` e `true` seguem rejeitados.

**A14. [MENOR] Cache não distinguia piloto de produção.** Prompts de sistema
diferentes, mesma chave. `mode` agora entra na variante.

**A15. [MENOR] Gemini 2.5: "thinking" consome `maxOutputTokens`** e resposta
bloqueada por segurança dava KeyError críptico. `thinking_budget: 0`
configurável no provedor, `max_tokens` 200→300, erro explícito com
`finishReason`.

**A16. [MENOR] Regex do filtro sem fronteira em siglas** (`bcb`, `selic`
podiam casar dentro de palavras) e sem "taxa básica", "relatório de inflação",
"boletim focus". Corrigido.

**A17. [MENOR] Docstrings prometiam o que o código não fazia** (wire "±1 dia"
— na prática a janela é o mês; era o comportamento correto, a doc que mentia)
e `schema.validate` aceitava título vazio/NaN, degenerando o hash de
dedup/wire. Ambos corrigidos.

---

## B. Vieses checados que NÃO exigiram mudança de código

**B1. Circularidade índice↔validação.** OK por construção (índice: texto de
terceiros; validação: Focus/mercado). Reconfirmado que nada do Focus entra no
prompt ou no filtro.

**B2. Pessimismo macro ≠ descrédito.** Regra explícita no prompt e no guia;
será medida no piloto pela concordância humano-LLM nos itens de crise.

**B3. Halo entre dimensões.** Regra D10 agora tem função dedicada
(`checar_halo`, alerta se corr LLM > corr humana + 0,20) — antes o limiar
estava só no doc, sujeito a aplicação manual inconsistente.

**B4. Paradoxo do kappa na calmaria.** Distribuição concentrada (tudo "3")
derruba κ mesmo com concordância alta. Mitigado por desenho (estratos de
tensão garantem variância) e agora por relatório (concordância bruta ao lado
do κ). Interpretação registrada no protocolo: o gate é o κ **global**; κ por
estrato é diagnóstico, não gate.

**B5. `sem_sinal` não é aleatório (MNAR).** Some em crise, cresce na calmaria
— ignorá-lo enviesaria D2/D3. Tratamento: taxa mensal de `sem_sinal` vira
série auxiliar observável na agregação (pode inclusive ter conteúdo
informacional próprio: silêncio sobre autonomia é um estado do mundo).

**B6. Rajadas de cobertura (dias de Copom).** Itens do mesmo dia são
correlacionados; `ep = dp/√n` item a item subestimava a incerteza. O `ep`
oficial agora é clusterizado por dia (`ep_iid` mantido como referência).

**B7. Viés de posição/centralidade do LLM** (tendência ao "3"). Sem mudança:
temperatura 0 + âncoras textuais por nível já mitigam; o piloto compara a
distribuição de notas LLM vs. humana por estrato (análise prevista no
protocolo, sem código novo). Se o LLM colapsar ao centro, isso aparece no κ
contra o ouro.

**B8. Ordem das dimensões no prompt** (D1 poderia ancorar D2/D3). O sintoma é
exatamente o que o halo D10 mede. Permutação de ordem fica como robustez
opcional (T7) na Etapa 3 — não bloqueia o piloto.

**B9. Look-ahead humano.** Coberto pelo T2-H, agora com planilha
pré-registrada (A9).

**B10. Fuso do RPD.** Contador local reseta à meia-noite BRT/UTC; o do Google,
no Pacífico. Inofensivo (backoff absorve), documentado no README.

---

## C. Limitações residuais conhecidas (monitorar, não corrigir agora)

**C1. FE por TIPO, não por veículo.** Se o *mix* dentro de imprensa mudar
(Folha↑, Valor↓), sobra viés de composição fina. Spec da 4.2 manda tipo;
extensão natural (FE por veículo) só se o share por veículo/mês — que a Etapa
3 deve reportar — variar muito.

**C2. Wire com título reescrito entre veículos escapa do cluster** (dedup é
exata por título+lead normalizados). Fuzzy matching só se a taxa de wire
observada no corpus real justificar.

**C3. Sobrevivência do corpus digital** (anos 2000 ralos, paywalls). É questão
da Etapa 0; as bandas por volume já refletem o problema, e o estrato 2002-03
do piloto vai medir o quão magro está.

**C4. Máscara de nomes**: início de frase com sobrenome-substantivo ainda
escapa da regra case-sensitive (raro; aceito e documentado).

**C5. Sintéticos T5 = 12 pares** (era 8; meta era 10+, atingida). Direção
temporal balanceada (7 pares boa→ruim, 5 ruim→boa) para separar efeito-época
de efeito-direção. Mais pares = mais poder; expandir se o T5 der limítrofe.

---

## D. Emenda ao pré-registro (feita ANTES de qualquer coleta)

O critério do T5 muda de "Welch significativo a 5%" para "**t pareado por
grupo significativo a 5%**" (Welch vira robustez). Emenda legítima e
registrada agora porque nenhum dado foi coletado; o teste pareado é
estritamente mais fiel ao desenho (pares de texto idêntico) e mais poderoso —
ou seja, a emenda torna o critério **mais duro contra o próprio índice**, não
mais leniente.

Nada mais mudou nos critérios de reprovação de T2/T3/T4.

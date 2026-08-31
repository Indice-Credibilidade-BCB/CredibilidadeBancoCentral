# Teste inicial — corpus real `noticias_2016_2017.xlsx` (2026-08-20)

Primeiro contato do pipeline com dados reais de scraping. Tudo abaixo rodou
de fato no código v1.1 (pós-auditoria); nenhum provedor de API foi chamado —
a pontuação-exemplo da Seção 6 fui **eu (Claude) aplicando o prompt v1.0
manualmente**, como sanity check do prompt, não como piloto.

## 1. Perfil do arquivo

971 linhas, 2 veículos: **Valor (702**, via busca-globo, espécie "Matéria")
e **Poder360 (269**, via wp-api). Cobertura mensal completa de 2016-01 a
2017-12 (mín. 15, máx. 90 itens/mês; picos em mai-jun/2016 = impeachment +
transição Tombini→Goldfajn). Campos: título e 1º parágrafo sempre presentes
(p1 médio de 335 caracteres — dentro da unidade de corpus decidida);
**subtítulo/lead só existe no Poder360** (0% no Valor — a busca do Globo não
retorna). O `build_user_msg` já tolera lead ausente, nada a mudar.

## 2. Mapeamento ao schema

Direto: `data` (ISO c/ timezone) → `data_publicacao`; `subtitulo` → `lead`;
`p1` → `paragrafo_1`; `url` → `fonte_ref`; `item_id` = hash da URL;
`tipo_veiculo = imprensa` para ambos. Guardei `secao` e `especie` como
metadados extras (passam pelo schema; permitem FE mais fina depois — o Valor
tem 16 itens de `/opiniao`, exatamente onde mora sinal denso). `validate`
passou sem ajustes.

## 3. Dedup e wire

971 → **887** (84 duplicatas exatas removidas — títulos repetidos do
scraping). **Zero clusters wire entre veículos** (esperado: Valor e Poder360
não compartilham agência neste recorte); 2 pares (mês, cluster) com repetição
intra-veículo, colapsados na agregação como previsto.

## 4. Filtro de relevância (regex, estágio 1)

**90,8% aprovado** (805 itens) — mas com composição bem diferente por
veículo: Valor 99,8% (a busca já era temática) vs. **Poder360 69,9%** (o
wp-api trouxe Panama Papers, offshores etc., corretamente rejeitados).
Todos os 24 meses ficam com ≥14 itens relevantes.

Procedurais: só 3 flags. Dois corretos ("BC divulga calendário de reuniões",
item alheio com "reúne-se nesta"); **um limítrofe real**: *"Com expectativa
de redução nos juros, Copom faz reunião nesta semana"* — o corpo é agenda,
mas o título carrega expectativa. Perda de recall marginal aceita por
desenho (corte grosso); é exatamente o tipo de item que o conjunto de
validação de borda do piloto vai medir. Corrigi de passagem o warning de
grupo capturante no regex.

## 5. Anonimização (T3) em texto real

O período é o teste de estresse ideal: **Ilan/Goldfajn aparece em 314 dos
805 itens relevantes (39%)**, Tombini em 67, Meirelles em 36, Temer em 49.
Máscara L3 verificada em itens carregados (posse do Ilan): autoridades e
políticos mascarados corretamente, verbo "temer"/"fragata" intocados (bug
A2 da auditoria segue morto em dados reais). Limitação residual visível:
"presidente interino" permanece — cargo é pista contextual; mascarar cargos
destruiria o texto e não está no desenho do T3.

## 6. Pontuação-exemplo (Claude aplicando o prompt v1.0; N=12)

Amostra determinística (seed 42), 2 itens em cada uma de 6 janelas de
evento: pré-impeachment, transição Ilan, início dos cortes, choque JBS,
consolidação e desinflação. As 12 respostas em JSON passaram pelo
`parse_json_resposta` (contrato de ponta a ponta ok). Notas e justificativas
em `piloto_claude_notas.csv`. Destaques:

- **jan/2016** (opinião do Valor sobre a ata): D1=2, D2=1 — "comunicação
  errática e desnorteante" é o descrédito clássico da era; as âncoras
  discriminaram bem.
- **dez/2016** (Poder360, "Sob pressão, BC sinaliza cortes maiores"): D1=3,
  D3=2 — "embora insista no discurso" + "sob pressão" ativam a dimensão de
  autonomia sem tocar D1. As diagnósticas trabalham.
- **mai/2017** (véspera do Copom pós-JBS): D2=4, D3=4 — mercado espera BC
  manter o ritmo tecnicamente apesar da crise política.
- **18/mai/2017** (reunião de emergência Meirelles-Ilan, dia do estouro da
  JBS): D1=3 — o texto isolado não conecta a crise. Anotei sabendo o que
  aquele dia foi; segurar a restrição temporal exigiu esforço consciente.
  **O T2-H não é paranoia** — o look-ahead humano é real e este item devia
  entrar na reanotação mascarada.

## 7. Achado central: densidade de sinal

**Só 3 de 12 itens têm sinal em D1 (≠3); 9 são cobertura factual neutra.**
Média reescalada da amostra: 0,52 — colada no centro. Implicações:

1. **Confirma o gate LLM de relevância (estágio 2) como necessário, não
   opcional.** O regex aprova "Volpon vira economista-chefe do UBS" e a
   agenda regulatória do Ilan na FGV — relevantes ao universo BCB, sem sinal
   de credibilidade. Num scraping bruto, a maioria dos itens é assim.
2. **Muitos 3s comprimem o índice mensal em torno de 0,5** e diluem os
   episódios — exatamente o que não queremos. Para a Etapa 3, registrar
   como robustez pré-especificada: (i) série principal como está (o neutro
   É percepção neutra — decisão 4.2 mantida); (ii) variante "signal-only"
   (média só de |d1−3|>0) + **taxa mensal de neutros** como série auxiliar
   — a proporção de cobertura sem juízo pode, ela própria, carregar
   informação sobre o regime.
3. Para o **piloto de 50**, isso reforça a estratificação por tensão (já
   decidida): amostra puramente aleatória deste corpus daria κ sobre uma
   base dominada por 3s (paradoxo do kappa monitorado pela concordância
   bruta, adicionada na auditoria).

## 8. Cobertura vs. estratos do piloto

Este arquivo cobre **2 dos 6 estratos**: "2013-16 fiscal/impeachment"
(parcial: só 2016) e "calmaria 2017-19" (parcial: só 2017). Faltam
2002-03, 2008-09, 2020-21 e 2022-24 — o scraping precisa ser estendido
antes de rodar `sample_pilot.py` para valer. Nota: 2017 no config está
rotulado "calmaria", mas mai-jun/2017 (JBS) é tensão política aguda com BC
em ciclo de corte — na revisão dos estratos com o corpus completo, vale
excluir mai-jun/2017 da janela de calmaria ou aceitar a mistura documentada.

## 9. Estado dos arquivos

- `data/corpus_teste_2016_2017.parquet` — corpus mapeado, deduplicado, com
  flags de relevância e metadados extras (secao/especie).
- `data/piloto_claude_notas.csv` — as 12 notas com justificativas.
- Pipeline inalterado exceto o regex não-capturante em `relevance.py`.

**Veredicto: o pipeline engole dados reais de scraping sem fricção** —
mapeamento direto, dedup agindo, filtro com taxa sensata e discriminando
por veículo, máscara T3 exercitada num período denso de nomes, prompt e
parser fechando o contrato. Os riscos que o teste revelou são de *desenho
de corpus* (densidade de sinal, cobertura de estratos), não de código.

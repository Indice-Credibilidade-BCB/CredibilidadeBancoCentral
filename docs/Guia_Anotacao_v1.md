# Guia de Anotação — Piloto do Índice de Credibilidade do BCB (v1.0)

> Para os dois anotadores humanos da Etapa 2. A anotação é **independente e
> cega**: não discuta itens nem compare notas antes de entregar sua planilha.
> O mesmo guia é a base do prompt do LLM — humano e modelo seguem a mesma régua.

## 1. O que você está medindo

**Percepção, não fato.** A pergunta nunca é "a meta será cumprida?" e sim
"**este texto** trata a meta como provável de ser cumprida?". Você avalia o que
o veículo/analista transmite ao leitor na data de publicação.

**Restrição temporal (vale para você também).** Você conhece o desfecho de
2015, de 2021, etc. — o modelo de linguagem também. A régua é a mesma para os
dois: **julgue apenas o que o texto afirma ou implica**, como se você estivesse
na data de publicação, sem usar o que aconteceu depois. Se perceber que sua
nota está sendo puxada pelo desfecho conhecido ("e de fato estourou a meta"),
recue e releia só o texto.

## 2. As três dimensões (avalie cada uma de forma independente)

A nota de uma dimensão **não** deve contaminar a outra. Um texto pode elogiar a
condução (D2 alta) e ainda assim tratar a meta como perdida (D1 baixa) — isso é
comum e legítimo.

### D1 — Probabilidade percebida de cumprimento da meta (principal)
| Nota | Âncora | Exemplo de tom |
|---|---|---|
| 1 | Descumprimento certo/consumado | "meta virou ficção", "estouro é dado" |
| 2 | Cumprimento improvável | "analistas veem meta fora de alcance" |
| 3 | Neutro / incerto / sem sinal claro | relato factual, projeções divididas |
| 4 | Cumprimento provável | "meta deve ser cumprida", convergência esperada |
| 5 | Cumprimento certo / sob controle | "inflação ancorada", "meta garantida" |

D1 é **sempre** pontuada (o corpus já foi filtrado por relevância). Sem sinal
claro sobre a meta = 3.

### D2 — Confiança na condução da política monetária (diagnóstica)
1 = crítica direta à condução ("BC dormiu no ponto", "erro de política") ...
3 = neutro ... 5 = elogio à condução ("resposta correta e tempestiva").
Se o texto **não aborda** a condução, marque `d2_sem_sinal = 1` e deixe `d2` vazio.

### D3 — Autonomia percebida (diagnóstica)
1 = subordinação clara ("decisão para agradar o Planalto") ... 3 = neutro ...
5 = autonomia plena e inquestionada. Se o texto não toca em autonomia/pressão
política, `d3_sem_sinal = 1` e `d3` vazio.

## 3. Regras de decisão (casos que derrubam o kappa)

1. **Pessimismo macro ≠ descrédito.** "Inflação deve fechar o ano em 9%" sem
   atribuição ao BCB é pessimismo macroeconômico: D1 pode cair (o texto trata a
   meta como improvável), mas **D2 fica em 3/sem sinal** se não há juízo sobre a
   condução. Só rebaixe D2 se o texto ligar o resultado à incapacidade/inação
   do BC.
2. **Fala do próprio BCB citada não é percepção de terceiros.** Pese como o
   veículo **enquadra** a fala: "BC garante convergência" (neutro-positivo)
   difere de "BC insiste que meta será cumprida, apesar de..." (cético).
3. **Ironia e escolha de fontes contam.** Um texto que só ouve céticos sinaliza
   ceticismo do veículo.
4. **Manchete vs. corpo.** Se título e parágrafo divergem, pese o conjunto;
   o título tem peso editorial, mas não anula o corpo.
5. **Não use conhecimento sobre a pessoa.** "Fulano é bom/ruim presidente do
   BC" é prior seu; conta apenas o que o texto diz.

## 4. Campos da planilha

`d1` (1–5, obrigatório) · `d2`, `d3` (1–5 ou vazio) · `d2_sem_sinal`,
`d3_sem_sinal` (1 se vazio por falta de sinal) · `contexto_insuficiente`
(1 se título+lead+1º§ não bastaram para decidir com segurança — **ainda assim
dê sua melhor nota**; a flag serve para o gate de revisão da unidade, gatilho
&gt; 25%) · `obs` (livre, opcional).

## 5. Procedimento e prazos

1. Anote os 50 itens sozinho, em até duas sessões (~2–3 min/item; ~2h no total).
2. Entregue a planilha sem discutir com o outro anotador.
3. Calculamos κ ponderado quadrático (gate: ≥ 0,6 em D1) e α de Krippendorff.
4. **Adjudicação:** reunião única; toda discordância é discutida e vira um
   rótulo-ouro de consenso (usado para avaliar os LLMs). O κ é sempre o da
   rodada cega — a adjudicação não o altera.
5. Reanotação anti-look-ahead (T2-H): ~15 itens voltam semanas depois com data
   e nomes mascarados; serve para medir a sua própria consistência.


---

**Adendo (auditoria 2026-08-18).** As duas planilhas têm ordens diferentes de
propósito — não compare posições nem "sincronize" a sequência com o outro
anotador; siga a sua de cima a baixo. A planilha `anotacao_T2H.csv` (15 itens
sem data e com nomes mascarados) deve ser preenchida DEPOIS da anotação
principal, sem consultar as notas que você deu antes.

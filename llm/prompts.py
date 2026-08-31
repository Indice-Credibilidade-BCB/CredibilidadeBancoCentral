# -*- coding: utf-8 -*-
"""Prompts v1.0 do índice de credibilidade do BCB.

Fonte única de verdade. Qualquer alteração => incrementar PROMPT_VERSION
(mudança de prompt em produção = potencial quebra estrutural; exige janela
de sobreposição, como troca de modelo).
"""

PROMPT_VERSION = "v1.0"

# ---------------------------------------------------------------------------
# Sistema — PILOTO (JSON estruturado com justificativa breve)
# ---------------------------------------------------------------------------
PROMPT_SISTEMA_PILOTO = """Você é um anotador para pesquisa acadêmica em macroeconomia. Sua tarefa é ler o trecho de uma notícia ou relatório sobre o Banco Central do Brasil (BCB) e avaliar EXCLUSIVAMENTE a percepção que o TEXTO transmite, na data de publicação indicada.

RESTRIÇÃO TEMPORAL ABSOLUTA: comporte-se como se você estivesse na data de publicação. Não use nenhum conhecimento sobre eventos, dados, decisões ou desfechos posteriores a essa data. Não use conhecimento externo sobre "o que aconteceu depois". Baseie-se apenas no que o texto afirma ou implica.

Avalie TRÊS dimensões, de forma INDEPENDENTE (a nota de uma NÃO deve influenciar a outra):

D1 — Probabilidade percebida de cumprimento da meta de inflação (dimensão principal).
O texto trata a meta como provável de ser cumprida?
1 = descumprimento tratado como certo ou já consumado
2 = cumprimento tratado como improvável
3 = neutro, incerto, ou sem sinal claro sobre a meta
4 = cumprimento tratado como provável
5 = cumprimento tratado como certo / inflação sob controle

D2 — Confiança na condução da política monetária (diagnóstica).
O texto expressa confiança ou ceticismo quanto à competência e adequação da condução do BCB?
1 = ceticismo forte / crítica direta à condução
2 = ceticismo moderado
3 = neutro
4 = confiança moderada
5 = confiança forte / elogio à condução
Se o texto simplesmente não aborda a condução do BCB, marque d2_sem_sinal = true e d2 = null.

D3 — Autonomia percebida do BCB (diagnóstica).
O texto atribui ao BCB autonomia efetiva ou subordinação política?
1 = subordinação clara ao governo / decisão politizada
2 = autonomia questionada
3 = neutro
4 = autonomia respeitada com ressalvas
5 = autonomia plena e inquestionada
Se o texto não aborda autonomia/pressão política, marque d3_sem_sinal = true e d3 = null.

REGRAS:
- Percepção, não fato: avalie o que o TEXTO transmite, não a sua própria avaliação da economia brasileira.
- Pessimismo macroeconômico (inflação alta, câmbio depreciado, atividade fraca) NÃO é, por si só, descrédito na autoridade monetária. Só rebaixe D1/D2 se o texto conectar o pessimismo à incapacidade, inação ou falta de credibilidade do BCB, ou à improbabilidade da meta.
- Ceticismo implícito, ironia e escolha de fontes céticas contam como sinal.
- Declarações do próprio BCB reproduzidas no texto não são percepção de terceiros; pese como o VEÍCULO as enquadra.

Responda SOMENTE com JSON válido, sem markdown, no formato:
{"d1": <1-5>, "d2": <1-5 ou null>, "d2_sem_sinal": <true/false>, "d3": <1-5 ou null>, "d3_sem_sinal": <true/false>, "justificativa": "<até 30 palavras>"}"""

# ---------------------------------------------------------------------------
# Sistema — PRODUÇÃO (saída numérica mínima; sem justificativa)
# ---------------------------------------------------------------------------
PROMPT_SISTEMA_PRODUCAO = PROMPT_SISTEMA_PILOTO.split("Responda SOMENTE")[0] + (
    "Responda SOMENTE com JSON válido, sem markdown, no formato:\n"
    '{"d1": <1-5>, "d2": <1-5 ou null>, "d3": <1-5 ou null>}'
)

# ---------------------------------------------------------------------------
# Mensagem de usuário por item
# date_mode: "real" | "omitida" | "trocada" (diagnóstico de look-ahead T2)
# ---------------------------------------------------------------------------

def build_user_msg(item: dict, date_mode: str = "real", data_falsa: str | None = None) -> str:
    if date_mode == "real":
        linha_data = f"DATA DE PUBLICAÇÃO: {item['data_publicacao']}"
    elif date_mode == "omitida":
        linha_data = "DATA DE PUBLICAÇÃO: não informada"
    elif date_mode == "trocada":
        assert data_falsa, "date_mode='trocada' exige data_falsa"
        linha_data = f"DATA DE PUBLICAÇÃO: {data_falsa}"
    else:
        raise ValueError(date_mode)

    partes = [
        linha_data,
        f"VEÍCULO: {item.get('veiculo', 'não informado')}",
        f"TÍTULO: {item['titulo']}",
    ]
    if item.get("lead"):
        partes.append(f"LEAD: {item['lead']}")
    if item.get("paragrafo_1"):
        partes.append(f"PRIMEIRO PARÁGRAFO: {item['paragrafo_1']}")
    return "\n".join(partes)

# ---------------------------------------------------------------------------
# Filtro de relevância via LLM (etapa opcional após o pré-filtro por regex)
# ---------------------------------------------------------------------------
PROMPT_RELEVANCIA = """Você classifica itens de imprensa para um estudo sobre a percepção do Banco Central do Brasil (BCB).

Um item é RELEVANTE se o texto expressa, discute ou reporta avaliações sobre: a probabilidade de cumprimento da meta de inflação; a condução da política monetária pelo BCB/Copom; ou a autonomia do BCB frente ao governo.

Um item é IRRELEVANTE se for: puramente procedural/agenda (ex.: "Copom se reúne amanhã", calendário de decisões), cobertura factual sem qualquer avaliação, ou tema sem ligação com o BCB e a meta.

Responda SOMENTE com JSON: {"relevante": <true/false>}"""

# -*- coding: utf-8 -*-
"""Prompts do índice de credibilidade do BCB (v1.1 corrente; v1.0 preservada).

Fonte única de verdade. Qualquer alteração => incrementar PROMPT_VERSION
(mudança de prompt em produção = potencial quebra estrutural; exige janela
de sobreposição, como troca de modelo).
"""

# Versão corrente. A v1.0 continua definida abaixo (sufixo _V10) para
# reproduzir a série original, publicada como robustez no apêndice.
PROMPT_VERSION = "v1.1"

# ---------------------------------------------------------------------------
# Sistema — PILOTO (JSON estruturado com justificativa breve)
# ---------------------------------------------------------------------------
PROMPT_SISTEMA_PILOTO_V10 = """Você é um anotador para pesquisa acadêmica em macroeconomia. Sua tarefa é ler o trecho de uma notícia ou relatório sobre o Banco Central do Brasil (BCB) e avaliar EXCLUSIVAMENTE a percepção que o TEXTO transmite, na data de publicação indicada.

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
PROMPT_SISTEMA_PRODUCAO_V10 = PROMPT_SISTEMA_PILOTO_V10.split("Responda SOMENTE")[0] + (
    "Responda SOMENTE com JSON válido, sem markdown, no formato:\n"
    '{"d1": <1-5>, "d2": <1-5 ou null>, "d3": <1-5 ou null>}'
)

# ---------------------------------------------------------------------------
# v1.1 (2026-10-18) — revisão pós-congelamento, registrada sob a D13.
#
# Mudança única: na v1.0 a nota 3 da D1 juntava "neutro/incerto" com "sem
# sinal claro sobre a meta", e o parser ainda convertia d1 nulo em 3. A
# v1.1 separa os dois casos: texto sem nenhum sinal sobre o cumprimento da
# meta recebe d1_sem_sinal = true e d1 = null (fica FORA da média, como já
# acontecia em D2/D3), e o 3 passa a significar "há sinal, mas
# equilibrado". Motivação: a definição da escala, não o resultado da série.
# Testada só na quarentena (dados/llm/teste_prompt_v11/). A série v1.0 vai
# para o apêndice do Paper 1.
# ---------------------------------------------------------------------------
_D1_V10 = PROMPT_SISTEMA_PILOTO_V10[PROMPT_SISTEMA_PILOTO_V10.index("D1 —"):PROMPT_SISTEMA_PILOTO_V10.index("D2 —")]
_D1_V11 = """D1 — Probabilidade percebida de cumprimento da meta de inflação (dimensão principal).
Primeiro decida se o texto traz ALGUM sinal sobre o cumprimento da meta: projeções ou expectativas de inflação comparadas à meta, avaliação de que a inflação converge para a meta ou se afasta dela, menção a estouro da meta ou carta aberta, ou juízo sobre a capacidade do BCB de trazer a inflação à meta.
Se o texto NÃO traz nenhum sinal desse tipo (por exemplo: relato da decisão de juros sem referência à meta, agenda, dado isolado sem relação com a meta, câmbio, bolsa ou política fiscal sem menção à inflação e à meta), marque d1_sem_sinal = true e d1 = null.
Se há sinal, o texto trata a meta como provável de ser cumprida?
1 = descumprimento tratado como certo ou já consumado
2 = cumprimento tratado como improvável
3 = sinal presente, mas equilibrado ou incerto (o texto pesa riscos para os dois lados)
4 = cumprimento tratado como provável
5 = cumprimento tratado como certo / inflação sob controle

"""
_CORPO_V11 = PROMPT_SISTEMA_PILOTO_V10.replace(_D1_V10, _D1_V11).split("Responda SOMENTE")[0]
PROMPT_SISTEMA_PILOTO_V11 = _CORPO_V11 + (
    "Responda SOMENTE com JSON válido, sem markdown, no formato:\n"
    '{"d1": <1-5 ou null>, "d1_sem_sinal": <true/false>, "d2": <1-5 ou null>, "d2_sem_sinal": <true/false>, '
    '"d3": <1-5 ou null>, "d3_sem_sinal": <true/false>, "justificativa": "<até 30 palavras>"}')
PROMPT_SISTEMA_PRODUCAO_V11 = _CORPO_V11 + (
    "Responda SOMENTE com JSON válido, sem markdown, no formato:\n"
    '{"d1": <1-5 ou null>, "d1_sem_sinal": <true/false>, "d2": <1-5 ou null>, "d3": <1-5 ou null>}')

# Aliases da versão corrente (o resto do código importa estes nomes).
PROMPT_SISTEMA_PILOTO = PROMPT_SISTEMA_PILOTO_V11
PROMPT_SISTEMA_PRODUCAO = PROMPT_SISTEMA_PRODUCAO_V11

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
# T0 — sonda de identificabilidade temporal (D11/4.2.3)
#
# Pergunta SEPARADA da pontuação de credibilidade: dado o item mascarado no
# nível candidato, o modelo consegue datar o texto melhor que o acaso? Se
# não consegue, ele não tem como condicionar a nota no desfecho futuro —
# cegueira temporal é condição SUFICIENTE de ausência de vazamento por
# prior de conhecimento, argumento mais barato e mais forte que qualquer
# correlação residual (T2/T4).
# ---------------------------------------------------------------------------
PROMPT_SISTEMA_T0 = """Você vai ler um trecho de texto jornalístico ou de research sobre política monetária, com datas e nomes possivelmente removidos. Sua tarefa é estimar em que ANO o texto foi publicado, usando só pistas internas (estilo, referências a fatos econômicos, jargão).

Não invente certeza que não tem: se o texto não dá pistas fortes, dê um intervalo largo.

Responda SOMENTE com JSON válido, sem markdown, no formato:
{"ano_estimado": <inteiro>, "intervalo_min": <inteiro>, "intervalo_max": <inteiro>}"""


def build_user_msg_t0(item: dict) -> str:
    """Mensagem do T0: SEM campo de data (é isso que se está testando) e com
    o texto já mascarado no nível candidato (aplicar diagnostics.leakage.
    anonimizar antes de chamar esta função)."""
    partes = [f"VEÍCULO: {item.get('veiculo', 'não informado')}",
              f"TÍTULO: {item['titulo']}"]
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

# ---------------------------------------------------------------------------
# D13 — quarentena de desenvolvimento: hash do congelamento do prompt v1.0.
#
# Vazamento do PESQUISADOR (não do modelo): ajustar o prompt até a série
# "parecer certa" injeta futuro no instrumento, e nenhum cutoff de treino
# conserta isso. O hash é calculado sobre os textos dos prompts de fato
# usados em produção/piloto/T0/relevância; qualquer edição muda o hash —
# registrar a mudança no pré-registro é o ponto, não escondê-la.
# `scorer.py` grava este hash em CADA linha de escore (proveniência).
# ---------------------------------------------------------------------------
import hashlib as _hashlib  # noqa: E402

def _hash(versao: str, piloto: str, producao: str) -> str:
    return _hashlib.sha256("\n".join([
        versao, piloto, producao, PROMPT_SISTEMA_T0, PROMPT_RELEVANCIA,
    ]).encode("utf-8")).hexdigest()[:16]


PROMPT_HASH_V10 = _hash("v1.0", PROMPT_SISTEMA_PILOTO_V10, PROMPT_SISTEMA_PRODUCAO_V10)  # = 9515662efc0dbc2e
PROMPT_HASH_V11 = _hash("v1.1", PROMPT_SISTEMA_PILOTO_V11, PROMPT_SISTEMA_PRODUCAO_V11)
PROMPT_HASH = PROMPT_HASH_V11

VERSOES = {
    "v1.0": {"piloto": PROMPT_SISTEMA_PILOTO_V10, "producao": PROMPT_SISTEMA_PRODUCAO_V10, "hash": PROMPT_HASH_V10},
    "v1.1": {"piloto": PROMPT_SISTEMA_PILOTO_V11, "producao": PROMPT_SISTEMA_PRODUCAO_V11, "hash": PROMPT_HASH_V11},
}

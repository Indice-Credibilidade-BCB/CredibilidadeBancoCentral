# %% G1 — busca da Globo com plano explícito de consultas

"""O G1 usa a mesma busca da Valor e do O Globo (motor globo), mas a busca do
tenant g1 NÃO ordena por data: a posição 9.900 de "Copom" pode ser de 2011 ou
de 2025. O planejador (planejamento.expandir) decide subdividir pela data
nessa posição, então para o G1 ele concluiria "alcança a janela" sem garantia
nenhuma. Aqui o plano é fixo e exaustivo: cada termo sozinho, cada termo com
cada divisor de primeiro nível e cada termo com cada divisor de segundo nível.
Cada consulta rende até TETO_FROM resultados; dedup, filtro temático e o
registro de consultas concluídas são os do pipeline.

robots.txt (verificado em 2026-10-20): g1.globo.com só fecha /busca/ (a página
HTML); busca.globo.com não tem robots.txt; nenhuma regra para agentes de IA.

Uso (de dentro de coleta/):  python g1.py
"""

import os

import configuracao as cfg
from armazenamento import carregarFeitas, gravar, marcarFeita
from utilitarios import log
from varredura import varrerGlobo

VEICULO, TENANT = "G1", "g1"


def plano(termos=None) -> list[str]:
    termos = termos or cfg.TERMOS
    consultas = list(termos)
    for divisores in (cfg.DIVISORES, cfg.DIVISORES_2):
        consultas += [f"{t} {d}" for t in termos for d in divisores if d.lower() not in t.lower()]
    return list(dict.fromkeys(consultas))


def coletar(ini=None, fim=None) -> list[dict]:
    ini, fim = ini or cfg.INICIO, fim or cfg.FIM
    feitas = carregarFeitas()
    resumo = []
    consultas = plano()
    log(f"{VEICULO}: {len(consultas)} consultas no plano")
    for i, q in enumerate(consultas, 1):
        chave = f"{VEICULO}||{q}||{ini:%Y%m%d}-{fim:%Y%m%d}"
        if chave in feitas:
            continue
        registros, info = varrerGlobo(q, VEICULO, TENANT, ini, fim, ordenada=False)
        gravar(VEICULO, registros)
        resumo.append({"consulta": q, "n": len(registros), "truncou": info["truncou"]})
        if not info["ok"]:
            log(f"  [{i}/{len(consultas)}] {q!r}: falha transitória — NÃO marcada; refeita na próxima rodada")
            continue
        marcarFeita(chave)
        feitas.add(chave)
        log(f"  [{i}/{len(consultas)}] {q!r}: {len(registros)} notícias"
            + ("  [teto de 10 mil]" if info["truncou"] else ""))
    return resumo


if __name__ == "__main__":
    cfg.definirColaborador(cfg.COLABORADOR)  # COLETA_USER ou usuário do sistema
    coletar()

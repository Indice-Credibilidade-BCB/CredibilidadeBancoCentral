# %% Agência Brasil — coleta pelas listagens das seções

"""Agência Brasil (EBC), pelas páginas de listagem da seção Economia.

A busca do site fica em /search/, proibida no robots.txt; o sitemap só cobre
2014–2020. As listagens (/economia?page=N, da mais nova para a mais antiga)
são permitidas e chegam a 2011. O robots.txt pede 10 s entre requisições.

1. lê a listagem página a página até passar de INICIO;
2. pré-filtro pelo endereço (mês dentro da janela e palavra no slug);
3. baixa a matéria: título, data (article:published_time) e parágrafos do
   corpo, sem a legenda da foto;
4. mesmo filtro temático dos outros veículos (casaTermo) e o mesmo registro
   de extracao.montar, gravado em dados/bruto/.

Notícia nova no topo empurra as antigas para páginas seguintes: lendo em
ordem crescente, uma matéria pode aparecer duas vezes, mas não some.
Retomável: páginas já lidas e URLs já baixadas são puladas.
Uso (de dentro de coleta/):  python agenciabrasil.py
"""

import json
import os
import re
import time
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup

import configuracao as cfg
from armazenamento import caminhoBruto
from extracao import montar
from linea import slug_relevante
from transporte import sessaoAtual
from utilitarios import casaTermo, log

VEICULO = "Agência Brasil"
BASE = "https://agenciabrasil.ebc.com.br"
SECOES = ("economia",)  # Política fora por prazo (2026-10-21): cerca de um dia a mais de listagem
PAUSA = 10.0  # Crawl-delay do robots.txt
RX_LINK = re.compile(r'href="(?:https?://agenciabrasil\.ebc\.com\.br)?(/([a-z-]+)/noticia/(\d{4})-(\d{2})/[a-z0-9-]+)"')


def _get(url, params=None):
    r = sessaoAtual().get(url, params=params, timeout=cfg.TIMEOUT)
    time.sleep(PAUSA)
    r.raise_for_status()
    return r.text


def links_da_listagem(pagina_html: str, secao: str) -> list[tuple[str, datetime]]:
    out = []
    for caminho, sec, ano, mes in RX_LINK.findall(pagina_html):
        if sec == secao:
            out.append((BASE + caminho, datetime(int(ano), int(mes), 1)))
    return list(dict.fromkeys(out))


def extrair(url: str, pagina: str) -> dict | None:
    s = BeautifulSoup(pagina, "lxml")
    h1 = s.select_one("h1.titulo-materia")
    corpo = s.select_one(".conteudo-noticia")
    data = s.find("meta", attrs={"property": "article:published_time"})
    if not (h1 and corpo and data):
        return None
    paragrafos = [p.get_text(" ", strip=True) for p in corpo.find_all("p") if not p.find_parent("figure")]
    paragrafos = [p for p in paragrafos if len(p) >= 60]
    texto = " ".join(paragrafos)
    return montar(VEICULO, url, data.get("content"), h1.get_text(" ", strip=True), None,
                  paragrafos, url.split("/")[3], "Matéria", len(texto), "ebc-listagem", "listagem-slug")


def coletar() -> dict:
    destino = caminhoBruto(VEICULO)
    feitas_pg = os.path.join(cfg.PASTA_BRUTO, "_agenciabrasil_paginas_lidas.txt")
    vistos = set()
    if os.path.exists(destino):
        with open(destino, encoding="utf-8") as f:
            vistos = {json.loads(l)["url"] for l in f if l.strip()}
    if os.path.exists(destino + ".descartadas"):
        vistos |= set(open(destino + ".descartadas", encoding="utf-8").read().split())
    lidas = set(open(feitas_pg, encoding="utf-8").read().split()) if os.path.exists(feitas_pg) else set()
    cont = {"paginas": 0, "links": 0, "pre_filtro": 0, "baixadas": 0, "temáticas": 0, "erros": 0}
    log(f"{VEICULO}: seções {SECOES}; {len(lidas)} páginas de listagem já lidas")
    for secao in SECOES:
        pagina, vazias = 0, 0
        while True:
            chave = f"{secao}:{pagina}"
            if chave in lidas:
                pagina += 1
                continue
            try:
                links = links_da_listagem(_get(f"{BASE}/{secao}", {"page": pagina}), secao)
            except Exception as e:  # noqa: BLE001
                cont["erros"] += 1
                log(f"  listagem {chave} falhou: {type(e).__name__}")
                vazias += 1
                if vazias >= 3:
                    break
                pagina += 1
                continue
            if not links:
                break                        # passou da última página
            vazias = 0
            cont["paginas"] += 1
            cont["links"] += len(links)
            erros_pg = 0
            for url, mes in links:
                if url in vistos or not (cfg.INICIO.replace(day=1) <= mes < cfg.FIM) or not slug_relevante(url):
                    continue
                cont["pre_filtro"] += 1
                try:
                    reg = extrair(url, _get(url))
                except Exception as e:  # noqa: BLE001
                    cont["erros"] += 1
                    erros_pg += 1
                    log(f"  {url} falhou: {type(e).__name__}")
                    continue
                if reg is None:
                    erros_pg += 1            # formato inesperado: tenta de novo noutra rodada
                    continue
                vistos.add(url)
                cont["baixadas"] += 1
                publicada = pd.to_datetime(reg.get("data"), utc=True, errors="coerce")
                dentro = pd.notna(publicada) and \
                    cfg.INICIO <= publicada.tz_convert("America/Sao_Paulo").tz_localize(None) < cfg.FIM
                if dentro and casaTermo(reg["titulo"], reg["subtitulo"], reg["p1"]):
                    reg["colaborador"] = cfg.COLABORADOR
                    with open(destino, "a", encoding="utf-8") as f:
                        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
                    cont["temáticas"] += 1
                else:
                    with open(destino + ".descartadas", "a", encoding="utf-8") as f:
                        f.write(url + "\n")
            if erros_pg == 0:
                with open(feitas_pg, "a", encoding="utf-8") as f:
                    f.write(chave + "\n")
            if pagina % 50 == 0:
                log(f"  {secao} pág. {pagina} ({min(m for _, m in links):%Y-%m}) | {cont}")
            if max(m for _, m in links) < cfg.INICIO.replace(day=1):
                break                        # a página inteira é anterior à janela
            pagina += 1
    log(f"{VEICULO} concluído: {cont}")
    return cont


if __name__ == "__main__":
    cfg.definirColaborador(cfg.COLABORADOR)  # COLETA_USER ou usuário do sistema
    coletar()

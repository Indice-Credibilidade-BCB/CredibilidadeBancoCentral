# %% Bloomberg Línea — coleta pelos sitemaps diários (Arc XP)

"""Bloomberg Línea Brasil (desde jul/2021), pelos sitemaps que o próprio site
publica no robots.txt. A busca do site (/queryly-advanced-search, /pf/api)
é proibida no robots.txt; páginas de matéria e sitemaps são permitidos.

1. índice completo de sitemaps -> um sitemap por dia;
2. pré-filtro pelo endereço (o slug traz as palavras do título);
3. baixa a matéria e lê o JSON que a página embute (Fusion.globalContent):
   título, linha fina, parágrafos, data de publicação e seção;
4. mesmo filtro temático local dos outros veículos (casaTermo) e o mesmo
   registro de extracao.montar, gravado em dados/bruto/.

Retomável: os sitemaps já lidos e as URLs já baixadas são pulados.
Uso (de dentro de coleta/):  python linea.py
"""

import html
import json
import os
import re
import time
from datetime import datetime

import pandas as pd

import configuracao as cfg
from armazenamento import caminhoBruto
from extracao import montar
from transporte import sessaoAtual
from utilitarios import casaTermo, log, norm

VEICULO = "Bloomberg Línea"
INDICE = "https://www.bloomberglinea.com.br/arc/outboundfeeds/full-sitemap-index/?outputType=xml"
PAUSA = 2.0
# pré-filtro no slug: mais largo que o filtro temático, para não perder matéria
# cujo título não traz o termo exato (o filtro de verdade vem depois, no texto)
PALAVRAS_SLUG = ("copom", "selic", "banco-central", "politica-monetaria", "meta-de-inflacao",
                 "relatorio-de-inflacao", "bacen", "campos-neto", "galipolo", "inflacao",
                 "ipca", "juros")
TOKENS_SLUG = {"bc"}
RX_PREFIXO = re.compile(r"^\s*(Bloomberg(\s+L[íi]nea)?)\s*[—–-]+\s*", re.I)


def _get(url):
    r = sessaoAtual().get(url, timeout=cfg.TIMEOUT, headers={"accept": "*/*", "content-type": None})
    time.sleep(PAUSA)
    r.raise_for_status()
    return r.text


def sitemaps_diarios() -> list[tuple[str, str]]:
    xml = _get(INDICE)
    locs = re.findall(r"<loc>([^<]+)</loc>", xml)
    out = []
    for u in locs:
        m = re.search(r"/(\d{4}-\d{2}-\d{2})/", u)
        if m and cfg.INICIO <= datetime.fromisoformat(m.group(1)) < cfg.FIM:
            out.append((m.group(1), html.unescape(u)))
    return sorted(out)


def slug_relevante(url: str) -> bool:
    s = norm(url.rstrip("/").rsplit("/", 1)[-1])
    return any(p in s for p in PALAVRAS_SLUG) or bool(TOKENS_SLUG & set(s.split("-")))


def _texto(h: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h or ""))).strip()


def extrair(url: str, pagina: str) -> dict | None:
    m = re.search(r"Fusion\.globalContent\s*=\s*(\{.*?\});\s*Fusion\.", pagina, re.S)
    if not m:
        return None
    g = json.loads(m.group(1))
    paragrafos = [_texto(c.get("content")) for c in g.get("content_elements", []) if c.get("type") == "text"]
    paragrafos = [p for p in paragrafos if len(p) >= 60]
    if paragrafos:
        paragrafos[0] = RX_PREFIXO.sub("", paragrafos[0])
    secao = (g.get("taxonomy", {}).get("primary_section") or {}).get("name")
    corpo = " ".join(paragrafos)
    return montar(VEICULO, url, g.get("first_publish_date") or g.get("display_date"),
                  _texto(g.get("headlines", {}).get("basic")),
                  _texto(g.get("subheadlines", {}).get("basic")) or None,
                  paragrafos, secao, g.get("subtype"), len(corpo), "arc-sitemap", "sitemap-slug")


def coletar() -> dict:
    destino = caminhoBruto(VEICULO)
    feitos_sm = os.path.join(cfg.PASTA_BRUTO, "_linea_sitemaps_lidos.txt")
    vistos = set()
    if os.path.exists(destino):
        with open(destino, encoding="utf-8") as f:
            vistos = {json.loads(l)["url"] for l in f if l.strip()}
    lidos = set(open(feitos_sm, encoding="utf-8").read().split()) if os.path.exists(feitos_sm) else set()
    vistos |= set(open(destino + ".descartadas", encoding="utf-8").read().split()) \
        if os.path.exists(destino + ".descartadas") else set()
    cont = {"sitemaps": 0, "urls": 0, "pre_filtro": 0, "baixadas": 0, "temáticas": 0, "erros": 0}
    dias = sitemaps_diarios()
    log(f"{VEICULO}: {len(dias)} sitemaps diários no período; {len(lidos)} já lidos")
    for i, (dia, sm) in enumerate(dias, 1):
        if sm in lidos:
            continue
        try:
            urls = [html.unescape(u) for u in re.findall(r"<loc>([^<]+)</loc>", _get(sm))
                    if "/resizer/" not in u]
        except Exception as e:  # noqa: BLE001
            cont["erros"] += 1
            log(f"  sitemap {dia} falhou: {type(e).__name__}")
            continue
        cont["sitemaps"] += 1
        cont["urls"] += len(urls)
        erros_dia = 0
        for url in (u for u in urls if slug_relevante(u) and u not in vistos):
            cont["pre_filtro"] += 1
            try:
                reg = extrair(url, _get(url))
            except Exception as e:  # noqa: BLE001
                cont["erros"] += 1
                erros_dia += 1
                log(f"  {url} falhou: {type(e).__name__}")
                continue
            if reg is None:
                # página sem o JSON da matéria (fora do ar, formato novo): não
                # vai para as descartadas, para ser tentada de novo
                erros_dia += 1
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
        # o dia só conta como lido se nenhuma matéria falhou: senão é refeito
        if erros_dia == 0:
            with open(feitos_sm, "a", encoding="utf-8") as f:
                f.write(sm + "\n")
        if i % 50 == 0:
            log(f"  {dia}: {i}/{len(dias)} sitemaps | {cont}")
    log(f"{VEICULO} concluído: {cont}")
    return cont


if __name__ == "__main__":
    cfg.definirColaborador(cfg.COLABORADOR)  # COLETA_USER ou usuário do sistema
    coletar()

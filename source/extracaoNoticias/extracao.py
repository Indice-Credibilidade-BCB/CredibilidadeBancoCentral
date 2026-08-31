# %% Extração — do JSON cru ao registro da base

import re

from bs4 import BeautifulSoup

from utilitarios import norm

# %% Limpeza de texto

AGENCIAS = (r"Valor|Divulgação|Reuters|AFP|Bloomberg|Agência Brasil|Getty|"
            r"Arquivo pessoal|Folhapress|Estadão Conteúdo|AP|EFE|Unsplash|Pixabay")
RX_LEGENDA = re.compile(rf"^.{{0,220}}?/({AGENCIAS})\b\s*")


def limparBody(texto: str) -> str:
    """Remove legenda de foto e crédito colados no início. Preserva quebras."""
    t = str(texto or "")
    t = re.sub(r"[ \t\r\xa0]+", " ", t)
    t = re.sub(r"\n{2,}", "\n\n", t).strip()
    primeira = t.split("\n", 1)[0]
    m = RX_LEGENDA.match(primeira)
    if m:
        resto = primeira[m.end():].strip()
        t = (resto + t[len(primeira):]) if resto else t[len(primeira):].lstrip("\n")
    return t.strip()


def partirParagrafos(texto: str, minimo: int = 60) -> list:
    """Usa as quebras do próprio corpo; sem elas, remonta por período."""
    bruto = str(texto or "")
    if "\n" in bruto:
        partes = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n+", bruto)]
        partes = [p for p in partes if len(p) >= minimo]
        if partes:
            return partes
    t = re.sub(r"\s+", " ", limparBody(bruto)).strip()
    paragrafos, atual = [], ""
    for frase in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú“\"])", t):
        atual = (atual + " " + frase).strip()
        if len(atual) >= 220:
            paragrafos.append(atual)
            atual = ""
    if len(atual) >= minimo:
        paragrafos.append(atual)
    return paragrafos


def paragrafosDeHtml(html, minimo: int = 60) -> list:
    soup = BeautifulSoup(str(html or ""), "lxml")
    saida = []
    for p in soup.find_all("p"):
        txt = re.sub(r"\s+", " ", p.get_text()).strip()
        if len(txt) >= minimo:
            saida.append(txt)
    return saida

# %% Montagem do registro

def montar(veiculo, url, data, titulo, subtitulo, paragrafos, secao=None,
           especie=None, tam=0, origem="", consulta="") -> dict:
    if paragrafos and subtitulo and norm(paragrafos[0])[:80] == norm(subtitulo)[:80]:
        paragrafos = paragrafos[1:]
    return {"veiculo": veiculo, "url": url, "data": data, "secao": secao,
            "especie": especie, "titulo": titulo, "subtitulo": subtitulo or None,
            "p1": paragrafos[0] if paragrafos else None,
            "p2": paragrafos[1] if len(paragrafos) > 1 else None,
            "n_paragrafos": len(paragrafos), "tam_body": tam, "origem": origem,
            "consulta": consulta}


def extrairGlobo(item, veiculo, consulta) -> dict:
    body = limparBody(item.get("body"))
    legenda = re.sub(r"\s+", " ", str(item.get("caption") or "")).strip() or None
    secao = item.get("sectionPath")
    return montar(veiculo, item.get("url"), item.get("issued"), item.get("title"),
                  legenda, partirParagrafos(body),
                  "|".join(secao) if isinstance(secao, list) else secao,
                  item.get("species"), len(body), "busca-globo", consulta)


def extrairWp(post, veiculo, consulta) -> dict:
    titulo = BeautifulSoup(post.get("title", {}).get("rendered", ""),
                           "lxml").get_text().strip()
    subtitulo = BeautifulSoup(post.get("excerpt", {}).get("rendered", ""),
                              "lxml").get_text().strip()
    corpo = post.get("content", {}).get("rendered", "")
    return montar(veiculo, post.get("link"), post.get("date"), titulo, subtitulo,
                  paragrafosDeHtml(corpo), None, None, len(corpo),
                  "wp-api", consulta)

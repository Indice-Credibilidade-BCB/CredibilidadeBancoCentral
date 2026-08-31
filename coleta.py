#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COLETA COMPLETA — notícias sobre política monetária / atuação do Banco Central

Somente veículos em FAIXA A: aqueles cuja API devolve título, linha fina e corpo
na mesma requisição da descoberta. Dois motores:

  globo      -> busca.globo.com/v1/search   (Valor, G1, O Globo…)
  wordpress  -> /wp-json/wp/v2/posts        (Poder360, InfoMoney…)

Quem é Faixa A de fato é decidido por sondagem, não por suposição.

O motor globo trava em from=10.000, então cada termo que não alcança o início da
série é SUBDIVIDIDO cruzando com os presidentes do BC — que recortam o período
por época. Os presidentes são apenas divisores: não entram na definição do
corpus, que é dada só pelos termos temáticos.

Todo o processo é compartimentado: cada par (veículo, consulta) é gravado assim
que termina e nunca é refeito. Pode interromper e retomar quantas vezes quiser.
"""

# ─────────────────────────────────────────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

INICIO = datetime(2011, 1, 1)      # o arquivo da busca da Globo chega a 2011
FIM = datetime(2026, 9, 1)

PASTA = "dados"                    # dentro do repositório, versionado
PASTA_BRUTO = os.path.join(PASTA, "bruto")
PASTA_LEDGER = os.path.join(PASTA, "concluidas")
PASTA_PLANOS = os.path.join(PASTA, "planos")

# Quem está rodando. Cada pessoa grava nos SEUS arquivos — é isso que evita
# conflito de merge quando várias fazem push. Defina antes de coletar:
#   COLABORADOR = "enzo"
COLABORADOR = (os.environ.get("COLETA_USER")
               or os.environ.get("USER")
               or os.environ.get("USERNAME")
               or "anonimo")

SINCRONIZAR_GIT = True             # commit+push automático durante a coleta
SINCRONIZAR_A_CADA = 5             # consultas concluídas entre cada push

# Repertório temático: termos específicos de política monetária.
# Deliberadamente fora: "taxa de juros", "inflação", "economia" — amplos demais,
# trazem crédito bancário, juro de cartão e preço de supermercado.
TERMOS = [
    "Copom",
    "Selic",
    "ata do Copom",
    "política monetária",
    "meta de inflação",
    "Relatório de Inflação",
    "Banco Central",
]

# Divisores para subdividir consultas que estouram o teto de paginação.
# Presidentes do BC recortam a série por época — não fazem parte do corpus.
DIVISORES = ["Tombini", "Ilan Goldfajn", "Roberto Campos Neto", "Galípolo"]
DIVISORES_2 = ["Copom", "Selic", "inflação", "reunião", "comunicado"]

# Candidatos a Faixa A. `sondar_veiculos()` confirma quais realmente respondem.
VEICULOS = {
    "Valor":          {"motor": "globo", "tenant": "valor"},
    "G1":             {"motor": "globo", "tenant": "g1"},
    "O Globo":        {"motor": "globo", "tenant": "oglobo"},
    "Poder360":       {"motor": "wordpress", "base": "https://www.poder360.com.br"},
    "InfoMoney":      {"motor": "wordpress", "base": "https://www.infomoney.com.br"},
    "Money Times":    {"motor": "wordpress", "base": "https://www.moneytimes.com.br"},
    "Agência Brasil": {"motor": "wordpress", "base": "https://agenciabrasil.ebc.com.br"},
}

# Filtro LOCAL de tema, sobre o texto já baixado (sem acento).
TERMOS_FILTRO = ["banco central", "copom", "selic", "politica monetaria",
                 "meta de inflacao", "relatorio de inflacao", "bacen"]

# Reuniões do Copom (2ª sessão). 2017 conferido; demais anos: CONFERIR no BCB.
COPOM = {
    2016: ["2016-01-20", "2016-03-02", "2016-04-27", "2016-06-08",
           "2016-07-20", "2016-08-31", "2016-10-19", "2016-11-30"],
    2017: ["2017-01-11", "2017-02-22", "2017-04-12", "2017-05-31",
           "2017-07-26", "2017-09-06", "2017-10-25", "2017-12-06"],
}
JANELA_COPOM = 2

PAUSA = 3.0
TIMEOUT = 45
TETO_FROM = 10000
CONTADOR = {}


def log(m):
    print(f"[{datetime.now():%H:%M:%S}] {m}", flush=True)


def norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


RX_TERMOS = re.compile("|".join(re.escape(norm(t)) for t in TERMOS_FILTRO))


def casa_termo(*campos):
    return bool(RX_TERMOS.search(norm(" ".join(str(c or "") for c in campos))))


# ─────────────────────────────────────────────────────────────────────────────
# TRANSPORTE
# ─────────────────────────────────────────────────────────────────────────────

CABECALHOS = {
    "accept": "*/*",
    "accept-language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "sec-ch-ua": '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"),
    "x-must-thumborize": "true",
    "x-track-urls": "true",
}


def nova_sessao():
    s = requests.Session()
    s.headers.update(CABECALHOS)
    s.mount("https://", HTTPAdapter(max_retries=Retry(
        total=4, connect=4, read=4, backoff_factor=2.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]))))
    return s


SESSAO = nova_sessao()
BUSCA_GLOBO = "https://busca.globo.com/v1/search"


def conta(veiculo):
    CONTADOR[veiculo] = CONTADOR.get(veiculo, 0) + 1


def buscar_globo(q, frm=0, size=10, tenant="valor", veiculo="?", tentativas=3):
    global SESSAO
    origem = f"https://{'valor' if tenant == 'valor' else tenant}.globo.com"
    corpo = [{"search_profile": f"sp_{tenant}_globo_com",
              "query": f"{tenant}.info_query_recency",
              "params": {"q": q, "from": frm, "size": size}}]
    cab = dict(CABECALHOS, **{"x-tenant-id": tenant, "origin": origem,
                              "referer": f"{origem}/busca/?q={q}"})
    for t in range(1, tentativas + 1):
        try:
            r = SESSAO.post(BUSCA_GLOBO, json=corpo, headers=cab, timeout=TIMEOUT)
            conta(veiculo)
            time.sleep(PAUSA)
            try:
                return r.status_code, r.json()
            except ValueError:
                return r.status_code, r.text[:400]
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            espera = 10 * t
            log(f"    conexão caiu ({type(e).__name__}); nova sessão em {espera}s "
                f"[{t}/{tentativas}]")
            time.sleep(espera)
            SESSAO = nova_sessao()
    return None, None


def itens_da_resposta(js):
    """Resposta é Elasticsearch cru: result.hits.hits[] com campos em _source."""
    fila = [js]
    while fila:
        o = fila.pop(0)
        if isinstance(o, list):
            if o and isinstance(o[0], dict):
                if "_source" in o[0]:
                    return [dict(h.get("_source") or {}, _id=h.get("_id"))
                            for h in o if isinstance(h, dict)]
                if any(k in o[0] for k in ("url", "link", "title")):
                    return o
            fila.extend(x for x in o if isinstance(x, (dict, list)))
        elif isinstance(o, dict):
            fila.extend(v for v in o.values() if isinstance(v, (dict, list)))
    return []


def total_de_hits(js):
    """10.000 é o track_total_hits do Elasticsearch: significa '>= 10.000'."""
    fila = [js]
    while fila:
        o = fila.pop(0)
        if isinstance(o, dict):
            t = o.get("total")
            if isinstance(t, dict) and "value" in t:
                return t["value"]
            if t is not None and not isinstance(t, (dict, list)):
                return t
            fila.extend(v for v in o.values() if isinstance(v, (dict, list)))
        elif isinstance(o, list):
            fila.extend(x for x in o if isinstance(x, (dict, list)))
    return None


# ─────────────────────────────────────────────────────────────────────────────
# EXTRAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

AGENCIAS = (r"Valor|Divulgação|Reuters|AFP|Bloomberg|Agência Brasil|Getty|"
            r"Arquivo pessoal|Folhapress|Estadão Conteúdo|AP|EFE|Unsplash|Pixabay")
RX_LEGENDA = re.compile(rf"^.{{0,220}}?/({AGENCIAS})\b\s*")


def limpar_body(texto):
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


def partir_paragrafos(texto, minimo=60):
    bruto = str(texto or "")
    if "\n" in bruto:
        partes = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n+", bruto)]
        partes = [p for p in partes if len(p) >= minimo]
        if partes:
            return partes
    t = re.sub(r"\s+", " ", limpar_body(bruto)).strip()
    paras, atual = [], ""
    for f in re.split(r"(?<=[.!?])\s+(?=[A-ZÀ-Ú“\"])", t):
        atual = (atual + " " + f).strip()
        if len(atual) >= 220:
            paras.append(atual)
            atual = ""
    if len(atual) >= minimo:
        paras.append(atual)
    return paras


def montar(veiculo, url, data, titulo, subtitulo, paras, secao=None, especie=None,
           tam=0, origem="", consulta=""):
    if paras and subtitulo and norm(paras[0])[:80] == norm(subtitulo)[:80]:
        paras = paras[1:]
    return {"veiculo": veiculo, "url": url, "data": data, "secao": secao,
            "especie": especie, "titulo": titulo, "subtitulo": subtitulo or None,
            "p1": paras[0] if paras else None,
            "p2": paras[1] if len(paras) > 1 else None,
            "n_paragrafos": len(paras), "tam_body": tam, "origem": origem,
            "consulta": consulta}


def extrair_globo(it, veiculo, consulta):
    body = limpar_body(it.get("body"))
    cap = re.sub(r"\s+", " ", str(it.get("caption") or "")).strip() or None
    secao = it.get("sectionPath")
    return montar(veiculo, it.get("url"), it.get("issued"), it.get("title"), cap,
                  partir_paragrafos(body),
                  "|".join(secao) if isinstance(secao, list) else secao,
                  it.get("species"), len(body), "busca-globo", consulta)


def paragrafos_de_html(html, minimo=60):
    soup = BeautifulSoup(str(html or ""), "lxml")
    out = []
    for p in soup.find_all("p"):
        txt = re.sub(r"\s+", " ", p.get_text()).strip()
        if len(txt) >= minimo:
            out.append(txt)
    return out


def extrair_wp(p, veiculo, consulta):
    titulo = BeautifulSoup(p.get("title", {}).get("rendered", ""),
                           "lxml").get_text().strip()
    sub = BeautifulSoup(p.get("excerpt", {}).get("rendered", ""),
                        "lxml").get_text().strip()
    corpo = p.get("content", {}).get("rendered", "")
    return montar(veiculo, p.get("link"), p.get("date"), titulo, sub,
                  paragrafos_de_html(corpo), None, None, len(corpo),
                  "wp-api", consulta)


# ─────────────────────────────────────────────────────────────────────────────
# SONDAGEM — quem é Faixa A de fato
# ─────────────────────────────────────────────────────────────────────────────

def sondar_veiculos(veiculos=None):
    """
    Faixa A exige que a resposta traga corpo do texto na própria descoberta.
    Testa cada candidato e reporta. Só os aprovados entram na coleta.
    """
    veiculos = veiculos or VEICULOS
    linhas = []
    for nome, cfg in veiculos.items():
        r = {"veiculo": nome, "motor": cfg["motor"], "http": None,
             "itens": 0, "tem_corpo": False, "faixa_a": False, "obs": ""}
        try:
            if cfg["motor"] == "globo":
                st, js = buscar_globo("Copom", 0, 3, cfg["tenant"], nome)
                itens = itens_da_resposta(js) if st == 200 else []
                r["http"], r["itens"] = st, len(itens)
                if itens:
                    corpo = str(itens[0].get("body") or "")
                    r["tem_corpo"] = len(corpo) > 500
                    r["obs"] = f"body={len(corpo)} car."
            else:
                resp = SESSAO.get(f'{cfg["base"]}/wp-json/wp/v2/posts',
                                  params={"per_page": 1, "search": "Copom",
                                          "_fields": "link,title,excerpt,content,date"},
                                  timeout=TIMEOUT)
                conta(nome)
                time.sleep(PAUSA)
                r["http"] = resp.status_code
                if resp.status_code == 200:
                    js = resp.json()
                    r["itens"] = len(js)
                    if js:
                        corpo = js[0].get("content", {}).get("rendered", "")
                        r["tem_corpo"] = len(corpo) > 500
                        r["obs"] = f"content={len(corpo)} car."
                else:
                    r["obs"] = resp.text[:80]
        except requests.RequestException as e:
            r["obs"] = f"{type(e).__name__}"
        r["faixa_a"] = bool(r["itens"]) and r["tem_corpo"]
        linhas.append(r)

    df = pd.DataFrame(linhas)
    print(df.to_string(index=False))
    aprovados = df[df["faixa_a"]]["veiculo"].tolist()
    print(f"\nFaixa A confirmada: {aprovados}")
    reprovados = df[~df["faixa_a"]]["veiculo"].tolist()
    if reprovados:
        print(f"Fora da coleta: {reprovados}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# PLANEJADOR (motor globo)
# ─────────────────────────────────────────────────────────────────────────────

def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")[:80]


def medir_termo(q, tenant, veiculo):
    st, js = buscar_globo(q, 0, 1, tenant, veiculo)
    total = total_de_hits(js) if st == 200 else None
    if not isinstance(total, int) or total == 0:
        return total, None
    if total < TETO_FROM:
        return total, None
    st2, js2 = buscar_globo(q, TETO_FROM - 100, 10, tenant, veiculo)
    itens = itens_da_resposta(js2) if st2 == 200 else []
    if not itens:
        return total, None
    d = pd.to_datetime(itens[-1].get("issued"), errors="coerce", utc=True)
    return total, (d.tz_convert("America/Sao_Paulo").tz_localize(None)
                   if pd.notna(d) else None)


def testar_conjuncao(tenant="valor", veiculo="Valor", a="Copom", b="Tombini"):
    """A busca combina palavras com E? Se não, subdividir não reduz o conjunto."""
    ta, _ = medir_termo(a, tenant, veiculo)
    tb, _ = medir_termo(b, tenant, veiculo)
    tab, _ = medir_termo(f"{a} {b}", tenant, veiculo)
    print(f"  {a!r}={ta} | {b!r}={tb} | {a + ' ' + b!r}={tab}")
    if not all(isinstance(x, int) for x in (ta, tb, tab)):
        print("  não foi possível medir")
        return None
    ok = tab < min(ta, tb)
    print("  -> conjunção (E): subdividir funciona" if ok else
          "  -> NÃO reduz: subdividir não vai adiantar")
    return ok


def expandir(termo, tenant, veiculo, fim, prof=0, max_prof=2, _visto=None):
    """Subdivide a consulta até cada pedaço caber no teto de paginação."""
    _visto = _visto if _visto is not None else set()
    if termo in _visto:
        return []
    _visto.add(termo)

    total, limite = medir_termo(termo, tenant, veiculo)
    if not isinstance(total, int) or total == 0:
        return [{"consulta": termo, "total": total, "alcance": None,
                 "status": "sem resultados", "nivel": prof}]
    if total < TETO_FROM:
        return [{"consulta": termo, "total": total, "alcance": "completo",
                 "status": "enumerável", "nivel": prof}]
    if limite is not None and limite < fim:
        return [{"consulta": termo, "total": total, "alcance": str(limite.date()),
                 "status": "alcança a janela", "nivel": prof}]
    if prof >= max_prof:
        return [{"consulta": termo, "total": total,
                 "alcance": str(limite.date()) if limite is not None else None,
                 "status": "TRUNCADO", "nivel": prof}]

    divs = DIVISORES if prof == 0 else DIVISORES_2
    log(f"    {termo!r} trava em "
        f"{limite.strftime('%Y-%m') if limite is not None else '?'} — subdividindo")
    saida = []
    for d in divs:
        if norm(d) in norm(termo):
            continue
        saida += expandir(f"{termo} {d}", tenant, veiculo, fim,
                          prof + 1, max_prof, _visto)
    return saida


def planejar(veiculo, tenant, termos=None, ini=None, fim=None, max_prof=2,
             usar_cache=True):
    """
    Monta (ou completa) o plano de consultas do veículo. O plano fica em disco e
    é compartilhado no repositório: numa retomada ele é lido, não refeito.
    Termo NOVO — que ninguém planejou ainda — é acrescentado ao plano existente,
    então dá para ampliar o repertório sem jogar fora o trabalho anterior.
    """
    termos, ini, fim = termos or TERMOS, ini or INICIO, fim or FIM
    os.makedirs(PASTA_PLANOS, exist_ok=True)
    cache = os.path.join(PASTA_PLANOS, f"plano_{_slug(veiculo)}.csv")

    plano = pd.DataFrame()
    if usar_cache and os.path.exists(cache):
        plano = pd.read_csv(cache)

    def coberto(t):
        if plano.empty:
            return False
        c = plano["consulta"].astype(str)
        return bool((c == t).any() or c.str.startswith(t + " ").any())

    faltando = [t for t in termos if not coberto(t)]
    if not faltando:
        log(f"  plano em cache: {int(plano['usar'].sum())} consulta(s)")
        return plano

    linhas = []
    for t in faltando:
        log(f"  planejando {t!r}")
        linhas += expandir(t, tenant, veiculo, fim, max_prof=max_prof)

    novo = pd.DataFrame(linhas)
    novo["veiculo"] = veiculo
    plano = (pd.concat([plano, novo], ignore_index=True)
             if not plano.empty else novo).drop_duplicates(subset="consulta")
    plano["usar"] = plano["status"].isin(["enumerável", "alcança a janela"])
    plano.to_csv(cache, index=False, encoding="utf-8-sig")

    trunc = int((plano["status"] == "TRUNCADO").sum())
    print(f"  {int(plano['usar'].sum())} consulta(s) utilizáveis"
          + (f", {trunc} truncada(s)" if trunc else ""))
    return plano


# ─────────────────────────────────────────────────────────────────────────────
# CHECKPOINT — compartimentação do processo
# ─────────────────────────────────────────────────────────────────────────────

def _caminho(veiculo):
    """Um arquivo por veículo POR PESSOA — dois colaboradores nunca escrevem
    no mesmo arquivo, então o git não tem o que conflitar."""
    os.makedirs(PASTA_BRUTO, exist_ok=True)
    return os.path.join(PASTA_BRUTO, f"{_slug(veiculo)}__{_slug(COLABORADOR)}.jsonl")


def _arquivo_feitos(colaborador=None):
    os.makedirs(PASTA_LEDGER, exist_ok=True)
    return os.path.join(PASTA_LEDGER, f"{_slug(colaborador or COLABORADOR)}.txt")


def carregar_feitas():
    """
    Lê o registro de TODOS os colaboradores: se seu amigo já varreu
    'Copom Tombini' no Valor, você não refaz.
    """
    feitas = set()
    if os.path.isdir(PASTA_LEDGER):
        for nome in os.listdir(PASTA_LEDGER):
            if nome.endswith(".txt"):
                with open(os.path.join(PASTA_LEDGER, nome), encoding="utf-8") as f:
                    feitas |= {l.strip() for l in f if l.strip()}
    return feitas


def marcar_feita(chave):
    with open(_arquivo_feitos(), "a", encoding="utf-8") as f:
        f.write(chave + "\n")
        f.flush()
        os.fsync(f.fileno())


def gravar(veiculo, registros):
    if not registros:
        return
    with open(_caminho(veiculo), "a", encoding="utf-8") as f:
        for r in registros:
            r = dict(r, colaborador=COLABORADOR)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


# ── sincronização com o repositório ──────────────────────────────────────────

def _git(*args, checar=True):
    import subprocess
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if checar and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r


def git_disponivel():
    try:
        return _git("rev-parse", "--is-inside-work-tree", checar=False).returncode == 0
    except FileNotFoundError:
        return False


def git_puxar():
    """Traz o progresso dos outros antes de começar."""
    if not (SINCRONIZAR_GIT and git_disponivel()):
        return False
    r = _git("pull", "--rebase", "--autostash", checar=False)
    if r.returncode != 0:
        log(f"  git pull falhou: {r.stderr.strip()[:200]}")
        return False
    log("  repositório atualizado")
    return True


def git_enviar(mensagem="coleta"):
    """
    Publica o que esta pessoa coletou. Como cada um só escreve nos próprios
    arquivos, o rebase resolve sozinho; ainda assim tenta de novo em caso de
    corrida com outro push.
    """
    if not (SINCRONIZAR_GIT and git_disponivel()):
        return False
    _git("add", PASTA, checar=False)
    if not _git("diff", "--cached", "--quiet", checar=False).returncode:
        return False                                   # nada mudou
    _git("commit", "-m", f"{mensagem} [{COLABORADOR}]", checar=False)
    for tentativa in range(3):
        if _git("push", checar=False).returncode == 0:
            log(f"  push ok ({mensagem})")
            return True
        log(f"  push rejeitado; rebase e nova tentativa [{tentativa + 1}/3]")
        if _git("pull", "--rebase", "--autostash", checar=False).returncode != 0:
            log("  rebase falhou — resolva à mão e rode de novo")
            return False
    return False


GITIGNORE = """\
__pycache__/
*.pyc
.ipynb_checkpoints/
.venv/
env/
.DS_Store
.env
*.log
"""

LEIAME = """\
# Coleta de notícias sobre política monetária

Base para quantificar a percepção pública sobre a atuação do Banco Central.

## Como participar

1. `pip install -r requirements.txt`
2. Abra `coleta.ipynb` e defina `COLABORADOR = "seunome"` na célula de configuração.
3. Rode a sondagem, depois `coletar_tudo()`.

Cada pessoa grava nos próprios arquivos (`dados/bruto/<veiculo>__<pessoa>.jsonl`),
então ninguém sobrescreve o trabalho de ninguém. O registro de consultas
concluídas é compartilhado: o que um já coletou, o outro pula.

Se forem coletar ao mesmo tempo, dividam os termos antes com
`dividir_trabalho(["enzo", "amigo"])`.

## Estrutura

    dados/bruto/        registros crus, um arquivo por veículo por pessoa
    dados/concluidas/   o que cada pessoa já varreu
    dados/planos/       partições planejadas por veículo (compartilhado)
    dados/noticias.csv  base consolidada (gerada por consolidar())

## Aviso

O repositório armazena título, linha fina e os dois primeiros parágrafos de
matérias de terceiros. Mantenha o repositório **privado**: redistribuir texto
jornalístico publicamente esbarra em direito autoral e nos termos de uso dos
veículos.
"""

REQUISITOS = "requests\npandas\nbeautifulsoup4\nlxml\nmatplotlib\n"


def preparar_repositorio():
    """Cria .gitignore, README e requirements — rode uma vez, antes do 1º push."""
    for nome, conteudo in [(".gitignore", GITIGNORE), ("README.md", LEIAME),
                           ("requirements.txt", REQUISITOS)]:
        if not os.path.exists(nome):
            with open(nome, "w", encoding="utf-8") as f:
                f.write(conteudo)
            print(f"  criado: {nome}")
        else:
            print(f"  já existe: {nome}")
    for p in (PASTA_BRUTO, PASTA_LEDGER, PASTA_PLANOS):
        os.makedirs(p, exist_ok=True)
        guard = os.path.join(p, ".gitkeep")
        if not os.path.exists(guard):
            open(guard, "w").close()
    print(f"\nColaborador atual: {COLABORADOR!r}")
    print("Se não for o seu nome, defina COLABORADOR na célula de configuração.")


# ─────────────────────────────────────────────────────────────────────────────
# VARREDURA
# ─────────────────────────────────────────────────────────────────────────────

def varrer_globo(consulta, veiculo, tenant, ini, fim, size=100, so_materias=True):
    registros, frm, parar, truncou, ultima = [], 0, False, False, None
    while frm < TETO_FROM and not parar:
        st, js = buscar_globo(consulta, frm, size, tenant, veiculo)
        if st != 200 or not js:
            if st == 400:
                truncou = True
            break
        itens = itens_da_resposta(js)
        if not itens:
            break
        antigas = 0
        for it in itens:
            if so_materias and it.get("species") not in (None, "Matéria"):
                continue
            d = pd.to_datetime(it.get("issued"), errors="coerce", utc=True)
            if pd.isna(d):
                continue
            d = d.tz_convert("America/Sao_Paulo").tz_localize(None)
            if d < ini:
                antigas += 1
                continue
            if d >= fim:
                continue
            r = extrair_globo(it, veiculo, consulta)
            if casa_termo(r["titulo"], r["subtitulo"], r["p1"]):
                registros.append(r)
        u = pd.to_datetime(itens[-1].get("issued"), errors="coerce", utc=True)
        ultima = u.date() if pd.notna(u) else ultima
        if antigas >= len(itens) * 0.8:
            parar = True
        frm += size
    if frm >= TETO_FROM and not parar:
        truncou = True
    return registros, {"chegou_em": ultima, "truncou": truncou}


def varrer_wp(termo, veiculo, base, ano, ini, fim):
    """WordPress filtra data no servidor: uma fatia por ano, sem teto."""
    registros = []
    a = max(datetime(ano, 1, 1), ini)
    b = min(datetime(ano + 1, 1, 1), fim)
    if a >= b:
        return registros, {"total": 0}
    pagina, total = 1, None
    while True:
        r = SESSAO.get(f"{base}/wp-json/wp/v2/posts", timeout=TIMEOUT, params={
            "search": termo, "after": a.isoformat(), "before": b.isoformat(),
            "per_page": 100, "page": pagina, "orderby": "date", "order": "asc",
            "_fields": "link,title,excerpt,content,date"})
        conta(veiculo)
        time.sleep(PAUSA)
        if total is None:
            total = r.headers.get("X-WP-Total")
        if r.status_code != 200:
            break
        posts = r.json()
        if not posts:
            break
        for p in posts:
            reg = extrair_wp(p, veiculo, termo)
            if casa_termo(reg["titulo"], reg["subtitulo"], reg["p1"]):
                registros.append(reg)
        if len(posts) < 100:
            break
        pagina += 1
    return registros, {"total": total}


# ─────────────────────────────────────────────────────────────────────────────
# ORQUESTRADOR
# ─────────────────────────────────────────────────────────────────────────────

def dividir_trabalho(pessoas, termos=None):
    """
    Reparte os termos entre as pessoas de forma determinística: cada uma roda a
    sua fatia e ninguém duplica esforço mesmo trabalhando ao mesmo tempo.
    O registro compartilhado ainda protege contra sobreposição acidental.
    """
    termos = termos or TERMOS
    pessoas = sorted(pessoas)
    lotes = {p: [] for p in pessoas}
    for i, t in enumerate(termos):
        lotes[pessoas[i % len(pessoas)]].append(t)
    for p, ts in lotes.items():
        print(f"  {p:12} → {ts}")
    return lotes


def coletar_tudo(veiculos=None, termos=None, ini=None, fim=None, sondagem=None,
                 max_prof=2, replanejar=False, sincronizar=None):
    """
    Percorre os veículos Faixa A. Cada consulta concluída é gravada, marcada e
    (se houver git) publicada periodicamente. Consulta já feita por QUALQUER
    colaborador é pulada.
    """
    ini, fim = ini or INICIO, fim or FIM
    termos = termos or TERMOS
    sincronizar = SINCRONIZAR_GIT if sincronizar is None else sincronizar
    if sondagem is not None:
        nomes = sondagem[sondagem["faixa_a"]]["veiculo"].tolist()
        veiculos = {k: v for k, v in VEICULOS.items() if k in nomes}
    veiculos = veiculos or VEICULOS

    if sincronizar:
        git_puxar()
    feitas = carregar_feitas()
    log(f"{len(feitas)} consulta(s) já concluída(s) (todos os colaboradores).")
    log(f"Gravando como {COLABORADOR!r}.")

    planos, resumo, desde_push = [], [], 0

    def talvez_publicar(forcar=False):
        nonlocal desde_push
        if not sincronizar:
            return
        if forcar or desde_push >= SINCRONIZAR_A_CADA:
            git_enviar(f"coleta: +{desde_push} consulta(s)")
            desde_push = 0

    for nome, cfg in veiculos.items():
        log(f"═══ {nome} ({cfg['motor']})")

        if cfg["motor"] == "globo":
            plano = planejar(nome, cfg["tenant"], termos, ini, fim, max_prof,
                             usar_cache=not replanejar)
            planos.append(plano)
            for _, linha in plano[plano["usar"]].iterrows():
                chave = f"{nome}||{linha['consulta']}"
                if chave in feitas:
                    continue
                regs, info = varrer_globo(linha["consulta"], nome, cfg["tenant"],
                                          ini, fim)
                gravar(nome, regs)
                marcar_feita(chave)
                feitas.add(chave)
                desde_push += 1
                log(f"  {linha['consulta']!r}: {len(regs)} notícias | "
                    f"chegou em {info['chegou_em']}"
                    + ("  [TRUNCADA]" if info["truncou"] else ""))
                resumo.append({"veiculo": nome, "consulta": linha["consulta"],
                               "n": len(regs), "truncou": info["truncou"]})
                talvez_publicar()
        else:
            for termo in termos:
                for ano in range(ini.year, fim.year + 1):
                    chave = f"{nome}||{termo}||{ano}"
                    if chave in feitas:
                        continue
                    regs, info = varrer_wp(termo, nome, cfg["base"], ano, ini, fim)
                    gravar(nome, regs)
                    marcar_feita(chave)
                    feitas.add(chave)
                    desde_push += 1
                    if regs:
                        log(f"  {termo!r} {ano}: {len(regs)} notícias "
                            f"(busca achou {info['total']})")
                    resumo.append({"veiculo": nome, "consulta": f"{termo} [{ano}]",
                                   "n": len(regs), "truncou": False})
                    talvez_publicar()

    talvez_publicar(forcar=True)
    df_res = pd.DataFrame(resumo)
    if not df_res.empty:
        print("\n" + df_res.groupby("veiculo")["n"].agg(["sum", "size"]).to_string())
    return df_res


def consolidar(exigir_p2=True, puxar=True):
    """Junta os arquivos brutos de TODOS os colaboradores e monta a base final."""
    if puxar:
        git_puxar()
    arquivos = ([os.path.join(PASTA_BRUTO, f) for f in os.listdir(PASTA_BRUTO)
                 if f.endswith(".jsonl")] if os.path.isdir(PASTA_BRUTO) else [])
    registros = []
    for a in arquivos:
        with open(a, encoding="utf-8") as f:
            for l in f:
                try:
                    registros.append(json.loads(l))
                except json.JSONDecodeError:
                    pass
    if not registros:
        print("Nada coletado ainda.")
        return pd.DataFrame()
    print(f"{len(arquivos)} arquivo(s) de {len({r.get('colaborador') for r in registros})} "
          f"colaborador(es)")

    df = pd.DataFrame(registros)
    n0 = len(df)

    # a mesma notícia chega por várias consultas — dedup por URL normalizada
    df["chave_url"] = (df["url"].astype(str).str.replace(r"[?#].*$", "", regex=True)
                       .str.rstrip("/").str.lower())
    df = df.drop_duplicates(subset="chave_url")

    df["data"] = pd.to_datetime(df["data"], errors="coerce", utc=True, format="mixed")
    df = df[df["data"].notna()]
    df["data"] = df["data"].dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)

    df = df[df["titulo"].notna() & df["p1"].notna()]
    if exigir_p2:
        df = df[df["p2"].notna()]

    # matéria de agência republicada: mesmo título em veículos diferentes
    df["chave_tit"] = df["titulo"].map(lambda t: re.sub(r"[^a-z0-9 ]", " ", norm(t)))
    df = df.sort_values("data")
    df["n_replicacoes"] = df.groupby("chave_tit")["chave_tit"].transform("size")
    df["replicada"] = df.duplicated(subset="chave_tit", keep="first")

    df["texto_llm"] = df.apply(lambda r: "\n\n".join(x for x in [
        f"TÍTULO: {r['titulo']}",
        f"SUBTÍTULO: {r['subtitulo']}" if pd.notna(r["subtitulo"]) else None,
        f"TEXTO: {r['p1']}",
        r["p2"] if pd.notna(r["p2"]) else None] if x), axis=1)

    cols = ["veiculo", "data", "url", "titulo", "subtitulo", "p1", "p2", "secao",
            "n_paragrafos", "consulta", "n_replicacoes", "replicada", "texto_llm"]
    df = df[cols].sort_values(["data", "veiculo"]).reset_index(drop=True)

    os.makedirs(PASTA, exist_ok=True)
    df.to_csv(os.path.join(PASTA, "noticias.csv"), index=False, encoding="utf-8-sig")
    unicas = df[~df["replicada"]]
    with open(os.path.join(PASTA, "para_llm.jsonl"), "w", encoding="utf-8") as f:
        for i, r in unicas.iterrows():
            f.write(json.dumps({"id": f"{_slug(r['veiculo'])[:4]}-{i:06d}",
                                "veiculo": r["veiculo"],
                                "data": r["data"].strftime("%Y-%m-%d"),
                                "url": r["url"], "texto": r["texto_llm"]},
                               ensure_ascii=False) + "\n")
    print(f"{n0} brutos → {len(df)} após dedup e filtros → "
          f"{len(unicas)} sem replicação de agência")
    git_enviar("consolidação da base")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# DIAGNÓSTICO
# ─────────────────────────────────────────────────────────────────────────────

def cobertura_mensal(df):
    """Meses zerados indicam falha de coleta, não ausência de notícia."""
    m = (df.set_index("data").groupby("veiculo").resample("MS").size()
         .unstack(0).fillna(0).astype(int))
    vazios = {c: int((m[c] == 0).sum()) for c in m.columns}
    print("Meses sem nenhuma notícia, por veículo:")
    for k, v in sorted(vazios.items(), key=lambda x: -x[1]):
        print(f"  {k:16} {v}")
    return m


def teste_copom(df):
    """Cada decisão do Copom teve cobertura na janela de 2 dias?"""
    linhas = []
    for veiculo, g in df.groupby("veiculo"):
        for ano, datas in COPOM.items():
            for dt in datas:
                ref = pd.Timestamp(dt)
                n = int(((g["data"] >= ref) &
                         (g["data"] < ref + pd.Timedelta(days=JANELA_COPOM))).sum())
                linhas.append({"veiculo": veiculo, "ano": ano, "reuniao": dt,
                               "noticias": n, "coberta": n > 0})
    cob = pd.DataFrame(linhas)
    if cob.empty:
        return cob
    print(cob.groupby(["veiculo", "ano"]).agg(
        cobertas=("coberta", "sum"), taxa=("coberta", "mean"),
        noticias=("noticias", "sum")).to_string())
    return cob


def relatorio(df):
    print("\n" + "═" * 76)
    print("VOLUME POR VEÍCULO E ANO")
    print("═" * 76)
    print(df.assign(ano=df["data"].dt.year).pivot_table(
        index="ano", columns="veiculo", values="url", aggfunc="size",
        fill_value=0).to_string())

    print("\n" + "═" * 76)
    print("COMPLETUDE E CUSTO")
    print("═" * 76)
    for v, g in df.groupby("veiculo"):
        req = CONTADOR.get(v, 0)
        taxa = f"{req / len(g):.2f}" if len(g) else "—"
        print(f"  {v:16} n={len(g):6} | subtítulo={g['subtitulo'].notna().mean():.2f}"
              f" | p2={g['p2'].notna().mean():.2f} | {req} req ({taxa} req/notícia)")

    print("\n" + "═" * 76)
    print("COBERTURA DO COPOM (anos com calendário conferido)")
    print("═" * 76)
    teste_copom(df)
    return df

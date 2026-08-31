# %% Transporte — sessão HTTP e a busca da Globo

import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import configuracao as cfg
from utilitarios import log

# %% Sessão

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

BUSCA_GLOBO = "https://busca.globo.com/v1/search"

CONTADOR = {}      # requisições por veículo, para o relatório de custo


def novaSessao() -> requests.Session:
    s = requests.Session()
    s.headers.update(CABECALHOS)
    s.mount("https://", HTTPAdapter(max_retries=Retry(
        total=4, connect=4, read=4, backoff_factor=2.0,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST"]))))
    return s


SESSAO = novaSessao()


def sessaoAtual() -> requests.Session:
    """A sessão é recriada quando a conexão cai, então quem for usar deve
    pedir por aqui em vez de guardar a referência."""
    return SESSAO


def conta(veiculo) -> None:
    CONTADOR[veiculo] = CONTADOR.get(veiculo, 0) + 1

# %% Busca da Globo

def buscarGlobo(q, frm=0, size=10, tenant="valor", veiculo="?", tentativas=3):
    global SESSAO
    origem = f"https://{'valor' if tenant == 'valor' else tenant}.globo.com"
    corpo = [{"search_profile": f"sp_{tenant}_globo_com",
              "query": f"{tenant}.info_query_recency",
              "params": {"q": q, "from": frm, "size": size}}]
    cabecalho = dict(CABECALHOS, **{"x-tenant-id": tenant, "origin": origem,
                                    "referer": f"{origem}/busca/?q={q}"})
    for t in range(1, tentativas + 1):
        try:
            r = SESSAO.post(BUSCA_GLOBO, json=corpo, headers=cabecalho,
                            timeout=cfg.TIMEOUT)
            conta(veiculo)
            time.sleep(cfg.PAUSA)
            try:
                return r.status_code, r.json()
            except ValueError:
                return r.status_code, r.text[:400]
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout) as e:
            espera = 10 * t
            log(f"    conexão caiu ({type(e).__name__}); nova sessão em {espera}s "
                f"[{t}/{tentativas}]")
            time.sleep(espera)
            SESSAO = novaSessao()
    return None, None

# %% Leitura da resposta do Elasticsearch

def itensDaResposta(js):
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


def totalDeHits(js):
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

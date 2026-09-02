# %% Utilitários compartilhados

import re
import unicodedata
from datetime import datetime
from urllib.parse import parse_qs, unquote, urlparse

import configuracao as cfg

# %% Funções

def log(mensagem) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {mensagem}", flush=True)


def desembrulharUrl(u) -> str:
    """Extrai a URL real de dentro do redirecionador de clique da Globo.

    A busca da Globo entrega measures.globo.com/v1/click?...&u=<url real>.
    O PATH é idêntico para toda matéria (só a query muda) — por isso
    normalizar removendo a query (como um dedup ingênuo faria) colapsa
    TODO o veículo num único id. Vimos isso na prática: consolidar() sem
    este desembrulho reduziu 5.262 brutos da Valor a 1 registro só."""
    u = str(u or "")
    try:
        p = urlparse(u)
    except ValueError:
        return u
    if "measures.globo.com" in p.netloc or p.path.endswith("/v1/click"):
        q = parse_qs(p.query)
        for chave in ("u", "url"):
            if q.get(chave):
                return unquote(q[chave][0])
    return u


def norm(texto) -> str:
    """Minúscula e sem acento — a forma em que os filtros comparam."""
    t = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def slug(texto) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(texto)).strip("-")[:80]


RX_TERMOS = re.compile("|".join(re.escape(norm(t)) for t in cfg.TERMOS_FILTRO))


def casaTermo(*campos) -> bool:
    """A notícia é mesmo de política monetária? Filtro local, pós-download."""
    return bool(RX_TERMOS.search(norm(" ".join(str(c or "") for c in campos))))

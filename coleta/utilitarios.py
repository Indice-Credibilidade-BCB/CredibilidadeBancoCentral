# %% Utilitários compartilhados

import re
import unicodedata
from datetime import datetime

import configuracao as cfg

# %% Funções

def log(mensagem) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {mensagem}", flush=True)


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

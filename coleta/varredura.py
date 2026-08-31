# %% Varredura — percorre uma consulta até o fim

import time
from datetime import datetime

import pandas as pd

import configuracao as cfg
import transporte
from extracao import extrairGlobo, extrairWp
from transporte import buscarGlobo, conta, itensDaResposta
from utilitarios import casaTermo

# %% Motor globo

def varrerGlobo(consulta, veiculo, tenant, ini, fim, size=100, soMaterias=True):
    registros, frm, parar, truncou, ultima = [], 0, False, False, None
    while frm < cfg.TETO_FROM and not parar:
        st, js = buscarGlobo(consulta, frm, size, tenant, veiculo)
        if st != 200 or not js:
            if st == 400:
                truncou = True
            break
        itens = itensDaResposta(js)
        if not itens:
            break
        antigas = 0
        for item in itens:
            if soMaterias and item.get("species") not in (None, "Matéria"):
                continue
            d = pd.to_datetime(item.get("issued"), errors="coerce", utc=True)
            if pd.isna(d):
                continue
            d = d.tz_convert("America/Sao_Paulo").tz_localize(None)
            if d < ini:
                antigas += 1
                continue
            if d >= fim:
                continue
            r = extrairGlobo(item, veiculo, consulta)
            if casaTermo(r["titulo"], r["subtitulo"], r["p1"]):
                registros.append(r)
        u = pd.to_datetime(itens[-1].get("issued"), errors="coerce", utc=True)
        ultima = u.date() if pd.notna(u) else ultima
        if antigas >= len(itens) * 0.8:
            parar = True
        frm += size
    if frm >= cfg.TETO_FROM and not parar:
        truncou = True
    return registros, {"chegou_em": ultima, "truncou": truncou}

# %% Motor wordpress

def varrerWp(termo, veiculo, base, ano, ini, fim):
    """WordPress filtra data no servidor: uma fatia por ano, sem teto."""
    registros = []
    a = max(datetime(ano, 1, 1), ini)
    b = min(datetime(ano + 1, 1, 1), fim)
    if a >= b:
        return registros, {"total": 0}
    pagina, total = 1, None
    while True:
        r = transporte.sessaoAtual().get(
            f"{base}/wp-json/wp/v2/posts", timeout=cfg.TIMEOUT, params={
                "search": termo, "after": a.isoformat(), "before": b.isoformat(),
                "per_page": 100, "page": pagina, "orderby": "date", "order": "asc",
                "_fields": "link,title,excerpt,content,date"})
        conta(veiculo)
        time.sleep(cfg.PAUSA)
        if total is None:
            total = r.headers.get("X-WP-Total")
        if r.status_code != 200:
            break
        posts = r.json()
        if not posts:
            break
        for p in posts:
            reg = extrairWp(p, veiculo, termo)
            if casaTermo(reg["titulo"], reg["subtitulo"], reg["p1"]):
                registros.append(reg)
        if len(posts) < 100:
            break
        pagina += 1
    return registros, {"total": total}

# %% Varredura — percorre uma consulta até o fim
#
# Cada varredura devolve (registros, info). info["ok"] = False quando a
# consulta parou por falha TRANSITÓRIA (rede, HTTP inesperado): quem chama
# não marca a consulta como concluída, e ela é refeita na próxima rodada.
# Falhas PERMANENTES do servidor (um post que sempre devolve 502) não
# impedem a conclusão: o post é pulado e anotado em info["lacunas"].

import time
from datetime import datetime

import pandas as pd
import requests

import configuracao as cfg
import transporte
from extracao import extrairGlobo, extrairWp
from transporte import buscarGlobo, conta, itensDaResposta
from utilitarios import casaTermo, log

# %% Motor globo

def varrerGlobo(consulta, veiculo, tenant, ini, fim, size=100, soMaterias=True, ordenada=True):
    """`ordenada=False` desliga a parada antecipada ("80% da página já é anterior
    a `ini`"), que só vale quando a busca vem da mais recente para a mais antiga
    — não é o caso do G1."""
    registros, frm, parar, truncou, ultima, ok = [], 0, False, False, None, True
    while frm < cfg.TETO_FROM and not parar:
        st, js = buscarGlobo(consulta, frm, size, tenant, veiculo)
        if st == 400:              # passou do fundo da paginação
            truncou = True
            break
        if st != 200:              # rede caiu (None) ou HTTP inesperado
            ok = False
            break
        itens = itensDaResposta(js) if js else []
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
        if ordenada and antigas >= len(itens) * 0.8:
            parar = True
        frm += size
    if frm >= cfg.TETO_FROM and not parar:
        truncou = True
    return registros, {"chegou_em": ultima, "truncou": truncou, "ok": ok}

# %% Motor wordpress

def janelaWp(ano, ini, fim):
    """Fatia [a, b) do ano dentro da janela e se ela cobre o ano inteiro."""
    a = max(datetime(ano, 1, 1), ini)
    b = min(datetime(ano + 1, 1, 1), fim)
    return a, b, (a == datetime(ano, 1, 1) and b == datetime(ano + 1, 1, 1))


def varrerWp(termo, veiculo, base, ano, ini, fim):
    """WordPress filtra data no servidor: uma fatia por ano, sem teto."""
    registros = []
    a, b, _ = janelaWp(ano, ini, fim)
    info = {"total": 0, "ok": True, "lacunas": []}
    if a >= b:
        return registros, info
    params = {"search": termo, "after": a.isoformat(), "before": b.isoformat(),
              "orderby": "date", "order": "asc", "_fields": "link,title,excerpt,content,date"}

    def processar(posts):
        for p in posts:
            reg = extrairWp(p, veiculo, termo)
            if casaTermo(reg["titulo"], reg["subtitulo"], reg["p1"]):
                registros.append(reg)

    pagina = 1
    while True:
        try:
            r = _getWp(base, veiculo, dict(params, per_page=100, page=pagina))
        except requests.exceptions.RetryError:
            # Uma matéria que quebra o servidor derruba a página inteira com
            # 502 (visto na Exame, "ata do Copom" 2012, página 3). Refaz a
            # página em pedaços menores e pula só o que continuar falhando.
            posts, acabou, lacunas = _paginaEmPedacos(base, veiculo, params, pagina)
            info["lacunas"] += lacunas
            processar(posts)
            if acabou:
                break
            pagina += 1
            continue
        if pagina == 1:
            info["total"] = r.headers.get("X-WP-Total")
        if r.status_code == 400 and pagina > 1:   # pediu a página depois da última
            break
        if r.status_code != 200:
            info["ok"] = False
            break
        posts = r.json()
        if not posts:
            break
        processar(posts)
        if len(posts) < 100:
            break
        pagina += 1
    return registros, info


def _getWp(base, veiculo, params):
    r = transporte.sessaoAtual().get(f"{base}/wp-json/wp/v2/posts", timeout=cfg.TIMEOUT, params=params)
    conta(veiculo)
    time.sleep(cfg.PAUSA)
    return r


def _paginaEmPedacos(base, veiculo, params, pagina, pedaco=10, max_falhas_seguidas=3):
    """Os mesmos 100 posts da `pagina`, em páginas de `pedaco`; um pedaço que
    falhe é refeito post a post, e o post que ainda falhar é pulado.

    Devolve (posts, acabou, lacunas). `acabou` = a fatia terminou (os dados
    acabaram, ou `max_falhas_seguidas` posts seguidos falharam: visto na Exame,
    em que a partir de certa posição TODA requisição falha). Um post pulado
    não encerra a fatia: a contagem é por posição tentada, não por post
    devolvido."""
    posts, lacunas, falhas = [], [], 0
    rotulo = f"'{params['search']}' {params['after'][:10]}"
    primeiro = (pagina - 1) * 100 // pedaco + 1
    for sub in range(primeiro, primeiro + 100 // pedaco):
        try:
            r = _getWp(base, veiculo, dict(params, per_page=pedaco, page=sub))
        except requests.exceptions.RetryError:
            for um in range((sub - 1) * pedaco + 1, sub * pedaco + 1):
                try:
                    r1 = _getWp(base, veiculo, dict(params, per_page=1, page=um))
                except requests.exceptions.RetryError:
                    falhas += 1
                    lacunas.append(f"{veiculo}|{rotulo}|posição {um}")
                    log(f"    {veiculo}: post na posição {um} de {rotulo} falha no servidor — pulado")
                    if falhas >= max_falhas_seguidas:
                        lacunas.append(f"{veiculo}|{rotulo}|INCOMPLETA a partir da posição {um - falhas + 1}")
                        log(f"    {veiculo}: {falhas} falhas seguidas — fatia {rotulo} INCOMPLETA "
                            f"a partir da posição {um - falhas + 1}")
                        return posts, True, lacunas
                    continue
                falhas = 0
                um_post = r1.json() if r1.status_code == 200 else []
                if not um_post:                      # passou do último post
                    return posts, True, lacunas
                posts += um_post
            continue
        lote = r.json() if r.status_code == 200 else []
        posts += lote
        if len(lote) < pedaco:                       # os dados acabaram
            return posts, True, lacunas
    return posts, False, lacunas

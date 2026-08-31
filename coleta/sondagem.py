# %% Sondagem — quem é Faixa A?

import time

import pandas as pd
import requests

import configuracao as cfg
import transporte
from transporte import buscarGlobo, conta, itensDaResposta, totalDeHits

# %% Faixa A

def sondarVeiculos(veiculos=None) -> pd.DataFrame:
    """Faixa A exige que a resposta traga corpo do texto na própria descoberta.
    Testa cada candidato e reporta. Só os aprovados entram na coleta."""
    veiculos = veiculos or cfg.VEICULOS
    linhas = []
    for nome, conf in veiculos.items():
        r = {"veiculo": nome, "motor": conf["motor"], "http": None,
             "itens": 0, "tem_corpo": False, "faixa_a": False, "obs": ""}
        try:
            if conf["motor"] == "globo":
                st, js = buscarGlobo("Copom", 0, 3, conf["tenant"], nome)
                itens = itensDaResposta(js) if st == 200 else []
                r["http"], r["itens"] = st, len(itens)
                if itens:
                    corpo = str(itens[0].get("body") or "")
                    r["tem_corpo"] = len(corpo) > 500
                    r["obs"] = f"body={len(corpo)} car."
            else:
                resp = transporte.sessaoAtual().get(
                    f'{conf["base"]}/wp-json/wp/v2/posts',
                    params={"per_page": 1, "search": "Copom",
                            "_fields": "link,title,excerpt,content,date"},
                    timeout=cfg.TIMEOUT)
                conta(nome)
                time.sleep(cfg.PAUSA)
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

    sondagem = pd.DataFrame(linhas)
    print(sondagem.to_string(index=False))
    aprovados = sondagem[sondagem["faixa_a"]]["veiculo"].tolist()
    print(f"\nFaixa A confirmada: {aprovados}")
    reprovados = sondagem[~sondagem["faixa_a"]]["veiculo"].tolist()
    if reprovados:
        print(f"Fora da coleta: {reprovados}")
    return sondagem

# %% Medição de consultas

def medirTermo(q, tenant, veiculo):
    """Quantos resultados a consulta tem e até que data a paginação alcança."""
    st, js = buscarGlobo(q, 0, 1, tenant, veiculo)
    total = totalDeHits(js) if st == 200 else None
    if not isinstance(total, int) or total == 0:
        return total, None
    if total < cfg.TETO_FROM:
        return total, None
    st2, js2 = buscarGlobo(q, cfg.TETO_FROM - 100, 10, tenant, veiculo)
    itens = itensDaResposta(js2) if st2 == 200 else []
    if not itens:
        return total, None
    d = pd.to_datetime(itens[-1].get("issued"), errors="coerce", utc=True)
    return total, (d.tz_convert("America/Sao_Paulo").tz_localize(None)
                   if pd.notna(d) else None)


def testarConjuncao(tenant="valor", veiculo="Valor", a="Copom", b="Tombini"):
    """A busca combina palavras com E? Se não, subdividir não reduz o conjunto."""
    ta, _ = medirTermo(a, tenant, veiculo)
    tb, _ = medirTermo(b, tenant, veiculo)
    tab, _ = medirTermo(f"{a} {b}", tenant, veiculo)
    print(f"  {a!r}={ta} | {b!r}={tb} | {a + ' ' + b!r}={tab}")
    if not all(isinstance(x, int) for x in (ta, tb, tab)):
        print("  não foi possível medir")
        return None
    ok = tab < min(ta, tb)
    print("  -> conjunção (E): subdividir funciona" if ok else
          "  -> NÃO reduz: subdividir não vai adiantar")
    return ok

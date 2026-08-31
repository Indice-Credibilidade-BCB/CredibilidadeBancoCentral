# -*- coding: utf-8 -*-
"""Adaptador coleta -> schema do índice.

Converte a base consolidada da coleta (`dados/noticias.csv`, saída de
`consolidar()` em coleta/pipeline.py, ou um .xlsx exportado dela) no schema exigido por
`schema.validate`. Validado contra `noticias_2016_2017.xlsx` (971 itens,
Valor + Poder360) — ver docs/TESTE_INICIAL_corpus_2016_2017.md.

Decisões embutidas:
  - `item_id` = sha1 da URL normalizada. A busca da Globo devolve um
    REDIRECIONADOR (`measures.globo.com/v1/click?...&u=<url real>`) cujos
    parâmetros incluem o termo de busca (`q`, `qid`, `rid`, `ts`): a mesma
    matéria achada por "Tombini" e por "Copom" chega com URLs diferentes.
    Por isso desembrulhamos `u=` ANTES de normalizar. Sem isso: normalizar
    removendo a query colapsa TODO o Valor num único id (o path é
    idêntico), e não normalizar deixa passar duplicata. Com o desembrulho,
    os 971 itens de 2016-17 viram 915 artigos distintos (56 duplicatas
    reais recuperadas). Ver docs/TESTE_INICIAL_corpus_2016_2017.md.
  - `subtitulo` -> `lead`. Ausente no Valor (a busca da Globo não devolve),
    presente no Poder360. `build_user_msg` já tolera lead vazio.
  - `p1` -> `paragrafo_1`. NÃO usamos a coluna `texto_llm` da coleta: ela
    já vem formatada e sem data, o que impede o date-swap do teste T2.
    O prompt monta a mensagem por conta própria.
  - `n_replicacoes`/`replicada` da coleta são preservadas quando existem
    (detecção de wire feita lá, com mais contexto); `schema.dedup` roda
    de qualquer forma como rede de segurança.
  - `tipo_veiculo` vem de `config.veiculos_tipo`, default `imprensa`.

Uso:
    python corpus/from_coleta.py                    # usa paths do config
    python corpus/from_coleta.py --entrada arquivo.xlsx --saida x.parquet
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import re
import sys
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import schema  # noqa: E402

# Colunas da coleta que vale a pena carregar adiante como metadados.
EXTRAS = ["secao", "especie", "origem", "consulta", "n_paragrafos",
          "n_replicacoes", "replicada"]


def _cfg() -> dict:
    return yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))


def desembrulhar_url(u: str) -> str:
    """Extrai a URL real de dentro de um redirecionador de busca.

    A busca da Globo entrega measures.globo.com/v1/click?...&u=<url real>.
    O path é o mesmo para todas as matérias, então normalizar sem
    desembrulhar destruiria o corpus inteiro do Valor.
    """
    u = str(u)
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


def normalizar_url(u: str) -> str:
    return re.sub(r"[?#].*$", "", desembrulhar_url(u)).rstrip("/").lower()


def item_id_de_url(u: str) -> str:
    return "n" + hashlib.sha1(normalizar_url(u).encode()).hexdigest()[:10]


def ler(entrada: pathlib.Path) -> pd.DataFrame:
    if entrada.suffix in (".xlsx", ".xlsm"):
        return pd.read_excel(entrada)
    if entrada.suffix == ".parquet":
        return pd.read_parquet(entrada)
    return pd.read_csv(entrada)


def converter(raw: pd.DataFrame, veiculos_tipo: dict | None = None) -> pd.DataFrame:
    veiculos_tipo = veiculos_tipo or {}
    faltando = [c for c in ("veiculo", "url", "data", "titulo", "p1")
                if c not in raw.columns]
    if faltando:
        raise ValueError(f"Base da coleta sem colunas esperadas: {faltando}")

    data = pd.to_datetime(raw["data"], errors="coerce", utc=True, format="mixed")
    sem_data = int(data.isna().sum())

    out = pd.DataFrame({
        "item_id": raw["url"].map(item_id_de_url),
        "data_publicacao": data.dt.tz_convert("America/Sao_Paulo").dt.strftime("%Y-%m-%d"),
        "veiculo": raw["veiculo"].astype(str).str.strip(),
        "titulo": raw["titulo"].astype(str).str.strip(),
        "lead": raw.get("subtitulo", pd.Series("", index=raw.index)).fillna("").astype(str).str.strip(),
        "paragrafo_1": raw["p1"].fillna("").astype(str).str.strip(),
        # fonte_ref = URL real do artigo: o link de tracking expira e não
        # serve para citar a fonte no paper nem para reauditar o item.
        "fonte_ref": raw["url"].map(desembrulhar_url),
    })
    out["tipo_veiculo"] = out["veiculo"].map(veiculos_tipo).fillna("imprensa")
    for c in EXTRAS:
        if c in raw.columns:
            out[c] = raw[c]

    n0 = len(out)
    out = out[data.notna().to_numpy()]
    # Mesma URL coletada por pessoas/consultas diferentes: fica uma.
    out = out.drop_duplicates(subset="item_id")
    # Título vazio quebraria o hash de dedup/wire (schema.validate recusaria).
    titulo_vazio = out["titulo"].isin(["", "nan", "None"])
    out = out[~titulo_vazio]

    print(f"entrada: {n0} linhas | sem data: {sem_data} | "
          f"url repetida: {n0 - sem_data - len(out) - int(titulo_vazio.sum())} | "
          f"título vazio: {int(titulo_vazio.sum())} | saída: {len(out)}")
    return out.reset_index(drop=True)


def construir(entrada: pathlib.Path, saida: pathlib.Path,
              veiculos_tipo: dict | None = None) -> pd.DataFrame:
    df = converter(ler(entrada), veiculos_tipo)
    df = schema.dedup(schema.validate(df))
    saida.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(saida, index=False)
    print(f"corpus: {len(df)} itens -> {saida}")
    return df


if __name__ == "__main__":
    cfg = _cfg()
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", default=cfg["paths"]["corpus_coleta"])
    ap.add_argument("--saida", default=cfg["paths"]["corpus"])
    a = ap.parse_args()
    construir((ROOT / a.entrada).resolve(), (ROOT / a.saida).resolve(),
              cfg.get("veiculos_tipo"))

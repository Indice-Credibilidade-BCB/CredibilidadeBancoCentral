# %% Armazenamento — arquivos brutos e registro de consultas concluídas

import json
import os

import configuracao as cfg
from utilitarios import slug

# %% Caminhos

def caminhoBruto(veiculo: str) -> str:
    """Um arquivo por veículo POR PESSOA — dois colaboradores nunca escrevem
    no mesmo arquivo, então o git não tem o que conflitar."""
    os.makedirs(cfg.PASTA_BRUTO, exist_ok=True)
    return os.path.join(cfg.PASTA_BRUTO,
                        f"{slug(veiculo)}__{slug(cfg.COLABORADOR)}.jsonl")


def arquivoFeitas(colaborador=None) -> str:
    os.makedirs(cfg.PASTA_LEDGER, exist_ok=True)
    return os.path.join(cfg.PASTA_LEDGER,
                        f"{slug(colaborador or cfg.COLABORADOR)}.txt")

# %% Registro compartilhado

def carregarFeitas() -> set:
    """Lê o registro de TODOS os colaboradores: se seu amigo já varreu
    'Copom Tombini' no Valor, você não refaz."""
    feitas = set()
    if os.path.isdir(cfg.PASTA_LEDGER):
        for nome in os.listdir(cfg.PASTA_LEDGER):
            if nome.endswith(".txt"):
                with open(os.path.join(cfg.PASTA_LEDGER, nome),
                          encoding="utf-8") as f:
                    feitas |= {l.strip() for l in f if l.strip()}
    return feitas


def marcarFeita(chave: str) -> None:
    with open(arquivoFeitas(), "a", encoding="utf-8") as f:
        f.write(chave + "\n")
        f.flush()
        os.fsync(f.fileno())

# %% Gravação

def gravar(veiculo: str, registros) -> None:
    if not registros:
        return
    with open(caminhoBruto(veiculo), "a", encoding="utf-8") as f:
        for r in registros:
            r = dict(r, colaborador=cfg.COLABORADOR)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def prepararPastas() -> None:
    """Cria as pastas de dados com .gitkeep — rode uma vez, antes do 1º push."""
    for p in (cfg.PASTA_BRUTO, cfg.PASTA_LEDGER, cfg.PASTA_PLANOS):
        os.makedirs(p, exist_ok=True)
        guarda = os.path.join(p, ".gitkeep")
        if not os.path.exists(guarda):
            open(guarda, "w").close()
        print(f"  pronto: {os.path.relpath(p, cfg.RAIZ)}")
    print(f"\nColaborador atual: {cfg.COLABORADOR!r}")
    print("Se não for o seu nome, use configuracao.definirColaborador('seunome').")

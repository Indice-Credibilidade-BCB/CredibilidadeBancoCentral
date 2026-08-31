# %% Sincronização com o repositório

import subprocess

import configuracao as cfg
from utilitarios import log

# %% Git

def _git(*args, checar=True):
    r = subprocess.run(["git", *args], capture_output=True, text=True,
                       cwd=cfg.RAIZ)
    if checar and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr.strip()[:300]}")
    return r


def gitDisponivel() -> bool:
    try:
        return _git("rev-parse", "--is-inside-work-tree",
                    checar=False).returncode == 0
    except FileNotFoundError:
        return False


def gitPuxar() -> bool:
    """Traz o progresso dos outros antes de começar."""
    if not (cfg.SINCRONIZAR_GIT and gitDisponivel()):
        return False
    r = _git("pull", "--rebase", "--autostash", checar=False)
    if r.returncode != 0:
        log(f"  git pull falhou: {r.stderr.strip()[:200]}")
        return False
    log("  repositório atualizado")
    return True


def gitEnviar(mensagem: str = "coleta") -> bool:
    """Publica o que esta pessoa coletou. Como cada um só escreve nos próprios
    arquivos, o rebase resolve sozinho; ainda assim tenta de novo em caso de
    corrida com outro push."""
    if not (cfg.SINCRONIZAR_GIT and gitDisponivel()):
        return False
    _git("add", cfg.PASTA, checar=False)
    if not _git("diff", "--cached", "--quiet", checar=False).returncode:
        return False                                   # nada mudou
    _git("commit", "-m", f"{mensagem} [{cfg.COLABORADOR}]", checar=False)
    for tentativa in range(3):
        if _git("push", checar=False).returncode == 0:
            log(f"  push ok ({mensagem})")
            return True
        log(f"  push rejeitado; rebase e nova tentativa [{tentativa + 1}/3]")
        if _git("pull", "--rebase", "--autostash", checar=False).returncode != 0:
            log("  rebase falhou — resolva à mão e rode de novo")
            return False
    return False

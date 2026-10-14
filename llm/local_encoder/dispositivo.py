# -*- coding: utf-8 -*-
"""Escolha de dispositivo (GPU/CPU) e precisão mista para o braço local.

Com placa NVIDIA e PyTorch com CUDA, treino e inferência rodam na GPU em
float16 automático (``torch.autocast``) — na RTX 3070 Ti isso é dezenas de
vezes mais rápido que a CPU. Sem CUDA, tudo cai para CPU em float32, sem
mudar o resultado além de arredondamento.

Verificar a instalação::

    python -c "import torch; print(torch.cuda.is_available())"

Se imprimir ``False`` numa máquina com placa NVIDIA, o PyTorch instalado é a
variante só-CPU; instalar a variante CUDA (ex.: ``pip install --force-reinstall
--no-deps torch==2.5.1+cu124 --index-url https://download.pytorch.org/whl/cu124``).
"""
from __future__ import annotations

import contextlib


def escolher(preferencia: str = "auto"):
    """``auto`` -> cuda se disponível, senão cpu. ``cuda`` sem GPU levanta erro claro."""
    import torch

    if preferencia == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if preferencia == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("--dispositivo cuda pedido, mas torch.cuda.is_available() é False "
                           "(PyTorch só-CPU ou driver ausente; ver docstring de dispositivo.py)")
    return torch.device(preferencia)


def autocast(dispositivo, fp16: bool = True):
    """Contexto de precisão mista: float16 na GPU; no-op na CPU."""
    import torch

    if fp16 and dispositivo.type == "cuda":
        return torch.autocast(device_type="cuda", dtype=torch.float16)
    return contextlib.nullcontext()


def descrever(dispositivo) -> str:
    import torch

    if dispositivo.type == "cuda":
        p = torch.cuda.get_device_properties(dispositivo)
        return f"GPU {p.name} ({p.total_memory / 2**30:.1f} GB)"
    return f"CPU ({torch.get_num_threads()} threads)"

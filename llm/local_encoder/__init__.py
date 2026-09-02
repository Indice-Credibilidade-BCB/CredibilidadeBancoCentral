# -*- coding: utf-8 -*-
"""Braço local (D7/D14): BERTimbau com cutoff de pré-treino conhecido.

Ver docstring de `model.py` para o porquê (cutoff ~2019 do brWaC é
estruturalmente mais à prova de vazamento que qualquer API de fronteira) e
de `dataset.py` para as mitigações de anti-contaminação da destilação.

Este subpacote depende de torch e transformers, que NÃO entram no
requirements.txt padrão de `llm/` (são pesados e só quem for treinar o braço
local precisa deles). Ver requirements.txt: linhas comentadas no fim.
"""

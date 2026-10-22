# Etapa 4 — Kalman e encompassing (saída automática)

Painel: 2001-11 a 2026-10 (300 meses). Amostra do filtro: 2001-12 a 2026-10 (299 meses).

## Bloco 2 — parâmetros por máxima verossimilhança

- **logistico**: σ_η = 0.3862, σ_ν = 0.4376, loglik = -211.53, otimizador ok = True
- **linear**: σ_η = 0.2749, σ_ν = 0.1218, loglik = -179.20, otimizador ok = True

Identificação fraca (|π*−π_{t−1}| < 1.0 p.p.): 28.1% dos meses; ganho médio 0.520 (fraco) vs 0.878 (forte); EP médio 0.155 vs 0.086.

|                    |   mean |   std |    min |   max |
|:-------------------|-------:|------:|-------:|------:|
| c_kf_filtrado      |  0.563 | 0.279 |  0.028 | 0.952 |
| c_kf_suavizado     |  0.548 | 0.239 |  0.069 | 0.9   |
| c_kf_suavizado_lin |  0.536 | 0.326 | -0.254 | 1.175 |

## Rivais disponíveis

- `dm2007` (Focus (fórmula)): 299 meses
- `dm2009` (Focus (fórmula c/ banda)): 299 meses
- `disp_focus_neg` (Focus (dispersão)): 299 meses
- `breakeven_neg` (mercado): 257 meses
- `cds_neg` (mercado): 91 meses
- `embi_neg` (mercado): 202 meses
- `inclinacao` (mercado): 300 meses
- ⚠ rival institucional (DEG) pulado: dados/macro/deg_brasil.csv não existe. Preencher com 'ano,valor' a partir de Dincer-Eichengreen-Geraats (2022).

Correlação do latente com cada rival:

|                |   corr |
|:---------------|-------:|
| dm2007         |  0.396 |
| dm2009         |  0.17  |
| disp_focus_neg |  0.139 |
| breakeven_neg  |  0.286 |
| cds_neg        | -0.214 |
| embi_neg       | -0.498 |
| inclinacao     |  0.009 |

## Bloco 3 — encompassing (nível, padronizado, HAC)

| variante_llm     | rival          |   n |     b1 |   t_b1 |   p_b1 |      b2 |    t_b2 |    p_b2 |    r2 |
|:-----------------|:---------------|----:|-------:|-------:|-------:|--------:|--------:|--------:|------:|
| c_llm            | nenhum         | 189 |  0.381 |  3.374 |  0.001 | nan     | nan     | nan     | 0.145 |
| c_llm            | dm2007         | 189 |  0.054 |  0.379 |  0.705 |   0.479 |   2.765 |   0.006 | 0.268 |
| c_llm            | dm2009         | 189 |  0.393 |  3.261 |  0.001 |  -0.025 |  -0.178 |   0.858 | 0.146 |
| c_llm            | disp_focus_neg | 189 |  0.497 |  4.586 |  0     |  -0.203 |  -1.823 |   0.068 | 0.173 |
| c_llm            | breakeven_neg  | 189 |  0.215 |  1.151 |  0.25  |   0.225 |   0.997 |   0.319 | 0.168 |
| c_llm            | cds_neg        |  90 |  0.358 |  2.435 |  0.015 |  -0.28  |  -2.099 |   0.036 | 0.163 |
| c_llm            | embi_neg       | 189 |  0.455 |  5.312 |  0     |  -0.565 |  -5.228 |   0     | 0.46  |
| c_llm            | inclinacao     | 189 |  0.348 |  2.961 |  0.003 |   0.188 |   1.337 |   0.181 | 0.18  |
| c_llm            | todos          |  90 | -0.083 | -0.786 |  0.432 | nan     | nan     | nan     | 0.711 |
| c_llm            | todos_longos   | 189 | -0.058 | -0.584 |  0.559 | nan     | nan     | nan     | 0.726 |
| c_llm_jm3        | nenhum         | 189 |  0.419 |  3.578 |  0     | nan     | nan     | nan     | 0.175 |
| c_llm_jm3        | dm2007         | 189 |  0.064 |  0.368 |  0.713 |   0.468 |   2.422 |   0.015 | 0.268 |
| c_llm_jm3        | dm2009         | 189 |  0.464 |  3.565 |  0     |  -0.089 |  -0.62  |   0.535 | 0.181 |
| c_llm_jm3        | disp_focus_neg | 189 |  0.61  |  4.813 |  0     |  -0.303 |  -2.484 |   0.013 | 0.231 |
| c_llm_jm3        | breakeven_neg  | 189 |  0.307 |  1.34  |  0.18  |   0.141 |   0.56  |   0.576 | 0.183 |
| c_llm_jm3        | cds_neg        |  90 |  0.451 |  3.155 |  0.002 |  -0.303 |  -2.181 |   0.029 | 0.234 |
| c_llm_jm3        | embi_neg       | 189 |  0.494 |  5.578 |  0     |  -0.571 |  -5.36  |   0     | 0.496 |
| c_llm_jm3        | inclinacao     | 189 |  0.379 |  2.938 |  0.003 |   0.146 |   0.99  |   0.322 | 0.195 |
| c_llm_jm3        | todos          |  90 | -0.066 | -0.471 |  0.638 | nan     | nan     | nan     | 0.71  |
| c_llm_jm3        | todos_longos   | 189 | -0.092 | -0.716 |  0.474 | nan     | nan     | nan     | 0.727 |
| c_llm_gemini     | nenhum         | 189 |  0.457 |  4.095 |  0     | nan     | nan     | nan     | 0.209 |
| c_llm_gemini     | dm2007         | 189 |  0.149 |  0.97  |  0.332 |   0.402 |   2.159 |   0.031 | 0.276 |
| c_llm_gemini     | dm2009         | 189 |  0.476 |  4.109 |  0     |  -0.046 |  -0.315 |   0.753 | 0.21  |
| c_llm_gemini     | disp_focus_neg | 189 |  0.622 |  5.9   |  0     |  -0.283 |  -2.528 |   0.011 | 0.261 |
| c_llm_gemini     | breakeven_neg  | 189 |  0.402 |  1.993 |  0.046 |   0.07  |   0.309 |   0.757 | 0.21  |
| c_llm_gemini     | cds_neg        |  90 |  0.406 |  2.74  |  0.006 |  -0.325 |  -2.417 |   0.016 | 0.19  |
| c_llm_gemini     | embi_neg       | 189 |  0.533 |  7.051 |  0     |  -0.577 |  -5.575 |   0     | 0.535 |
| c_llm_gemini     | inclinacao     | 189 |  0.423 |  3.513 |  0     |   0.162 |   1.17  |   0.242 | 0.234 |
| c_llm_gemini     | todos          |  90 | -0.114 | -0.976 |  0.329 | nan     | nan     | nan     | 0.712 |
| c_llm_gemini     | todos_longos   | 189 | -0.067 | -0.601 |  0.548 | nan     | nan     | nan     | 0.726 |
| c_llm_gemjm3     | nenhum         | 189 |  0.473 |  4.15  |  0     | nan     | nan     | nan     | 0.224 |
| c_llm_gemjm3     | dm2007         | 189 |  0.16  |  0.929 |  0.353 |   0.387 |   1.92  |   0.055 | 0.275 |
| c_llm_gemjm3     | dm2009         | 189 |  0.506 |  4.23  |  0     |  -0.076 |  -0.508 |   0.612 | 0.228 |
| c_llm_gemjm3     | disp_focus_neg | 189 |  0.685 |  5.806 |  0     |  -0.343 |  -2.894 |   0.004 | 0.296 |
| c_llm_gemjm3     | breakeven_neg  | 189 |  0.466 |  2.18  |  0.029 |   0.009 |   0.038 |   0.969 | 0.224 |
| c_llm_gemjm3     | cds_neg        |  90 |  0.479 |  3.351 |  0.001 |  -0.338 |  -2.343 |   0.019 | 0.251 |
| c_llm_gemjm3     | embi_neg       | 189 |  0.55  |  6.929 |  0     |  -0.579 |  -5.653 |   0     | 0.553 |
| c_llm_gemjm3     | inclinacao     | 189 |  0.437 |  3.405 |  0.001 |   0.119 |   0.817 |   0.414 | 0.236 |
| c_llm_gemjm3     | todos          |  90 | -0.117 | -0.859 |  0.39  | nan     | nan     | nan     | 0.711 |
| c_llm_gemjm3     | todos_longos   | 189 | -0.112 | -0.864 |  0.387 | nan     | nan     | nan     | 0.728 |
| c_llm_dupla      | nenhum         | 178 |  0.266 |  2.495 |  0.013 | nan     | nan     | nan     | 0.071 |
| c_llm_dupla      | dm2007         | 178 |  0.022 |  0.224 |  0.823 |   0.498 |   3.477 |   0.001 | 0.259 |
| c_llm_dupla      | dm2009         | 178 |  0.246 |  2.354 |  0.019 |   0.057 |   0.377 |   0.706 | 0.074 |
| c_llm_dupla      | disp_focus_neg | 178 |  0.301 |  3.22  |  0.001 |  -0.074 |  -0.574 |   0.566 | 0.075 |
| c_llm_dupla      | breakeven_neg  | 178 |  0.086 |  0.779 |  0.436 |   0.32  |   1.768 |   0.077 | 0.141 |
| c_llm_dupla      | cds_neg        |  87 |  0.238 |  1.594 |  0.111 |  -0.261 |  -1.956 |   0.05  | 0.095 |
| c_llm_dupla      | embi_neg       | 178 |  0.331 |  3.868 |  0     |  -0.542 |  -4.948 |   0     | 0.36  |
| c_llm_dupla      | inclinacao     | 178 |  0.244 |  2.332 |  0.02  |   0.264 |   1.959 |   0.05  | 0.14  |
| c_llm_dupla      | todos          |  87 | -0.01  | -0.115 |  0.908 | nan     | nan     | nan     | 0.711 |
| c_llm_dupla      | todos_longos   | 178 |  0.004 |  0.063 |  0.95  | nan     | nan     | nan     | 0.709 |
| c_llm_vmax_dupla | nenhum         | 178 |  0.266 |  2.495 |  0.013 | nan     | nan     | nan     | 0.071 |
| c_llm_vmax_dupla | dm2007         | 178 |  0.022 |  0.224 |  0.823 |   0.498 |   3.477 |   0.001 | 0.259 |
| c_llm_vmax_dupla | dm2009         | 178 |  0.246 |  2.354 |  0.019 |   0.057 |   0.377 |   0.706 | 0.074 |
| c_llm_vmax_dupla | disp_focus_neg | 178 |  0.301 |  3.22  |  0.001 |  -0.074 |  -0.574 |   0.566 | 0.075 |
| c_llm_vmax_dupla | breakeven_neg  | 178 |  0.086 |  0.779 |  0.436 |   0.32  |   1.768 |   0.077 | 0.141 |
| c_llm_vmax_dupla | cds_neg        |  87 |  0.238 |  1.594 |  0.111 |  -0.261 |  -1.956 |   0.05  | 0.095 |
| c_llm_vmax_dupla | embi_neg       | 178 |  0.331 |  3.868 |  0     |  -0.542 |  -4.948 |   0     | 0.36  |
| c_llm_vmax_dupla | inclinacao     | 178 |  0.244 |  2.332 |  0.02  |   0.264 |   1.959 |   0.05  | 0.14  |
| c_llm_vmax_dupla | todos          |  87 | -0.01  | -0.115 |  0.908 | nan     | nan     | nan     | 0.711 |
| c_llm_vmax_dupla | todos_longos   | 178 |  0.004 |  0.063 |  0.95  | nan     | nan     | nan     | 0.709 |
| c_llm_vmin_dupla | nenhum         | 180 |  0.087 |  0.92  |  0.358 | nan     | nan     | nan     | 0.008 |
| c_llm_vmin_dupla | dm2007         | 180 | -0.075 | -0.939 |  0.348 |   0.537 |   3.951 |   0     | 0.27  |
| c_llm_vmin_dupla | dm2009         | 180 |  0.05  |  0.532 |  0.595 |   0.127 |   0.864 |   0.388 | 0.022 |
| c_llm_vmin_dupla | disp_focus_neg | 180 |  0.065 |  0.743 |  0.458 |   0.058 |   0.403 |   0.687 | 0.01  |
| c_llm_vmin_dupla | breakeven_neg  | 180 | -0.077 | -0.925 |  0.355 |   0.408 |   2.412 |   0.016 | 0.147 |
| c_llm_vmin_dupla | cds_neg        |  89 |  0.051 |  0.38  |  0.704 |  -0.215 |  -1.455 |   0.146 | 0.045 |
| c_llm_vmin_dupla | embi_neg       | 180 |  0.167 |  2.03  |  0.042 |  -0.532 |  -4.543 |   0     | 0.284 |
| c_llm_vmin_dupla | inclinacao     | 180 |  0.097 |  1.082 |  0.279 |   0.267 |   1.936 |   0.053 | 0.079 |
| c_llm_vmin_dupla | todos          |  89 | -0.022 | -0.363 |  0.717 | nan     | nan     | nan     | 0.715 |
| c_llm_vmin_dupla | todos_longos   | 180 | -0.024 | -0.546 |  0.585 | nan     | nan     | nan     | 0.718 |

### Robustez em primeiras diferenças

| variante_llm     | rival          |   n |     b1 |   t_b1 |   p_b1 |      b2 |    t_b2 |    p_b2 |    r2 |
|:-----------------|:---------------|----:|-------:|-------:|-------:|--------:|--------:|--------:|------:|
| c_llm            | nenhum         | 188 |  0.045 |  0.646 |  0.519 | nan     | nan     | nan     | 0.002 |
| c_llm            | dm2007         | 188 | -0.007 | -0.123 |  0.902 |   0.456 |   6.941 |   0     | 0.207 |
| c_llm            | dm2009         | 188 |  0.043 |  0.716 |  0.474 |   0.266 |   5.592 |   0     | 0.073 |
| c_llm            | disp_focus_neg | 188 |  0.022 |  0.317 |  0.752 |   0.116 |   0.968 |   0.333 | 0.015 |
| c_llm            | breakeven_neg  | 188 | -0.015 | -0.24  |  0.81  |   0.214 |   3.168 |   0.002 | 0.044 |
| c_llm            | cds_neg        |  89 |  0.071 |  0.572 |  0.568 |   0.128 |   1.531 |   0.126 | 0.025 |
| c_llm            | embi_neg       | 188 |  0.044 |  0.633 |  0.527 |   0.019 |   0.271 |   0.786 | 0.002 |
| c_llm            | inclinacao     | 188 |  0.014 |  0.213 |  0.831 |  -0.133 |  -1.684 |   0.092 | 0.019 |
| c_llm            | todos          |  89 |  0.039 |  0.401 |  0.689 | nan     | nan     | nan     | 0.226 |
| c_llm            | todos_longos   | 188 | -0.045 | -0.801 |  0.423 | nan     | nan     | nan     | 0.238 |
| c_llm_jm3        | nenhum         | 188 |  0.03  |  0.26  |  0.795 | nan     | nan     | nan     | 0.001 |
| c_llm_jm3        | dm2007         | 188 | -0.076 | -0.804 |  0.421 |   0.472 |   6.758 |   0     | 0.212 |
| c_llm_jm3        | dm2009         | 188 | -0.028 | -0.272 |  0.786 |   0.272 |   5.082 |   0     | 0.072 |
| c_llm_jm3        | disp_focus_neg | 188 | -0.001 | -0.007 |  0.995 |   0.121 |   0.993 |   0.321 | 0.015 |
| c_llm_jm3        | breakeven_neg  | 188 | -0.051 | -0.451 |  0.652 |   0.227 |   3.233 |   0.001 | 0.046 |
| c_llm_jm3        | cds_neg        |  89 |  0.174 |  1.149 |  0.25  |   0.118 |   1.38  |   0.168 | 0.049 |
| c_llm_jm3        | embi_neg       | 188 |  0.027 |  0.236 |  0.813 |   0.018 |   0.26  |   0.795 | 0.001 |
| c_llm_jm3        | inclinacao     | 188 | -0.01  | -0.084 |  0.933 |  -0.139 |  -1.6   |   0.11  | 0.019 |
| c_llm_jm3        | todos          |  89 |  0.084 |  0.638 |  0.523 | nan     | nan     | nan     | 0.23  |
| c_llm_jm3        | todos_longos   | 188 | -0.116 | -1.218 |  0.223 | nan     | nan     | nan     | 0.247 |
| c_llm_gemini     | nenhum         | 188 |  0.028 |  0.375 |  0.708 | nan     | nan     | nan     | 0.001 |
| c_llm_gemini     | dm2007         | 188 | -0.014 | -0.222 |  0.824 |   0.456 |   6.982 |   0     | 0.207 |
| c_llm_gemini     | dm2009         | 188 |  0.026 |  0.406 |  0.685 |   0.266 |   5.536 |   0     | 0.072 |
| c_llm_gemini     | disp_focus_neg | 188 |  0.006 |  0.084 |  0.933 |   0.12  |   1.004 |   0.315 | 0.015 |
| c_llm_gemini     | breakeven_neg  | 188 | -0.05  | -0.696 |  0.486 |   0.226 |   3.351 |   0.001 | 0.046 |
| c_llm_gemini     | cds_neg        |  89 |  0.005 |  0.035 |  0.972 |   0.139 |   1.664 |   0.096 | 0.02  |
| c_llm_gemini     | embi_neg       | 188 |  0.025 |  0.338 |  0.736 |   0.018 |   0.257 |   0.797 | 0.001 |
| c_llm_gemini     | inclinacao     | 188 | -0.018 | -0.238 |  0.812 |  -0.142 |  -1.796 |   0.072 | 0.019 |
| c_llm_gemini     | todos          |  89 | -0.016 | -0.143 |  0.886 | nan     | nan     | nan     | 0.225 |
| c_llm_gemini     | todos_longos   | 188 | -0.056 | -0.915 |  0.36  | nan     | nan     | nan     | 0.239 |
| c_llm_gemjm3     | nenhum         | 188 |  0.016 |  0.152 |  0.879 | nan     | nan     | nan     | 0     |
| c_llm_gemjm3     | dm2007         | 188 | -0.109 | -1.204 |  0.229 |   0.483 |   6.97  |   0     | 0.218 |
| c_llm_gemjm3     | dm2009         | 188 | -0.048 | -0.504 |  0.614 |   0.277 |   5.384 |   0     | 0.073 |
| c_llm_gemjm3     | disp_focus_neg | 188 | -0.016 | -0.16  |  0.873 |   0.125 |   1.064 |   0.287 | 0.015 |
| c_llm_gemjm3     | breakeven_neg  | 188 | -0.065 | -0.631 |  0.528 |   0.232 |   3.192 |   0.001 | 0.048 |
| c_llm_gemjm3     | cds_neg        |  89 |  0.105 |  0.705 |  0.481 |   0.12  |   1.44  |   0.15  | 0.03  |
| c_llm_gemjm3     | embi_neg       | 188 |  0.012 |  0.114 |  0.909 |   0.02  |   0.293 |   0.769 | 0.001 |
| c_llm_gemjm3     | inclinacao     | 188 | -0.02  | -0.188 |  0.851 |  -0.141 |  -1.645 |   0.1   | 0.019 |
| c_llm_gemjm3     | todos          |  89 | -0.001 | -0.008 |  0.994 | nan     | nan     | nan     | 0.225 |
| c_llm_gemjm3     | todos_longos   | 188 | -0.137 | -1.543 |  0.123 | nan     | nan     | nan     | 0.252 |
| c_llm_dupla      | nenhum         | 167 |  0.041 |  0.701 |  0.483 | nan     | nan     | nan     | 0.002 |
| c_llm_dupla      | dm2007         | 167 |  0.043 |  0.987 |  0.324 |   0.447 |   6.905 |   0     | 0.202 |
| c_llm_dupla      | dm2009         | 167 |  0.058 |  1.253 |  0.21  |   0.287 |   5.663 |   0     | 0.084 |
| c_llm_dupla      | disp_focus_neg | 167 |  0.027 |  0.471 |  0.638 |   0.1   |   0.771 |   0.441 | 0.011 |
| c_llm_dupla      | breakeven_neg  | 167 |  0.01  |  0.178 |  0.858 |   0.236 |   3.14  |   0.002 | 0.056 |
| c_llm_dupla      | cds_neg        |  84 | -0.052 | -0.488 |  0.625 |   0.16  |   1.937 |   0.053 | 0.026 |
| c_llm_dupla      | embi_neg       | 167 |  0.039 |  0.683 |  0.494 |   0.021 |   0.277 |   0.782 | 0.002 |
| c_llm_dupla      | inclinacao     | 167 |  0.015 |  0.272 |  0.786 |  -0.14  |  -1.568 |   0.117 | 0.021 |
| c_llm_dupla      | todos          |  84 | -0.018 | -0.265 |  0.791 | nan     | nan     | nan     | 0.238 |
| c_llm_dupla      | todos_longos   | 167 |  0.027 |  0.614 |  0.539 | nan     | nan     | nan     | 0.236 |
| c_llm_vmax_dupla | nenhum         | 167 |  0.041 |  0.701 |  0.483 | nan     | nan     | nan     | 0.002 |
| c_llm_vmax_dupla | dm2007         | 167 |  0.043 |  0.987 |  0.324 |   0.447 |   6.905 |   0     | 0.202 |
| c_llm_vmax_dupla | dm2009         | 167 |  0.058 |  1.253 |  0.21  |   0.287 |   5.663 |   0     | 0.084 |
| c_llm_vmax_dupla | disp_focus_neg | 167 |  0.027 |  0.471 |  0.638 |   0.1   |   0.771 |   0.441 | 0.011 |
| c_llm_vmax_dupla | breakeven_neg  | 167 |  0.01  |  0.178 |  0.858 |   0.236 |   3.14  |   0.002 | 0.056 |
| c_llm_vmax_dupla | cds_neg        |  84 | -0.052 | -0.488 |  0.625 |   0.16  |   1.937 |   0.053 | 0.026 |
| c_llm_vmax_dupla | embi_neg       | 167 |  0.039 |  0.683 |  0.494 |   0.021 |   0.277 |   0.782 | 0.002 |
| c_llm_vmax_dupla | inclinacao     | 167 |  0.015 |  0.272 |  0.786 |  -0.14  |  -1.568 |   0.117 | 0.021 |
| c_llm_vmax_dupla | todos          |  84 | -0.018 | -0.265 |  0.791 | nan     | nan     | nan     | 0.238 |
| c_llm_vmax_dupla | todos_longos   | 167 |  0.027 |  0.614 |  0.539 | nan     | nan     | nan     | 0.236 |
| c_llm_vmin_dupla | nenhum         | 170 |  0.007 |  0.151 |  0.88  | nan     | nan     | nan     | 0     |
| c_llm_vmin_dupla | dm2007         | 170 | -0.001 | -0.019 |  0.985 |   0.441 |   6.771 |   0     | 0.194 |
| c_llm_vmin_dupla | dm2009         | 170 |  0.004 |  0.083 |  0.934 |   0.282 |   5.507 |   0     | 0.079 |
| c_llm_vmin_dupla | disp_focus_neg | 170 | -0.009 | -0.175 |  0.861 |   0.106 |   0.829 |   0.407 | 0.011 |
| c_llm_vmin_dupla | breakeven_neg  | 170 | -0.01  | -0.227 |  0.82  |   0.227 |   2.916 |   0.004 | 0.051 |
| c_llm_vmin_dupla | cds_neg        |  88 |  0.003 |  0.042 |  0.966 |   0.14  |   1.62  |   0.105 | 0.02  |
| c_llm_vmin_dupla | embi_neg       | 170 |  0.007 |  0.152 |  0.88  |  -0.003 |  -0.033 |   0.974 | 0     |
| c_llm_vmin_dupla | inclinacao     | 170 | -0.006 | -0.134 |  0.893 |  -0.112 |  -1.334 |   0.182 | 0.012 |
| c_llm_vmin_dupla | todos          |  88 |  0.024 |  0.313 |  0.754 | nan     | nan     | nan     | 0.227 |
| c_llm_vmin_dupla | todos_longos   | 170 | -0.009 | -0.213 |  0.831 | nan     | nan     | nan     | 0.228 |

### Veredito por variante (nível, α = 5%)

| variante_llm     |   n_regressoes | b1_sig_sem_rival   |   n_rivais_testados |   n_rivais_sobrevive | sobrevive_a_todos   | sinal_b1_estavel   |   b1_min |   b1_max |
|:-----------------|---------------:|:-------------------|--------------------:|---------------------:|:--------------------|:-------------------|---------:|---------:|
| c_llm            |             10 | True               |                   9 |                    5 | False               | False              |   -0.083 |    0.497 |
| c_llm_dupla      |             10 | True               |                   9 |                    4 | False               | False              |   -0.01  |    0.331 |
| c_llm_gemini     |             10 | True               |                   9 |                    6 | False               | False              |   -0.114 |    0.622 |
| c_llm_gemjm3     |             10 | True               |                   9 |                    6 | False               | False              |   -0.117 |    0.685 |
| c_llm_jm3        |             10 | True               |                   9 |                    5 | False               | False              |   -0.092 |    0.61  |
| c_llm_vmax_dupla |             10 | True               |                   9 |                    4 | False               | False              |   -0.01  |    0.331 |
| c_llm_vmin_dupla |             10 | False              |                   9 |                    1 | False               | False              |   -0.077 |    0.167 |

### Banda de vazamento V-max × V-min (D12)

| rival          |   b1_vmax |   p_vmax |   b1_vmin |   p_vmin | mesma_conclusao   |
|:---------------|----------:|---------:|----------:|---------:|:------------------|
| nenhum         |     0.266 |    0.013 |     0.087 |    0.358 | False             |
| dm2007         |     0.022 |    0.823 |    -0.075 |    0.348 | False             |
| dm2009         |     0.246 |    0.019 |     0.05  |    0.595 | False             |
| disp_focus_neg |     0.301 |    0.001 |     0.065 |    0.458 | False             |
| breakeven_neg  |     0.086 |    0.436 |    -0.077 |    0.355 | False             |
| cds_neg        |     0.238 |    0.111 |     0.051 |    0.704 | True              |
| embi_neg       |     0.331 |    0     |     0.167 |    0.042 | True              |
| inclinacao     |     0.244 |    0.02  |     0.097 |    0.279 | False             |
| todos          |    -0.01  |    0.908 |    -0.022 |    0.717 | True              |
| todos_longos   |     0.004 |    0.95  |    -0.024 |    0.585 | False             |


> Leitura: o índice é validado se b1 segue significativo com cada rival; se V-max e V-min divergirem, o V-min manda (D12). Latente e rivais de Focus compartilham a fonte — as âncoras decisivas são institucional e de mercado.
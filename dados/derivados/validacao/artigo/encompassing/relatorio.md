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
| c_llm            | nenhum         | 189 |  0.398 |  3.635 |  0     | nan     | nan     | nan     | 0.158 |
| c_llm            | dm2007         | 189 |  0.1   |  0.779 |  0.436 |   0.45  |   2.774 |   0.006 | 0.272 |
| c_llm            | dm2009         | 189 |  0.412 |  3.635 |  0     |  -0.033 |  -0.235 |   0.815 | 0.159 |
| c_llm            | disp_focus_neg | 189 |  0.517 |  5.156 |  0     |  -0.211 |  -1.875 |   0.061 | 0.189 |
| c_llm            | breakeven_neg  | 189 |  0.252 |  1.593 |  0.111 |   0.205 |   1.01  |   0.313 | 0.179 |
| c_llm            | cds_neg        |  90 |  0.38  |  2.744 |  0.006 |  -0.289 |  -2.224 |   0.026 | 0.177 |
| c_llm            | embi_neg       | 189 |  0.47  |  5.906 |  0     |  -0.566 |  -5.519 |   0     | 0.473 |
| c_llm            | inclinacao     | 189 |  0.369 |  3.311 |  0.001 |   0.197 |   1.445 |   0.149 | 0.196 |
| c_llm            | todos          |  90 | -0.01  | -0.084 |  0.933 | nan     | nan     | nan     | 0.709 |
| c_llm            | todos_longos   | 189 |  0.022 |  0.255 |  0.799 | nan     | nan     | nan     | 0.725 |
| c_llm_jm3        | nenhum         | 189 |  0.431 |  3.735 |  0     | nan     | nan     | nan     | 0.186 |
| c_llm_jm3        | dm2007         | 189 |  0.107 |  0.662 |  0.508 |   0.437 |   2.376 |   0.018 | 0.272 |
| c_llm_jm3        | dm2009         | 189 |  0.485 |  3.861 |  0     |  -0.104 |  -0.73  |   0.465 | 0.194 |
| c_llm_jm3        | disp_focus_neg | 189 |  0.648 |  5.291 |  0     |  -0.337 |  -2.723 |   0.006 | 0.252 |
| c_llm_jm3        | breakeven_neg  | 189 |  0.335 |  1.536 |  0.124 |   0.123 |   0.508 |   0.612 | 0.192 |
| c_llm_jm3        | cds_neg        |  90 |  0.468 |  3.474 |  0.001 |  -0.312 |  -2.303 |   0.021 | 0.247 |
| c_llm_jm3        | embi_neg       | 189 |  0.499 |  5.88  |  0     |  -0.565 |  -5.508 |   0     | 0.501 |
| c_llm_jm3        | inclinacao     | 189 |  0.393 |  3.135 |  0.002 |   0.15  |   1.04  |   0.299 | 0.207 |
| c_llm_jm3        | todos          |  90 |  0.012 |  0.088 |  0.93  | nan     | nan     | nan     | 0.709 |
| c_llm_jm3        | todos_longos   | 189 | -0.022 | -0.177 |  0.859 | nan     | nan     | nan     | 0.725 |
| c_llm_gemini     | nenhum         | 189 |  0.477 |  4.38  |  0     | nan     | nan     | nan     | 0.228 |
| c_llm_gemini     | dm2007         | 189 |  0.199 |  1.355 |  0.175 |   0.364 |   1.994 |   0.046 | 0.283 |
| c_llm_gemini     | dm2009         | 189 |  0.502 |  4.501 |  0     |  -0.06  |  -0.404 |   0.686 | 0.231 |
| c_llm_gemini     | disp_focus_neg | 189 |  0.655 |  6.62  |  0     |  -0.303 |  -2.72  |   0.007 | 0.288 |
| c_llm_gemini     | breakeven_neg  | 189 |  0.458 |  2.369 |  0.018 |   0.025 |   0.113 |   0.91  | 0.228 |
| c_llm_gemini     | cds_neg        |  90 |  0.428 |  3.015 |  0.003 |  -0.332 |  -2.453 |   0.014 | 0.207 |
| c_llm_gemini     | embi_neg       | 189 |  0.547 |  7.565 |  0     |  -0.573 |  -5.692 |   0     | 0.551 |
| c_llm_gemini     | inclinacao     | 189 |  0.445 |  3.793 |  0     |   0.161 |   1.193 |   0.233 | 0.253 |
| c_llm_gemini     | todos          |  90 | -0.076 | -0.593 |  0.553 | nan     | nan     | nan     | 0.71  |
| c_llm_gemini     | todos_longos   | 189 | -0.014 | -0.12  |  0.904 | nan     | nan     | nan     | 0.725 |
| c_llm_gemjm3     | nenhum         | 189 |  0.487 |  4.347 |  0     | nan     | nan     | nan     | 0.237 |
| c_llm_gemjm3     | dm2007         | 189 |  0.203 |  1.232 |  0.218 |   0.353 |   1.789 |   0.074 | 0.281 |
| c_llm_gemjm3     | dm2009         | 189 |  0.528 |  4.52  |  0     |  -0.091 |  -0.609 |   0.542 | 0.244 |
| c_llm_gemjm3     | disp_focus_neg | 189 |  0.72  |  6.277 |  0     |  -0.371 |  -3.134 |   0.002 | 0.321 |
| c_llm_gemjm3     | breakeven_neg  | 189 |  0.508 |  2.47  |  0.013 |  -0.026 |  -0.117 |   0.907 | 0.238 |
| c_llm_gemjm3     | cds_neg        |  90 |  0.499 |  3.605 |  0     |  -0.345 |  -2.38  |   0.017 | 0.269 |
| c_llm_gemjm3     | embi_neg       | 189 |  0.557 |  7.244 |  0     |  -0.573 |  -5.685 |   0     | 0.561 |
| c_llm_gemjm3     | inclinacao     | 189 |  0.453 |  3.591 |  0     |   0.117 |   0.823 |   0.411 | 0.25  |
| c_llm_gemjm3     | todos          |  90 | -0.086 | -0.61  |  0.542 | nan     | nan     | nan     | 0.71  |
| c_llm_gemjm3     | todos_longos   | 189 | -0.065 | -0.49  |  0.624 | nan     | nan     | nan     | 0.726 |
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
| c_llm            | nenhum         | 188 |  0.077 |  1.244 |  0.214 | nan     | nan     | nan     | 0.006 |
| c_llm            | dm2007         | 188 |  0.009 |  0.178 |  0.859 |   0.454 |   6.894 |   0     | 0.207 |
| c_llm            | dm2009         | 188 |  0.079 |  1.42  |  0.156 |   0.267 |   5.691 |   0     | 0.077 |
| c_llm            | disp_focus_neg | 188 |  0.06  |  0.967 |  0.333 |   0.112 |   0.936 |   0.349 | 0.018 |
| c_llm            | breakeven_neg  | 188 |  0.03  |  0.528 |  0.597 |   0.202 |   2.985 |   0.003 | 0.045 |
| c_llm            | cds_neg        |  89 |  0.073 |  0.609 |  0.542 |   0.126 |   1.467 |   0.143 | 0.025 |
| c_llm            | embi_neg       | 188 |  0.075 |  1.235 |  0.217 |   0.016 |   0.217 |   0.828 | 0.006 |
| c_llm            | inclinacao     | 188 |  0.051 |  0.894 |  0.371 |  -0.125 |  -1.61  |   0.107 | 0.021 |
| c_llm            | todos          |  89 |  0.03  |  0.287 |  0.774 | nan     | nan     | nan     | 0.226 |
| c_llm            | todos_longos   | 188 | -0.023 | -0.454 |  0.65  | nan     | nan     | nan     | 0.237 |
| c_llm_jm3        | nenhum         | 188 |  0.056 |  0.505 |  0.614 | nan     | nan     | nan     | 0.003 |
| c_llm_jm3        | dm2007         | 188 | -0.057 | -0.622 |  0.534 |   0.469 |   6.558 |   0     | 0.21  |
| c_llm_jm3        | dm2009         | 188 |  0.004 |  0.042 |  0.967 |   0.265 |   5.126 |   0     | 0.071 |
| c_llm_jm3        | disp_focus_neg | 188 |  0.025 |  0.227 |  0.821 |   0.114 |   0.941 |   0.346 | 0.015 |
| c_llm_jm3        | breakeven_neg  | 188 | -0.022 | -0.205 |  0.838 |   0.217 |   3.101 |   0.002 | 0.044 |
| c_llm_jm3        | cds_neg        |  89 |  0.175 |  1.119 |  0.263 |   0.111 |   1.277 |   0.202 | 0.049 |
| c_llm_jm3        | embi_neg       | 188 |  0.053 |  0.484 |  0.628 |   0.013 |   0.185 |   0.853 | 0.003 |
| c_llm_jm3        | inclinacao     | 188 |  0.016 |  0.143 |  0.887 |  -0.131 |  -1.54  |   0.123 | 0.019 |
| c_llm_jm3        | todos          |  89 |  0.074 |  0.502 |  0.616 | nan     | nan     | nan     | 0.229 |
| c_llm_jm3        | todos_longos   | 188 | -0.095 | -1.041 |  0.298 | nan     | nan     | nan     | 0.244 |
| c_llm_gemini     | nenhum         | 188 |  0.059 |  0.839 |  0.402 | nan     | nan     | nan     | 0.003 |
| c_llm_gemini     | dm2007         | 188 |  0.018 |  0.306 |  0.759 |   0.453 |   7.02  |   0     | 0.207 |
| c_llm_gemini     | dm2009         | 188 |  0.06  |  0.955 |  0.339 |   0.266 |   5.575 |   0     | 0.074 |
| c_llm_gemini     | disp_focus_neg | 188 |  0.041 |  0.578 |  0.563 |   0.114 |   0.96  |   0.337 | 0.016 |
| c_llm_gemini     | breakeven_neg  | 188 | -0.023 | -0.356 |  0.722 |   0.218 |   3.237 |   0.001 | 0.044 |
| c_llm_gemini     | cds_neg        |  89 |  0.025 |  0.175 |  0.861 |   0.133 |   1.547 |   0.122 | 0.02  |
| c_llm_gemini     | embi_neg       | 188 |  0.057 |  0.805 |  0.421 |   0.011 |   0.155 |   0.877 | 0.004 |
| c_llm_gemini     | inclinacao     | 188 |  0.017 |  0.255 |  0.798 |  -0.13  |  -1.681 |   0.093 | 0.019 |
| c_llm_gemini     | todos          |  89 |  0.005 |  0.045 |  0.964 | nan     | nan     | nan     | 0.225 |
| c_llm_gemini     | todos_longos   | 188 | -0.019 | -0.336 |  0.737 | nan     | nan     | nan     | 0.237 |
| c_llm_gemjm3     | nenhum         | 188 |  0.041 |  0.39  |  0.696 | nan     | nan     | nan     | 0.002 |
| c_llm_gemjm3     | dm2007         | 188 | -0.087 | -0.954 |  0.34  |   0.478 |   6.729 |   0     | 0.214 |
| c_llm_gemjm3     | dm2009         | 188 | -0.02  | -0.216 |  0.829 |   0.271 |   5.331 |   0     | 0.071 |
| c_llm_gemjm3     | disp_focus_neg | 188 |  0.006 |  0.059 |  0.953 |   0.119 |   1.005 |   0.315 | 0.015 |
| c_llm_gemjm3     | breakeven_neg  | 188 | -0.044 | -0.416 |  0.677 |   0.226 |   3.128 |   0.002 | 0.045 |
| c_llm_gemjm3     | cds_neg        |  89 |  0.118 |  0.742 |  0.458 |   0.112 |   1.303 |   0.192 | 0.033 |
| c_llm_gemjm3     | embi_neg       | 188 |  0.038 |  0.361 |  0.718 |   0.013 |   0.194 |   0.846 | 0.002 |
| c_llm_gemjm3     | inclinacao     | 188 |  0.005 |  0.043 |  0.966 |  -0.135 |  -1.602 |   0.109 | 0.018 |
| c_llm_gemjm3     | todos          |  89 |  0     |  0.001 |  0.999 | nan     | nan     | nan     | 0.225 |
| c_llm_gemjm3     | todos_longos   | 188 | -0.113 | -1.239 |  0.216 | nan     | nan     | nan     | 0.247 |
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
| c_llm            |             10 | True               |                   9 |                    5 | False               | False              |   -0.01  |    0.517 |
| c_llm_dupla      |             10 | True               |                   9 |                    4 | False               | False              |   -0.01  |    0.331 |
| c_llm_gemini     |             10 | True               |                   9 |                    6 | False               | False              |   -0.076 |    0.655 |
| c_llm_gemjm3     |             10 | True               |                   9 |                    6 | False               | False              |   -0.086 |    0.72  |
| c_llm_jm3        |             10 | True               |                   9 |                    5 | False               | False              |   -0.022 |    0.648 |
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
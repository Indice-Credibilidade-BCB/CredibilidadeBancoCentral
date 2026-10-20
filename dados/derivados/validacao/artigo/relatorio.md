# Artigo de medição — resultados provisórios (saída automática)

Critérios registrados antes de rodar: docs/local, seção 4.2.17. Série principal: Sabiá v1.1 mensal.

## Seção 5 — robustez da construção (composição de veículos e amostra aleatória)

| versao            | agregacao   |   n_meses |   corr |   dif_media |   dif_abs_media |   noticias_por_mes_mediana |
|:------------------|:------------|----------:|-------:|------------:|----------------:|---------------------------:|
| constante         | mensal      |       189 |  0.972 |       0.002 |           0.017 |                         24 |
| constante         | jm3         |       189 |  0.992 |       0.001 |           0.008 |                         69 |
| fe_veiculo        | mensal      |       189 |  0.999 |       0.002 |           0.004 |                         30 |
| fe_veiculo        | jm3         |       189 |  0.999 |       0.002 |           0.004 |                         82 |
| so_infomoney      | mensal      |       185 |  0.93  |      -0.012 |           0.048 |                         12 |
| so_infomoney      | jm3         |       189 |  0.953 |      -0.011 |           0.036 |                         36 |
| so_valor          | mensal      |       180 |  0.868 |       0.024 |           0.057 |                         13 |
| so_valor          | jm3         |       183 |  0.918 |       0.022 |           0.04  |                         32 |
| amostra_aleatoria | mensal      |       178 |  0.836 |      -0     |           0.067 |                          5 |
| amostra_aleatoria | jm3         |       189 |  0.906 |      -0.001 |           0.045 |                         13 |

## 7.1 Convergente

Critério (Sabiá mensal): positiva e p < 5% com breakeven_neg E com dm2007 ou foc_gap_neg → **APROVADO** {'breakeven': True, 'focus': True, 'aprovado': True}

| alvo           |   c_llm |   c_llm_gemini |   c_llm_gemjm3 |   c_llm_jm3 |
|:---------------|--------:|---------------:|---------------:|------------:|
| breakeven_neg  |   0.712 |          0.785 |          0.808 |       0.779 |
| c_kf_suavizado |   0.398 |          0.477 |          0.487 |       0.431 |
| cds_neg        |   0.231 |          0.304 |          0.288 |       0.237 |
| disp_focus_neg |   0.565 |          0.586 |          0.627 |       0.644 |
| dm2007         |   0.662 |          0.764 |          0.806 |       0.743 |
| dm2009         |   0.437 |          0.412 |          0.45  |       0.518 |
| embi_neg       |   0.128 |          0.122 |          0.121 |       0.119 |
| foc_gap_neg    |   0.722 |          0.816 |          0.866 |       0.82  |
| inclinacao     |   0.144 |          0.199 |          0.292 |       0.253 |

p HAC:

| alvo           |   c_llm |   c_llm_gemini |   c_llm_gemjm3 |   c_llm_jm3 |
|:---------------|--------:|---------------:|---------------:|------------:|
| breakeven_neg  |   0     |          0     |          0     |       0     |
| c_kf_suavizado |   0     |          0     |          0     |       0     |
| cds_neg        |   0.158 |          0.054 |          0.097 |       0.185 |
| disp_focus_neg |   0     |          0     |          0     |       0     |
| dm2007         |   0     |          0     |          0     |       0     |
| dm2009         |   0     |          0.001 |          0.001 |       0     |
| embi_neg       |   0.374 |          0.405 |          0.444 |       0.456 |
| foc_gap_neg    |   0     |          0     |          0     |       0     |
| inclinacao     |   0.153 |          0.064 |          0.007 |       0.016 |

## 7.2 Discriminante

Critério: R² da inflação < 0,8 E c > 0, p < 5% para breakeven_neg ou embi_neg → **APROVADO** {'r2_inflacao': 0.35804019137595455, 'ancoras_de_mercado_aprovadas': ['breakeven_neg'], 'aprovado': True}

| indice       |   n |   r2_inflacao |
|:-------------|----:|--------------:|
| c_llm        | 189 |         0.358 |
| c_llm_jm3    | 189 |         0.486 |
| c_llm_gemini | 189 |         0.456 |
| c_llm_gemjm3 | 189 |         0.53  |

| indice       | ancora        |   n |       c |   p_hac |    r2 |
|:-------------|:--------------|----:|--------:|--------:|------:|
| c_llm        | breakeven_neg | 189 |   0.43  |   0     | 0.564 |
| c_llm        | embi_neg      | 189 | -12.416 |   0.052 | 0.188 |
| c_llm        | foc_gap_neg   | 189 |   0.411 |   0     | 0.717 |
| c_llm_jm3    | breakeven_neg | 189 |   0.545 |   0     | 0.62  |
| c_llm_jm3    | embi_neg      | 189 | -21.923 |   0.003 | 0.219 |
| c_llm_jm3    | foc_gap_neg   | 189 |   0.539 |   0     | 0.768 |
| c_llm_gemini | breakeven_neg | 189 |   0.554 |   0     | 0.643 |
| c_llm_gemini | embi_neg      | 189 | -19.587 |   0.005 | 0.211 |
| c_llm_gemini | foc_gap_neg   | 189 |   0.564 |   0     | 0.797 |
| c_llm_gemjm3 | breakeven_neg | 189 |   0.618 |   0     | 0.664 |
| c_llm_gemjm3 | embi_neg      | 189 | -25.772 |   0.001 | 0.232 |
| c_llm_gemjm3 | foc_gap_neg   | 189 |   0.652 |   0     | 0.831 |

## 7.3 Preditiva (não vista antes)

Primário: foc_gap_neg, h = 6, b > 0 e p < 5% → **APROVADO** {'b_primario': 0.23693743241900134, 'p_primario': 0.012450172999517051, 'aprovado_primario': True, 'secundarios_holm': {'breakeven_neg': 0.25331079897978037, 'embi_neg': 0.47835058206647585, 'foc_gap_neg': 0.03735051899855116}}

| indice       | alvo          |   h |   n |      b |   ep_hac |   p_hac |   p_holm_h6 |
|:-------------|:--------------|----:|----:|-------:|---------:|--------:|------------:|
| c_llm        | breakeven_neg |   1 | 189 |  0.062 |    0.033 |   0.058 |     nan     |
| c_llm        | breakeven_neg |   3 | 187 |  0.135 |    0.069 |   0.05  |     nan     |
| c_llm        | breakeven_neg |   6 | 184 |  0.174 |    0.114 |   0.127 |       0.253 |
| c_llm        | embi_neg      |   1 | 189 | -0.813 |    1.849 |   0.66  |     nan     |
| c_llm        | embi_neg      |   3 | 187 | -4.09  |    3.948 |   0.3   |     nan     |
| c_llm        | embi_neg      |   6 | 184 | -4.596 |    6.483 |   0.478 |       0.478 |
| c_llm        | foc_gap_neg   |   1 | 189 |  0.062 |    0.024 |   0.01  |     nan     |
| c_llm        | foc_gap_neg   |   3 | 187 |  0.159 |    0.053 |   0.003 |     nan     |
| c_llm        | foc_gap_neg   |   6 | 184 |  0.237 |    0.095 |   0.012 |       0.037 |
| c_llm_jm3    | breakeven_neg |   1 | 189 |  0.056 |    0.037 |   0.132 |     nan     |
| c_llm_jm3    | breakeven_neg |   3 | 187 |  0.136 |    0.099 |   0.171 |     nan     |
| c_llm_jm3    | breakeven_neg |   6 | 184 |  0.319 |    0.159 |   0.044 |       0.089 |
| c_llm_jm3    | embi_neg      |   1 | 189 | -3.216 |    2.023 |   0.112 |     nan     |
| c_llm_jm3    | embi_neg      |   3 | 187 | -8.391 |    5.013 |   0.094 |     nan     |
| c_llm_jm3    | embi_neg      |   6 | 184 | -7.16  |    9.675 |   0.459 |       0.459 |
| c_llm_jm3    | foc_gap_neg   |   1 | 189 |  0.072 |    0.026 |   0.005 |     nan     |
| c_llm_jm3    | foc_gap_neg   |   3 | 187 |  0.19  |    0.069 |   0.006 |     nan     |
| c_llm_jm3    | foc_gap_neg   |   6 | 184 |  0.378 |    0.129 |   0.003 |       0.01  |
| c_llm_gemini | breakeven_neg |   1 | 189 |  0.084 |    0.035 |   0.017 |     nan     |
| c_llm_gemini | breakeven_neg |   3 | 187 |  0.235 |    0.072 |   0.001 |     nan     |
| c_llm_gemini | breakeven_neg |   6 | 184 |  0.447 |    0.129 |   0.001 |       0.001 |
| c_llm_gemini | embi_neg      |   1 | 189 | -1.739 |    2.233 |   0.436 |     nan     |
| c_llm_gemini | embi_neg      |   3 | 187 | -5.462 |    6.345 |   0.389 |     nan     |
| c_llm_gemini | embi_neg      |   6 | 184 | -3.267 |    9.089 |   0.719 |       0.719 |
| c_llm_gemini | foc_gap_neg   |   1 | 189 |  0.094 |    0.026 |   0     |     nan     |
| c_llm_gemini | foc_gap_neg   |   3 | 187 |  0.25  |    0.06  |   0     |     nan     |
| c_llm_gemini | foc_gap_neg   |   6 | 184 |  0.437 |    0.11  |   0     |       0     |
| c_llm_gemjm3 | breakeven_neg |   1 | 189 |  0.092 |    0.035 |   0.008 |     nan     |
| c_llm_gemjm3 | breakeven_neg |   3 | 187 |  0.312 |    0.083 |   0     |     nan     |
| c_llm_gemjm3 | breakeven_neg |   6 | 184 |  0.637 |    0.153 |   0     |       0     |
| c_llm_gemjm3 | embi_neg      |   1 | 189 | -3.754 |    2.61  |   0.15  |     nan     |
| c_llm_gemjm3 | embi_neg      |   3 | 187 | -8.53  |    7.449 |   0.252 |     nan     |
| c_llm_gemjm3 | embi_neg      |   6 | 184 | -5.938 |   11.888 |   0.617 |       0.617 |
| c_llm_gemjm3 | foc_gap_neg   |   1 | 189 |  0.099 |    0.025 |   0     |     nan     |
| c_llm_gemjm3 | foc_gap_neg   |   3 | 187 |  0.302 |    0.071 |   0     |     nan     |
| c_llm_gemjm3 | foc_gap_neg   |   6 | 184 |  0.595 |    0.12  |   0     |       0     |

## 7.4 Encompassing (contra o latente do Kalman)

| variante_llm     | rival          |   n |     b1 |   p_b1 |    r2 |
|:-----------------|:---------------|----:|-------:|-------:|------:|
| c_llm            | nenhum         | 189 |  0.398 |  0     | 0.158 |
| c_llm            | dm2007         | 189 |  0.1   |  0.436 | 0.272 |
| c_llm            | dm2009         | 189 |  0.412 |  0     | 0.159 |
| c_llm            | disp_focus_neg | 189 |  0.517 |  0     | 0.189 |
| c_llm            | breakeven_neg  | 189 |  0.252 |  0.111 | 0.179 |
| c_llm            | cds_neg        |  90 |  0.38  |  0.006 | 0.177 |
| c_llm            | embi_neg       | 189 |  0.47  |  0     | 0.473 |
| c_llm            | inclinacao     | 189 |  0.369 |  0.001 | 0.196 |
| c_llm            | todos          |  90 | -0.01  |  0.933 | 0.709 |
| c_llm            | todos_longos   | 189 |  0.022 |  0.799 | 0.725 |
| c_llm_jm3        | nenhum         | 189 |  0.431 |  0     | 0.186 |
| c_llm_jm3        | dm2007         | 189 |  0.107 |  0.508 | 0.272 |
| c_llm_jm3        | dm2009         | 189 |  0.485 |  0     | 0.194 |
| c_llm_jm3        | disp_focus_neg | 189 |  0.648 |  0     | 0.252 |
| c_llm_jm3        | breakeven_neg  | 189 |  0.335 |  0.124 | 0.192 |
| c_llm_jm3        | cds_neg        |  90 |  0.468 |  0.001 | 0.247 |
| c_llm_jm3        | embi_neg       | 189 |  0.499 |  0     | 0.501 |
| c_llm_jm3        | inclinacao     | 189 |  0.393 |  0.002 | 0.207 |
| c_llm_jm3        | todos          |  90 |  0.012 |  0.93  | 0.709 |
| c_llm_jm3        | todos_longos   | 189 | -0.022 |  0.859 | 0.725 |
| c_llm_gemini     | nenhum         | 189 |  0.477 |  0     | 0.228 |
| c_llm_gemini     | dm2007         | 189 |  0.199 |  0.175 | 0.283 |
| c_llm_gemini     | dm2009         | 189 |  0.502 |  0     | 0.231 |
| c_llm_gemini     | disp_focus_neg | 189 |  0.655 |  0     | 0.288 |
| c_llm_gemini     | breakeven_neg  | 189 |  0.458 |  0.018 | 0.228 |
| c_llm_gemini     | cds_neg        |  90 |  0.428 |  0.003 | 0.207 |
| c_llm_gemini     | embi_neg       | 189 |  0.547 |  0     | 0.551 |
| c_llm_gemini     | inclinacao     | 189 |  0.445 |  0     | 0.253 |
| c_llm_gemini     | todos          |  90 | -0.076 |  0.553 | 0.71  |
| c_llm_gemini     | todos_longos   | 189 | -0.014 |  0.904 | 0.725 |
| c_llm_gemjm3     | nenhum         | 189 |  0.487 |  0     | 0.237 |
| c_llm_gemjm3     | dm2007         | 189 |  0.203 |  0.218 | 0.281 |
| c_llm_gemjm3     | dm2009         | 189 |  0.528 |  0     | 0.244 |
| c_llm_gemjm3     | disp_focus_neg | 189 |  0.72  |  0     | 0.321 |
| c_llm_gemjm3     | breakeven_neg  | 189 |  0.508 |  0.013 | 0.238 |
| c_llm_gemjm3     | cds_neg        |  90 |  0.499 |  0     | 0.269 |
| c_llm_gemjm3     | embi_neg       | 189 |  0.557 |  0     | 0.561 |
| c_llm_gemjm3     | inclinacao     | 189 |  0.453 |  0     | 0.25  |
| c_llm_gemjm3     | todos          |  90 | -0.086 |  0.542 | 0.71  |
| c_llm_gemjm3     | todos_longos   | 189 | -0.065 |  0.624 | 0.726 |
| c_llm_dupla      | nenhum         | 178 |  0.266 |  0.013 | 0.071 |
| c_llm_dupla      | dm2007         | 178 |  0.022 |  0.823 | 0.259 |
| c_llm_dupla      | dm2009         | 178 |  0.246 |  0.019 | 0.074 |
| c_llm_dupla      | disp_focus_neg | 178 |  0.301 |  0.001 | 0.075 |
| c_llm_dupla      | breakeven_neg  | 178 |  0.086 |  0.436 | 0.141 |
| c_llm_dupla      | cds_neg        |  87 |  0.238 |  0.111 | 0.095 |
| c_llm_dupla      | embi_neg       | 178 |  0.331 |  0     | 0.36  |
| c_llm_dupla      | inclinacao     | 178 |  0.244 |  0.02  | 0.14  |
| c_llm_dupla      | todos          |  87 | -0.01  |  0.908 | 0.711 |
| c_llm_dupla      | todos_longos   | 178 |  0.004 |  0.95  | 0.709 |
| c_llm_vmax_dupla | nenhum         | 178 |  0.266 |  0.013 | 0.071 |
| c_llm_vmax_dupla | dm2007         | 178 |  0.022 |  0.823 | 0.259 |
| c_llm_vmax_dupla | dm2009         | 178 |  0.246 |  0.019 | 0.074 |
| c_llm_vmax_dupla | disp_focus_neg | 178 |  0.301 |  0.001 | 0.075 |
| c_llm_vmax_dupla | breakeven_neg  | 178 |  0.086 |  0.436 | 0.141 |
| c_llm_vmax_dupla | cds_neg        |  87 |  0.238 |  0.111 | 0.095 |
| c_llm_vmax_dupla | embi_neg       | 178 |  0.331 |  0     | 0.36  |
| c_llm_vmax_dupla | inclinacao     | 178 |  0.244 |  0.02  | 0.14  |
| c_llm_vmax_dupla | todos          |  87 | -0.01  |  0.908 | 0.711 |
| c_llm_vmax_dupla | todos_longos   | 178 |  0.004 |  0.95  | 0.709 |
| c_llm_vmin_dupla | nenhum         | 180 |  0.087 |  0.358 | 0.008 |
| c_llm_vmin_dupla | dm2007         | 180 | -0.075 |  0.348 | 0.27  |
| c_llm_vmin_dupla | dm2009         | 180 |  0.05  |  0.595 | 0.022 |
| c_llm_vmin_dupla | disp_focus_neg | 180 |  0.065 |  0.458 | 0.01  |
| c_llm_vmin_dupla | breakeven_neg  | 180 | -0.077 |  0.355 | 0.147 |
| c_llm_vmin_dupla | cds_neg        |  89 |  0.051 |  0.704 | 0.045 |
| c_llm_vmin_dupla | embi_neg       | 180 |  0.167 |  0.042 | 0.284 |
| c_llm_vmin_dupla | inclinacao     | 180 |  0.097 |  0.279 | 0.079 |
| c_llm_vmin_dupla | todos          |  89 | -0.022 |  0.717 | 0.715 |
| c_llm_vmin_dupla | todos_longos   | 180 | -0.024 |  0.585 | 0.718 |

## 8 Estudo de eventos do Copom (não visto antes)

b = variação do Δ do índice por 10 bps de surpresa; HC1.

| index   |   n |   b_por_10bps |   ep_por_10bps |     p |   const |   delta_medio |
|:--------|----:|--------------:|---------------:|------:|--------:|--------------:|
| d1_7d   |  81 |         0.022 |          0.013 | 0.084 |   0.026 |         0.024 |
| d1_14d  | 118 |         0.022 |          0.009 | 0.012 |   0.01  |         0.007 |
| d2_7d   | 101 |         0.014 |          0.009 | 0.113 |   0.03  |         0.026 |

|surpresa|:

| index   |   n |   b_por_10bps |   ep_por_10bps |     p |   const |
|:--------|----:|--------------:|---------------:|------:|--------:|
| d1_7d   |  81 |        -0.023 |          0.018 | 0.19  |   0.038 |
| d1_14d  | 118 |        -0.027 |          0.011 | 0.012 |   0.024 |
| d2_7d   | 101 |        -0.016 |          0.012 | 0.192 |   0.038 |

## 8 Eventos institucionais (EXPLORATÓRIO)

| data       | evento                                        | dimensao   |   antes |   depois |   delta |   n_antes |   n_depois |   placebo_frac_abs_maior |
|:-----------|:----------------------------------------------|:-----------|--------:|---------:|--------:|----------:|-----------:|-------------------------:|
| 2016-05-17 | Goldfajn anunciado e PEC da autonomia técnica | d1         |   0.423 |    0.625 |   0.202 |        13 |         18 |                    0.045 |
| 2020-11-03 | Senado aprova o PLP 19/2019                   | d1         |   0.589 |    0.609 |   0.021 |        31 |         32 |                    0.828 |
| 2021-02-10 | Câmara aprova a autonomia (LC 179/2021)       | d1         |   0.482 |    0.45  |  -0.032 |        42 |         40 |                    0.725 |
| 2023-01-18 | Lula critica a autonomia do BC (GloboNews)    | d1         |   0.195 |    0.335 |   0.14  |        50 |        174 |                    0.133 |
| 2024-05-08 | Copom corta 0,25 com placar 5 a 4             | d1         |   0.542 |    0.41  |  -0.132 |        77 |        120 |                    0.156 |
| 2024-12-11 | Copom sobe 1 ponto e sinaliza mais duas altas | d1         |   0.353 |    0.299 |  -0.054 |       107 |        112 |                    0.565 |
| 2016-05-17 | Goldfajn anunciado e PEC da autonomia técnica | d2         |   0.423 |    0.609 |   0.186 |        24 |         23 |                    0.035 |
| 2020-11-03 | Senado aprova o PLP 19/2019                   | d2         |   0.668 |    0.565 |  -0.103 |        49 |         41 |                    0.221 |
| 2021-02-10 | Câmara aprova a autonomia (LC 179/2021)       | d2         |   0.597 |    0.552 |  -0.045 |        64 |         64 |                    0.588 |
| 2023-01-18 | Lula critica a autonomia do BC (GloboNews)    | d2         |   0.448 |    0.357 |  -0.091 |        50 |        283 |                    0.277 |
| 2024-05-08 | Copom corta 0,25 com placar 5 a 4             | d2         |   0.527 |    0.448 |  -0.08  |       129 |        160 |                    0.356 |
| 2024-12-11 | Copom sobe 1 ponto e sinaliza mais duas altas | d2         |   0.536 |    0.454 |  -0.082 |       139 |        157 |                    0.333 |
| 2016-05-17 | Goldfajn anunciado e PEC da autonomia técnica | d3         |   0.446 |    0.517 |   0.071 |        24 |         21 |                    0.257 |
| 2020-11-03 | Senado aprova o PLP 19/2019                   | d3         |   0.566 |    0.571 |   0.005 |        42 |         34 |                    0.895 |
| 2021-02-10 | Câmara aprova a autonomia (LC 179/2021)       | d3         |   0.532 |    0.567 |   0.036 |        56 |         59 |                    0.494 |
| 2023-01-18 | Lula critica a autonomia do BC (GloboNews)    | d3         |   0.488 |    0.36  |  -0.128 |        37 |        282 |                    0.053 |
| 2024-05-08 | Copom corta 0,25 com placar 5 a 4             | d3         |   0.456 |    0.442 |  -0.014 |       101 |        123 |                    0.733 |
| 2024-12-11 | Copom sobe 1 ponto e sinaliza mais duas altas | d3         |   0.49  |    0.53  |   0.04  |       101 |        112 |                    0.468 |

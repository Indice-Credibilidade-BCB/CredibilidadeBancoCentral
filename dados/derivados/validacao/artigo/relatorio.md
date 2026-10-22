# Artigo de medição — resultados provisórios (saída automática)

Critérios registrados antes de rodar: docs/local, seção 4.2.17. Série principal: Sabiá v1.1 mensal.

## Seção 5 — robustez da construção (composição de veículos e amostra aleatória)

| versao              | agregacao   |   n_meses |   corr |   dif_media |   dif_abs_media |   noticias_por_mes_mediana |
|:--------------------|:------------|----------:|-------:|------------:|----------------:|---------------------------:|
| constante           | mensal      |       189 |  0.983 |      -0.001 |           0.014 |                         49 |
| constante           | jm3         |       189 |  0.997 |       0.001 |           0.007 |                        157 |
| so_originais        | mensal      |       189 |  0.955 |       0.007 |           0.027 |                         30 |
| so_originais        | jm3         |       189 |  0.985 |       0.007 |           0.017 |                         83 |
| fe_veiculo          | mensal      |       189 |  0.998 |       0.002 |           0.007 |                         64 |
| fe_veiculo          | jm3         |       189 |  0.998 |       0.002 |           0.007 |                        185 |
| so_infomoney        | mensal      |       185 |  0.911 |      -0.005 |           0.051 |                         12 |
| so_infomoney        | jm3         |       189 |  0.957 |      -0.005 |           0.031 |                         36 |
| so_valor            | mensal      |       180 |  0.803 |       0.032 |           0.068 |                         13 |
| so_valor            | jm3         |       183 |  0.889 |       0.03  |           0.049 |                         33 |
| amostra_aleatoria   | mensal      |       187 |  0.857 |       0.003 |           0.056 |                         10 |
| amostra_aleatoria   | jm3         |       189 |  0.954 |       0.003 |           0.03  |                         30 |
| sem_agência_brasil  | mensal      |       189 |  0.999 |       0.001 |           0.004 |                         60 |
| sem_agência_brasil  | jm3         |       189 |  0.999 |       0.001 |           0.003 |                        172 |
| sem_bloomberg_línea | mensal      |       189 |  1     |      -0     |           0.001 |                         63 |
| sem_bloomberg_línea | jm3         |       189 |  1     |      -0     |           0.001 |                        184 |
| sem_cartacapital    | mensal      |       189 |  1     |       0.001 |           0.002 |                         61 |
| sem_cartacapital    | jm3         |       189 |  1     |       0.001 |           0.001 |                        184 |
| sem_exame           | mensal      |       189 |  0.989 |       0.001 |           0.013 |                         45 |
| sem_exame           | jm3         |       189 |  0.997 |       0     |           0.008 |                        134 |
| sem_folha           | mensal      |       189 |  1     |       0     |           0.001 |                         63 |
| sem_folha           | jm3         |       189 |  1     |      -0     |           0.001 |                        184 |
| sem_g1              | mensal      |       189 |  0.993 |       0.003 |           0.011 |                         49 |
| sem_g1              | jm3         |       189 |  0.997 |       0.003 |           0.007 |                        146 |

## 7.1 Convergente

Critério (Sabiá mensal): positiva e p < 5% com breakeven_neg E com dm2007 ou foc_gap_neg → **APROVADO** {'breakeven': True, 'focus': True, 'aprovado': True}

| alvo           |   c_llm |   c_llm_gemini |   c_llm_gemjm3 |   c_llm_jm3 |
|:---------------|--------:|---------------:|---------------:|------------:|
| breakeven_neg  |   0.74  |          0.782 |          0.806 |       0.792 |
| c_kf_suavizado |   0.381 |          0.457 |          0.473 |       0.419 |
| cds_neg        |   0.219 |          0.304 |          0.285 |       0.225 |
| disp_focus_neg |   0.571 |          0.585 |          0.619 |       0.63  |
| dm2007         |   0.683 |          0.765 |          0.809 |       0.759 |
| dm2009         |   0.439 |          0.406 |          0.441 |       0.509 |
| embi_neg       |   0.13  |          0.132 |          0.133 |       0.132 |
| foc_gap_neg    |   0.752 |          0.819 |          0.869 |       0.836 |
| inclinacao     |   0.177 |          0.208 |          0.3   |       0.274 |

p HAC:

| alvo           |   c_llm |   c_llm_gemini |   c_llm_gemjm3 |   c_llm_jm3 |
|:---------------|--------:|---------------:|---------------:|------------:|
| breakeven_neg  |   0     |          0     |          0     |       0     |
| c_kf_suavizado |   0.001 |          0     |          0     |       0     |
| cds_neg        |   0.207 |          0.051 |          0.101 |       0.23  |
| disp_focus_neg |   0     |          0     |          0     |       0     |
| dm2007         |   0     |          0     |          0     |       0     |
| dm2009         |   0     |          0.001 |          0.001 |       0     |
| embi_neg       |   0.365 |          0.353 |          0.393 |       0.41  |
| foc_gap_neg    |   0     |          0     |          0     |       0     |
| inclinacao     |   0.096 |          0.052 |          0.006 |       0.011 |

## 7.2 Discriminante

Critério: R² da inflação < 0,8 E c > 0, p < 5% para breakeven_neg ou embi_neg → **APROVADO** {'r2_inflacao': 0.42042633392347284, 'ancoras_de_mercado_aprovadas': ['breakeven_neg'], 'aprovado': True}

| indice       |   n |   r2_inflacao |
|:-------------|----:|--------------:|
| c_llm        | 189 |         0.42  |
| c_llm_jm3    | 189 |         0.526 |
| c_llm_gemini | 189 |         0.484 |
| c_llm_gemjm3 | 189 |         0.549 |

| indice       | ancora        |   n |       c |   p_hac |    r2 |
|:-------------|:--------------|----:|--------:|--------:|------:|
| c_llm        | breakeven_neg | 189 |   0.478 |   0     | 0.586 |
| c_llm        | embi_neg      | 189 | -16.032 |   0.017 | 0.198 |
| c_llm        | foc_gap_neg   | 189 |   0.451 |   0     | 0.728 |
| c_llm_jm3    | breakeven_neg | 189 |   0.589 |   0     | 0.639 |
| c_llm_jm3    | embi_neg      | 189 | -23.644 |   0.002 | 0.222 |
| c_llm_jm3    | foc_gap_neg   | 189 |   0.581 |   0     | 0.781 |
| c_llm_gemini | breakeven_neg | 189 |   0.565 |   0     | 0.639 |
| c_llm_gemini | embi_neg      | 189 | -20.356 |   0.004 | 0.212 |
| c_llm_gemini | foc_gap_neg   | 189 |   0.581 |   0     | 0.798 |
| c_llm_gemjm3 | breakeven_neg | 189 |   0.63  |   0     | 0.663 |
| c_llm_gemjm3 | embi_neg      | 189 | -25.874 |   0.001 | 0.23  |
| c_llm_gemjm3 | foc_gap_neg   | 189 |   0.67  |   0     | 0.833 |

## 7.3 Preditiva (não vista antes)

Primário: foc_gap_neg, h = 6, b > 0 e p < 5% → **APROVADO** {'b_primario': 0.3013999275869357, 'p_primario': 0.0031143370340076856, 'aprovado_primario': True, 'secundarios_holm': {'breakeven_neg': 0.06844772874333063, 'embi_neg': 0.9648565023822279, 'foc_gap_neg': 0.009343011102023057}}

| indice       | alvo          |   h |   n |      b |   ep_hac |   p_hac |   p_holm_h6 |
|:-------------|:--------------|----:|----:|-------:|---------:|--------:|------------:|
| c_llm        | breakeven_neg |   1 | 189 |  0.072 |    0.034 |   0.036 |     nan     |
| c_llm        | breakeven_neg |   3 | 187 |  0.189 |    0.066 |   0.004 |     nan     |
| c_llm        | breakeven_neg |   6 | 184 |  0.281 |    0.133 |   0.034 |       0.068 |
| c_llm        | embi_neg      |   1 | 189 | -0.762 |    1.962 |   0.698 |     nan     |
| c_llm        | embi_neg      |   3 | 187 | -2.71  |    4.577 |   0.554 |     nan     |
| c_llm        | embi_neg      |   6 | 184 | -0.345 |    7.838 |   0.965 |       0.965 |
| c_llm        | foc_gap_neg   |   1 | 189 |  0.072 |    0.025 |   0.005 |     nan     |
| c_llm        | foc_gap_neg   |   3 | 187 |  0.183 |    0.056 |   0.001 |     nan     |
| c_llm        | foc_gap_neg   |   6 | 184 |  0.301 |    0.102 |   0.003 |       0.009 |
| c_llm_jm3    | breakeven_neg |   1 | 189 |  0.079 |    0.035 |   0.022 |     nan     |
| c_llm_jm3    | breakeven_neg |   3 | 187 |  0.213 |    0.089 |   0.016 |     nan     |
| c_llm_jm3    | breakeven_neg |   6 | 184 |  0.441 |    0.196 |   0.024 |       0.048 |
| c_llm_jm3    | embi_neg      |   1 | 189 | -2.916 |    2.066 |   0.158 |     nan     |
| c_llm_jm3    | embi_neg      |   3 | 187 | -6.913 |    5.837 |   0.236 |     nan     |
| c_llm_jm3    | embi_neg      |   6 | 184 | -3.854 |   11.185 |   0.73  |       0.73  |
| c_llm_jm3    | foc_gap_neg   |   1 | 189 |  0.079 |    0.025 |   0.002 |     nan     |
| c_llm_jm3    | foc_gap_neg   |   3 | 187 |  0.22  |    0.069 |   0.001 |     nan     |
| c_llm_jm3    | foc_gap_neg   |   6 | 184 |  0.453 |    0.136 |   0.001 |       0.003 |
| c_llm_gemini | breakeven_neg |   1 | 189 |  0.094 |    0.034 |   0.006 |     nan     |
| c_llm_gemini | breakeven_neg |   3 | 187 |  0.272 |    0.07  |   0     |     nan     |
| c_llm_gemini | breakeven_neg |   6 | 184 |  0.498 |    0.139 |   0     |       0.001 |
| c_llm_gemini | embi_neg      |   1 | 189 | -2.089 |    2.407 |   0.385 |     nan     |
| c_llm_gemini | embi_neg      |   3 | 187 | -5.287 |    6.848 |   0.44  |     nan     |
| c_llm_gemini | embi_neg      |   6 | 184 | -1.723 |   10.389 |   0.868 |       0.868 |
| c_llm_gemini | foc_gap_neg   |   1 | 189 |  0.094 |    0.025 |   0     |     nan     |
| c_llm_gemini | foc_gap_neg   |   3 | 187 |  0.252 |    0.06  |   0     |     nan     |
| c_llm_gemini | foc_gap_neg   |   6 | 184 |  0.463 |    0.109 |   0     |       0     |
| c_llm_gemjm3 | breakeven_neg |   1 | 189 |  0.108 |    0.035 |   0.002 |     nan     |
| c_llm_gemjm3 | breakeven_neg |   3 | 187 |  0.354 |    0.083 |   0     |     nan     |
| c_llm_gemjm3 | breakeven_neg |   6 | 184 |  0.681 |    0.166 |   0     |       0     |
| c_llm_gemjm3 | embi_neg      |   1 | 189 | -3.664 |    2.714 |   0.177 |     nan     |
| c_llm_gemjm3 | embi_neg      |   3 | 187 | -7.906 |    7.951 |   0.32  |     nan     |
| c_llm_gemjm3 | embi_neg      |   6 | 184 | -4.408 |   13.337 |   0.741 |       0.741 |
| c_llm_gemjm3 | foc_gap_neg   |   1 | 189 |  0.099 |    0.025 |   0     |     nan     |
| c_llm_gemjm3 | foc_gap_neg   |   3 | 187 |  0.313 |    0.068 |   0     |     nan     |
| c_llm_gemjm3 | foc_gap_neg   |   6 | 184 |  0.639 |    0.117 |   0     |       0     |

## 7.4 Encompassing (contra o latente do Kalman)

| variante_llm     | rival          |   n |     b1 |   p_b1 |    r2 |
|:-----------------|:---------------|----:|-------:|-------:|------:|
| c_llm            | nenhum         | 189 |  0.381 |  0.001 | 0.145 |
| c_llm            | dm2007         | 189 |  0.054 |  0.705 | 0.268 |
| c_llm            | dm2009         | 189 |  0.393 |  0.001 | 0.146 |
| c_llm            | disp_focus_neg | 189 |  0.497 |  0     | 0.173 |
| c_llm            | breakeven_neg  | 189 |  0.215 |  0.25  | 0.168 |
| c_llm            | cds_neg        |  90 |  0.358 |  0.015 | 0.163 |
| c_llm            | embi_neg       | 189 |  0.455 |  0     | 0.46  |
| c_llm            | inclinacao     | 189 |  0.348 |  0.003 | 0.18  |
| c_llm            | todos          |  90 | -0.083 |  0.432 | 0.711 |
| c_llm            | todos_longos   | 189 | -0.058 |  0.559 | 0.726 |
| c_llm_jm3        | nenhum         | 189 |  0.419 |  0     | 0.175 |
| c_llm_jm3        | dm2007         | 189 |  0.064 |  0.713 | 0.268 |
| c_llm_jm3        | dm2009         | 189 |  0.464 |  0     | 0.181 |
| c_llm_jm3        | disp_focus_neg | 189 |  0.61  |  0     | 0.231 |
| c_llm_jm3        | breakeven_neg  | 189 |  0.307 |  0.18  | 0.183 |
| c_llm_jm3        | cds_neg        |  90 |  0.451 |  0.002 | 0.234 |
| c_llm_jm3        | embi_neg       | 189 |  0.494 |  0     | 0.496 |
| c_llm_jm3        | inclinacao     | 189 |  0.379 |  0.003 | 0.195 |
| c_llm_jm3        | todos          |  90 | -0.066 |  0.638 | 0.71  |
| c_llm_jm3        | todos_longos   | 189 | -0.092 |  0.474 | 0.727 |
| c_llm_gemini     | nenhum         | 189 |  0.457 |  0     | 0.209 |
| c_llm_gemini     | dm2007         | 189 |  0.149 |  0.332 | 0.276 |
| c_llm_gemini     | dm2009         | 189 |  0.476 |  0     | 0.21  |
| c_llm_gemini     | disp_focus_neg | 189 |  0.622 |  0     | 0.261 |
| c_llm_gemini     | breakeven_neg  | 189 |  0.402 |  0.046 | 0.21  |
| c_llm_gemini     | cds_neg        |  90 |  0.406 |  0.006 | 0.19  |
| c_llm_gemini     | embi_neg       | 189 |  0.533 |  0     | 0.535 |
| c_llm_gemini     | inclinacao     | 189 |  0.423 |  0     | 0.234 |
| c_llm_gemini     | todos          |  90 | -0.114 |  0.329 | 0.712 |
| c_llm_gemini     | todos_longos   | 189 | -0.067 |  0.548 | 0.726 |
| c_llm_gemjm3     | nenhum         | 189 |  0.473 |  0     | 0.224 |
| c_llm_gemjm3     | dm2007         | 189 |  0.16  |  0.353 | 0.275 |
| c_llm_gemjm3     | dm2009         | 189 |  0.506 |  0     | 0.228 |
| c_llm_gemjm3     | disp_focus_neg | 189 |  0.685 |  0     | 0.296 |
| c_llm_gemjm3     | breakeven_neg  | 189 |  0.466 |  0.029 | 0.224 |
| c_llm_gemjm3     | cds_neg        |  90 |  0.479 |  0.001 | 0.251 |
| c_llm_gemjm3     | embi_neg       | 189 |  0.55  |  0     | 0.553 |
| c_llm_gemjm3     | inclinacao     | 189 |  0.437 |  0.001 | 0.236 |
| c_llm_gemjm3     | todos          |  90 | -0.117 |  0.39  | 0.711 |
| c_llm_gemjm3     | todos_longos   | 189 | -0.112 |  0.387 | 0.728 |
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
| d1_7d   | 115 |         0.009 |          0.012 | 0.42  |   0.028 |         0.026 |
| d1_14d  | 124 |         0.019 |          0.007 | 0.007 |   0.018 |         0.016 |
| d2_7d   | 122 |         0.005 |          0.008 | 0.548 |   0.022 |         0.021 |

|surpresa|:

| index   |   n |   b_por_10bps |   ep_por_10bps |     p |   const |
|:--------|----:|--------------:|---------------:|------:|--------:|
| d1_7d   | 115 |        -0.005 |          0.014 | 0.708 |   0.03  |
| d1_14d  | 124 |         0     |          0.012 | 0.973 |   0.015 |
| d2_7d   | 122 |        -0.005 |          0.011 | 0.623 |   0.025 |

## 8 Eventos institucionais (EXPLORATÓRIO)

| data       | evento                                        | dimensao   |   antes |   depois |   delta |   n_antes |   n_depois |   placebo_frac_abs_maior |
|:-----------|:----------------------------------------------|:-----------|--------:|---------:|--------:|----------:|-----------:|-------------------------:|
| 2016-05-17 | Goldfajn anunciado e PEC da autonomia técnica | d1         |   0.46  |    0.585 |   0.125 |        31 |         50 |                    0.156 |
| 2020-11-03 | Senado aprova o PLP 19/2019                   | d1         |   0.568 |    0.633 |   0.064 |        44 |         49 |                    0.413 |
| 2021-02-10 | Câmara aprova a autonomia (LC 179/2021)       | d1         |   0.531 |    0.462 |  -0.07  |        64 |         52 |                    0.37  |
| 2023-01-18 | Lula critica a autonomia do BC (GloboNews)    | d1         |   0.198 |    0.343 |   0.145 |        62 |        235 |                    0.096 |
| 2024-05-08 | Copom corta 0,25 com placar 5 a 4             | d1         |   0.538 |    0.413 |  -0.125 |        92 |        155 |                    0.158 |
| 2024-12-11 | Copom sobe 1 ponto e sinaliza mais duas altas | d1         |   0.355 |    0.278 |  -0.077 |       138 |        152 |                    0.337 |
| 2016-05-17 | Goldfajn anunciado e PEC da autonomia técnica | d2         |   0.537 |    0.608 |   0.07  |        60 |         73 |                    0.328 |
| 2020-11-03 | Senado aprova o PLP 19/2019                   | d2         |   0.497 |    0.591 |   0.094 |        68 |         58 |                    0.189 |
| 2021-02-10 | Câmara aprova a autonomia (LC 179/2021)       | d2         |   0.548 |    0.581 |   0.032 |       102 |         84 |                    0.648 |
| 2023-01-18 | Lula critica a autonomia do BC (GloboNews)    | d2         |   0.351 |    0.307 |  -0.044 |        57 |        418 |                    0.543 |
| 2024-05-08 | Copom corta 0,25 com placar 5 a 4             | d2         |   0.568 |    0.485 |  -0.083 |       162 |        218 |                    0.26  |
| 2024-12-11 | Copom sobe 1 ponto e sinaliza mais duas altas | d2         |   0.48  |    0.438 |  -0.042 |       190 |        220 |                    0.559 |
| 2016-05-17 | Goldfajn anunciado e PEC da autonomia técnica | d3         |   0.489 |    0.532 |   0.044 |        51 |         50 |                    0.387 |
| 2020-11-03 | Senado aprova o PLP 19/2019                   | d3         |   0.509 |    0.575 |   0.065 |        55 |         40 |                    0.237 |
| 2021-02-10 | Câmara aprova a autonomia (LC 179/2021)       | d3         |   0.531 |    0.57  |   0.039 |        85 |         77 |                    0.425 |
| 2023-01-18 | Lula critica a autonomia do BC (GloboNews)    | d3         |   0.415 |    0.372 |  -0.043 |        41 |        430 |                    0.396 |
| 2024-05-08 | Copom corta 0,25 com placar 5 a 4             | d3         |   0.487 |    0.442 |  -0.045 |       125 |        167 |                    0.383 |
| 2024-12-11 | Copom sobe 1 ponto e sinaliza mais duas altas | d3         |   0.455 |    0.452 |  -0.002 |       137 |        157 |                    0.957 |

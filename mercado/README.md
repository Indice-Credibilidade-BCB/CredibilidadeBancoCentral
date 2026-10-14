# `mercado/` — Séries de mercado e calendários (Etapa 0)

Âncoras de **comportamento revelado** para a validação independente do índice
(Bloco 3): "preço é percepção sem retórica". Também o calendário que liga as
reuniões do Copom aos contratos de DI1 (Blocos 5 e 6).

Rodar da **raiz** do repositório:

```bash
python -m mercado.lista2              # atualiza tudo e imprime o estado (usa caches)
python -m mercado.lista2 --atualizar  # baixa tudo de novo
python -m pytest mercado/tests -q     # 11 testes, sem rede
```

| Arquivo | O que faz |
|---|---|
| `calendario.py` | Dias úteis (feriados ANBIMA, com regra algorítmica idêntica em 2001–2030), vencimentos DI1 (1º dia útil do mês), calendário estruturado do Copom × DI1. |
| `anbima.py` | Coletor **cumulativo** da ETTJ (Svensson + vértices: nominal, real, implícita) e das taxas indicativas de títulos públicos. |
| `inflacao_implicita.py` | Curvas nominal e real e inflação implícita históricas a partir do Tesouro Direto (2004–hoje), validadas contra a ETTJ. |
| `lista2.py` | Orquestra a "lista 2" (abaixo) e imprime a tabela de estado. |
| `scrappingDI.py` | Coleta antiga da curva de Swap DI (SGS). |

## Lista 2 — o que é baixado e onde fica

| Dado | Fonte | Saída |
|---|---|---|
| Focus — mediana IPCA 12m e dispersão | BCB Olinda | `dados/macro/focus_ipca_12m_{suav,nsuav}.csv` (diário), `focus_ipca_12m_mensal.csv` |
| Metas históricas de inflação | SGS 13521 + bandas do CMN | `dados/macro/metas_inflacao_historico.csv` |
| Selic-meta histórica | SGS 432 + histórico do Copom | `dados/macro/selic_meta.csv`, `reunioes_copom.csv` |
| Calendário Copom × vencimentos DI1 | BCB + regra B3 + feriados ANBIMA | `dados/mercado/calendario_copom_di1.csv`, `di1_vencimentos_genericos.csv` |
| Curvas nominal e real, inflação implícita | Tesouro Direto (histórico) e ANBIMA (último mês) | `dados/mercado/curvas_tesouro_direto_diario.csv`, `inflacao_implicita_mensal.csv`, `breakeven.csv`, `anbima/` |
| Dispersão do Focus | BCB Olinda | colunas `desvio_padrao_*` e `amplitude_*` do Focus mensal |

## Limites de acesso (verificados em 2026-10-14)

- **ANBIMA** só serve gratuitamente cerca de **um mês** para trás (ETTJ desde
  ~21 dias úteis; arquivos `msAAMMDD.txt` idem). O histórico exige o ANBIMA
  Data. Por isso `anbima.coletar()` acumula: rodar `python -m mercado.lista2`
  ao menos a cada três semanas mantém a série sem buracos a partir de
  2026-09-14.
- **B3 (taxas referenciais DI×pré e DI×IPCA)**: a página antiga devolve erro
  524 do Cloudflare para datas históricas e só a casca HTML para datas
  recentes. Não usada.
- **Calendário futuro do Copom**: o BCB não o expõe por API. Opcional:
  `dados/mercado/copom_agenda_futura.csv` com a coluna `data_reuniao`. Sem
  ele, só a última reunião fica sem `proxima_reuniao`.

## Inflação implícita histórica (Tesouro Direto)

Taxa média de compra e venda por título-dia; títulos com menos de 6 meses
para o vencimento saem (taxa espúria perto de zero). Zero-cupom (LTN,
NTN-B Principal) no próprio prazo; com cupom (NTN-F, NTN-B) na duration de
Macaulay. Interpolação linear em 1, 2, 3, 5 e 10 anos úteis, sem
extrapolação. Implícita de Fisher: (1+nominal)/(1+real) − 1.

Validação na sobreposição com a ETTJ oficial (21 dias, set–out/2026): diferença
média abaixo de 0,09 p.p. em 3 e 5 anos, correlação diária de 0,95 a 0,99
(`dados/mercado/validacao_td_vs_anbima.csv`).

`breakeven.csv` (rival de mercado lido por `validacao/rivais.py`) usa **5
anos**: horizonte de ancoragem de médio prazo e cobertura de 100% dos dias
desde 2010. O de 2 anos tem buracos em 2020–2022 (sem NTN-B curta no Tesouro
Direto).

A implícita é expectativa + prêmio de risco de inflação + prêmio de
liquidez, não expectativa pura — registrar isso na leitura dos resultados.

## Calendário Copom × DI1

Uma linha por reunião: pregões D−1, D e D+1 (o Copom anuncia após o
fechamento, então o fechamento de D ainda é "antes"), vigência, os quatro DI1
vivos em D com seus dias úteis, o contrato curto que precifica a decisão
(`kuttner_*`) e o seguinte (`kuttner2_*`), se cada um atravessa a próxima
reunião, o fator de Kuttner DU[D+1, venc)/DU[vigência, venc) e a marca
`kuttner_curto_demais` quando o curto tem menos de 5 dias úteis entre a
vigência e o vencimento (aí usar `kuttner2`).

## Independência dos blocos

Estas séries ficam **isoladas no Bloco 3**, como validação genuinamente fora
da amostra. Os termos de inflação dos Blocos 1–2 usam IPCA realizado defasado
e medianas do Focus. Alimentar breakeven na estimação do Bloco 2 destruiria a
independência do Bloco 3.

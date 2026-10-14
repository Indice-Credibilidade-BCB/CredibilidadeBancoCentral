# `mercado/` — Séries de mercado e calendários (Etapa 0)

Âncoras de **comportamento revelado** para a validação independente do índice
(Bloco 3): "preço é percepção sem retórica". Também o calendário que liga as
reuniões do Copom aos contratos de DI1 (Blocos 5 e 6).

Rodar da **raiz** do repositório:

```bash
python -m mercado.lista2              # atualiza tudo e imprime o estado (usa caches)
python -m mercado.lista2 --atualizar  # baixa tudo de novo
python -m pytest mercado/tests -q     # 14 testes, sem rede
```

| Arquivo | O que faz |
|---|---|
| `calendario.py` | Dias úteis (feriados ANBIMA, com regra algorítmica idêntica em 2001–2030), vencimentos DI1 (1º dia útil do mês), calendário estruturado do Copom × DI1. |
| `anbima.py` | Coletor **cumulativo** da ETTJ (Svensson + vértices: nominal, real, implícita) e das taxas indicativas de títulos públicos. |
| `b3_taxas.py` | Curvas de referência diárias da B3 (arquivo TaxaSwap): DI×Pré desde 2001, LTN e NTN-B desde 2004, DI×IPCA desde 2005. **Fonte principal** das curvas e da inflação implícita. |
| `inflacao_implicita.py` | Curvas e inflação implícita a partir do Tesouro Direto (2004–hoje): fonte secundária, preenche buracos. |
| `lista2.py` | Orquestra a "lista 2" (abaixo) e imprime a tabela de estado. |
| `scrappingDI.py` | Coleta antiga da curva de Swap DI (SGS). |

## Lista 2 — o que é baixado e onde fica

| Dado | Fonte | Saída |
|---|---|---|
| Focus — mediana IPCA 12m e dispersão | BCB Olinda | `dados/macro/focus_ipca_12m_{suav,nsuav}.csv` (diário), `focus_ipca_12m_mensal.csv` |
| Metas históricas de inflação | SGS 13521 + bandas do CMN | `dados/macro/metas_inflacao_historico.csv` |
| Selic-meta histórica | SGS 432 + histórico do Copom | `dados/macro/selic_meta.csv`, `reunioes_copom.csv` |
| Calendário Copom × vencimentos DI1 | BCB + regra B3 + feriados ANBIMA | `dados/mercado/calendario_copom_di1.csv`, `di1_vencimentos_genericos.csv` |
| Curvas nominal e real, inflação implícita | B3 TaxaSwap (histórico), Tesouro Direto (secundária), ANBIMA (último mês) | `dados/mercado/curvas_b3_diario.csv`, `curvas_b3_mensal.csv`, `curvas_tesouro_direto_diario.csv`, `breakeven.csv`, `anbima/` |
| Agenda do Copom, inclusive reuniões futuras | BCB, agenda "Reuniões do Copom" | `dados/mercado/copom_agenda.csv` |
| Dispersão do Focus | BCB Olinda | colunas `desvio_padrao_*` e `amplitude_*` do Focus mensal |

## Limites de acesso (verificados em 2026-10-14)

- **ANBIMA** só serve gratuitamente cerca de **um mês** para trás (ETTJ desde
  ~21 dias úteis; arquivos `msAAMMDD.txt` idem). O histórico exige o ANBIMA
  Data. Por isso `anbima.coletar()` acumula: rodar `python -m mercado.lista2`
  ao menos a cada três semanas mantém a série sem buracos a partir de
  2026-09-14.
- **ANBIMA Data** (histórico da ETTJ): a API do portal exige login em todas
  as rotas. Substituída pela B3, que reproduz a ETTJ (ver validação abaixo).
- **B3, página de taxas referenciais**: erro 524 para datas antigas. O que
  funciona é o arquivo diário **TaxaSwap** da "pesquisa por pregão"
  (`b3_taxas.py`), com histórico desde jan/2001. Até out/2002 o layout é mais
  curto (taxa com 12 dígitos); o parser lê os dois.
- **Calendário futuro do Copom**: vem do serviço que alimenta a página de
  calendário do BCB (agenda "Reuniões do Copom"). O arquivo manual
  `dados/mercado/copom_agenda_futura.csv` continua aceito como complemento.

## Curvas da B3 (fonte principal)

`TaxaSwap.txt` traz as curvas que a B3 usa para precificar swaps. Usamos
PRE (DI×Pré), DIC (DI×IPCA), TPR (LTN) e TIC (NTN-B), reduzidas a vértices
padrão por interpolação *flat forward* base 252, sem extrapolação. Inflação
implícita em duas versões: de títulos (TPR × TIC, mesmo emissor) e de swaps
(PRE × DIC). Também saem DI×Pré em 3m, 6m, 1, 2, 3, 5 e 10 anos e a
inclinação (5a − 3m e 2a − 3m).

Validação contra a ETTJ oficial na sobreposição (21 dias): a implícita de
títulos em 5 anos difere 0,013 p.p. na média, correlação 0,998; nominal e
real em 2 a 10 anos ficam dentro de ±0,08 p.p. A versão por swaps diverge na
ponta curta da curva real (o cupom de IPCA curto carrega a sazonalidade do
índice) e por isso não é a série principal.

`breakeven.csv` (rival do Bloco 3) usa a implícita de títulos da B3 em 5
anos; dias sem ela usam o Tesouro Direto (coluna `fonte`).

## Inflação implícita pelo Tesouro Direto (fonte secundária)

Taxa média de compra e venda por título-dia; títulos com menos de 6 meses
para o vencimento saem (taxa espúria perto de zero). Zero-cupom (LTN,
NTN-B Principal) no próprio prazo; com cupom (NTN-F, NTN-B) na duration de
Macaulay. Interpolação linear em 1, 2, 3, 5 e 10 anos úteis, sem
extrapolação. Implícita de Fisher: (1+nominal)/(1+real) − 1.

Validação na sobreposição com a ETTJ oficial (21 dias, set–out/2026): diferença
média abaixo de 0,09 p.p. em 3 e 5 anos, correlação diária de 0,95 a 0,99
(`dados/mercado/validacao_td_vs_anbima.csv`).

Horizonte de 5 anos: ancoragem de médio prazo e cobertura de 100% dos dias
desde 2010 no Tesouro Direto; o de 2 anos tem buracos em 2020–2022.

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

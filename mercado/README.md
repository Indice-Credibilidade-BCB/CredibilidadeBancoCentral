# `mercado/` — Séries de mercado (Etapa 0)

Âncoras de **comportamento revelado** para a validação independente do índice
(Bloco 3 do desenho): "preço é percepção sem retórica".

| Arquivo | O que faz |
|---|---|
| `scrappingDI.py` | Coleta da curva de Swap DI. |
| `../dados/mercado/SwapDI.csv` | Série coletada (numérica, versionada). |

## A fazer (Bloco 3)

- **Breakeven de inflação**: ETTJ da ANBIMA a partir de **LTN/NTN-F** para a
  perna nominal — não Swap DI PRE, para preservar o cancelamento do risco de
  crédito do mesmo emissor — contra a curva real de NTN-B. Preferir prazos de
  **2 anos ou mais**: a defasagem de ~2 meses na indexação ao IPCA da NTN-B
  distorce a ponta curta. A decomposição de Fisher captura expectativa +
  prêmio de risco de inflação + prêmio de liquidez, não expectativa pura —
  registrar isso na leitura dos resultados.
- **CDS soberano** e **inclinação da estrutura a termo**.
- **Surpresa de inflação 12m** (IPCA realizado − mediana do Focus na data):
  insumo dos testes anti-vazamento T2 e T4 do índice.

## Independência dos blocos

Estas séries ficam **isoladas no Bloco 3**, como validação genuinamente fora
da amostra. Os termos de inflação dos Blocos 1–2 usam IPCA realizado defasado
e medianas do Focus. Alimentar breakeven na estimação do Bloco 2 destruiria a
independência do Bloco 3.

Séries numéricas públicas podem ser versionadas em `dados/mercado/`
(liberado no `.gitignore`) — não contêm texto de terceiros.

# `validacao/` — Kalman e encompassing (Etapa 4 → Paper 1)

Vazio por enquanto. **Não depende do índice LLM** e pode ser prototipado já.

## Bloco 2 — espaço de estados

$$\pi^{Focus}_t = C_t\,\pi^{*}_t + (1-C_t)\,\pi_{t-1} + \eta_t, \qquad C_t = C_{t-1} + \nu_t$$

Regressão de parâmetro variável no tempo; produz $\hat{C}^{KF}_t$ usando só
Focus, meta e inflação defasada. Cuidados registrados no desenho:

- **Identificação fraca perto da meta**: quando $\pi_{t-1} \approx \pi^{*}_t$ o
  regressor tende a zero e o filtro se recosta no prior. O índice é menos
  informativo nos "bons tempos" — não é ruído, é falta de identificação.
- **Domínio**: usar estado latente irrestrito $x_t$ com $C_t = \Lambda(x_t)$
  (logística), não truncar.

## Bloco 3 — encompassing

$$\hat{C}^{KF}_t = a + b_1\,\hat{C}^{LLM}_t + b_2\,\hat{C}^{rival}_t + u_t$$

Índice validado se $b_1$ segue significativo com cada rival incluído. Rivais:
de Mendonça (2007), dispersão do Focus, Dincer-Eichengreen-Geraats,
breakeven/CDS. Erro Newey-West. Como o latente e parte dos rivais derivam do
Focus, as âncoras decisivas são a **institucional** e a **de mercado**.

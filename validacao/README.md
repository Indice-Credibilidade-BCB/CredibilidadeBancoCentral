# `validacao/` — validade de construto do índice (artigo de medição)

Tudo o que o artigo usa para defender o índice depois de construído: latente
do Kalman, rivais, encompassing (7.4), bateria convergente, discriminante e
preditiva (7.1–7.3), estudo de eventos (8) e as figuras.

```
painel.py          painel mensal: Focus, IPCA, meta e banda, Selic e o índice LLM
econometria.py     MQO com erro HAC e regra de Newey-West
kalman.py          latente: TVP com elo logístico (EKF + suavizador RTS + MV)
rivais.py          de Mendonça 2007/2009, dispersão do Focus, DEG e mercado
encompassing.py    tabelas por rival, veredito, banda V-max × V-min (D12)
pipeline.py        painel -> Kalman -> rivais -> encompassing
construto.py       7.1 convergente, 7.2 discriminante, 7.3 preditiva
eventos.py         8: Copom (surpresa do swap DI×Pré 3m) e eventos institucionais
artigo.py          orquestra tudo -> dados/derivados/validacao/artigo/
figuras_artigo.py  figuras do artigo -> dados/derivados/validacao/artigo/figuras/
tests/             testes sintéticos (sem rede)
```

Rodar da **raiz do repositório** (usa `mercado` e `llm`):

```bash
python -m mercado.bcb                 # séries do BCB em dados/macro/ (cache)
python -m validacao.artigo            # bateria completa + relatório + figuras
python -m validacao.figuras_artigo    # só as figuras
python -m pytest validacao/tests -q
```

Especificações e critérios de aprovação foram registrados **antes** de rodar
(docs/local, seção 4.2.17); os resultados ficam em `relatorio.md` e
`veredictos.json`.

## Latente (Kalman)

$$\pi^{Focus}_t - \pi_{t-1} = \Lambda(x_t)\,(\pi^*_t - \pi_{t-1}) + \eta_t,\qquad x_t = x_{t-1} + \nu_t,\qquad C_t=\Lambda(x_t)$$

Regressão de parâmetro variável no tempo em que o regressor é a distância
meta−inflação; $\sigma_\eta,\sigma_\nu$ por máxima verossimilhança (EKF).
Perto da meta ($\pi_{t-1}\approx\pi^*_t$) o ganho colapsa e o filtro segue o
prior; o pipeline reporta a fração desses meses.

## Rivais e encompassing

$$\hat{C}^{KF}_t = a + b_1\,\hat{C}^{LLM}_t + b_2\,\hat{C}^{rival}_t + u_t$$

HAC, em nível e em primeiras diferenças. V-min é limite inferior, não veto
(D12 revisada).

| rival | origem |
|---|---|
| de Mendonça (2007, 2009), dispersão do Focus | calculados do painel |
| Dincer-Eichengreen-Geraats | `dados/macro/deg_brasil.csv` (`ano,valor`, preenchido à mão; pulado se faltar) |
| breakeven 5 anos | `dados/mercado/breakeven.csv` (ver `mercado/README.md`) |
| inclinação DI×Pré 5a − 3m | `dados/mercado/curvas_b3_diario.csv` (sem sinal orientado) |
| CDS 5 anos, EMBI+ | **só** `dados/terceiros/lista1/{cds,embi}.csv`, fora do Git |

CDS e EMBI+ são dados de fornecedor com licença que não permite
redistribuição. Ficam fora do repositório e saem dos CSVs gravados
(`rivais.csv`, `painel_construto.csv`); só os coeficientes estimados com eles
aparecem nas tabelas de resultado. Sem esses arquivos a bateria roda com os
rivais públicos e diz isso no relatório.

## Estudo de eventos

Copom: Δ = média de D1 em D+1..D+k menos D−k..D−1 (o dia D fica fora),
regredido na surpresa do swap DI×Pré 3m de D−1 a D+1, em bps, erro HC1.
Eventos institucionais (exploratório): Δ em ±30 dias para D1, D2 e D3,
comparado à distribuição placebo de todas as datas a cada 7 dias.

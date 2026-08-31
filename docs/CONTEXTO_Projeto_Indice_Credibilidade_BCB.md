# Projeto de Pesquisa — Índice de Credibilidade do Banco Central do Brasil via LLM

> **Documento de contexto/memória.** Alimenta um Projeto do Claude para que qualquer
> instância retome o trabalho com o estado completo: objetivo, decisões já tomadas,
> arquitetura matemática, ressalvas metodológicas, escolhas de modelo e o que ainda
> está em aberto. Leia por inteiro antes de propor qualquer coisa.

---

## 0. Convenções (importante)

- **BC / BCB = Banco Central do Brasil.** Nunca o Fed. Quando for preciso citar o banco central dos EUA, escreve-se **"Fed"** por extenso.
- Registro **acadêmico**, econometria aplicada / macro monetária, foco no **Brasil**.
- Contexto institucional: pesquisa de graduação (Iniciação Científica) no âmbito da **FEA Pública / FEA-USP**.
- Plano de publicação em **dois papers** (ver Seções 5 e 10).

---

## 1. Objetivo do projeto

Construir um **índice de credibilidade do BCB baseado em LLM** e testá-lo em duas frentes:

1. **Validade** — o índice rastreia a credibilidade latente implícita nas expectativas e nos preços de mercado?
2. **Utilidade** — o índice explica a **heterogeneidade na transmissão** de choques de política monetária sobre inflação e produto, superando os proxies tradicionais?

Lógica: se rastreia a credibilidade latente, é **válido**; se ainda melhora a explicação da transmissão, é **útil**.

---

## 2. Pergunta de pesquisa

> *Um índice de credibilidade extraído por LLM da percepção de terceiros sobre o BCB (i) rastreia a credibilidade latente implícita nas expectativas e nos preços de mercado e (ii) explica a heterogeneidade na transmissão de choques de política monetária sobre inflação e produto, superando os proxies tradicionais?*

---

## 3. Fundamentação conceitual

**Credibilidade = peso de ancoragem** $C_t \in [0,1]$: a fração que os agentes atribuem à meta ao formar expectativas de inflação, contra $(1-C_t)$ atribuída à inflação passada (Bomfim & Rudebusch, 2000; estrutura híbrida forward/backward de Galí & Gertler, 1999).

**Distinção central (correção conceitual chave do projeto):**
- **Credibilidade-resposta** — o quanto os agentes *acreditam*. É o que se quer medir. Vive em **notícias, research, preços e surveys** (lado da audiência).
- **Esforço de sinalização** — o quanto o BC *tenta* ser crível. Vive na comunicação oficial (lado do emissor).

> Credibilidade é atribuída pela **audiência**, não emitida pela fonte. Por isso o índice **não** pode ser extraído da comunicação do próprio BCB (mediria assertividade de comunicação, não crença). Essa foi uma correção explícita de um desenho anterior que lia atas/comunicados do Copom.

Requisitos de design: (i) fonte na audiência; (ii) não construir a partir das próprias expectativas de inflação (circularidade); (iii) ser *real-time* (sem look-ahead) e robusto à troca de modelo de linguagem.

---

## 4. Arquitetura do índice

### 4.1 Fonte e escopo (DEFINIDO)
- **Índice de credibilidade percebida $\hat{C}^{LLM}_t$**: pontuar, via LLM, **corpus de terceiros sobre o BCB** — imprensa econômica (Valor, Folha, Estadão, Reuters/Bloomberg), *research* de bancos/gestoras e, se acessível, redes.
- Dimensões **de percepção** (não de emissão): o texto trata a meta como provável de ser cumprida? Expressa confiança/ceticismo quanto à condução? Atribui autonomia efetiva ou subordinação política?
- **Índice de sinalização $\hat{S}^{LLM}_t$** (variável explicativa, opcional): pontua a comunicação oficial do Copom em consistência com guidance anterior, especificidade do forward guidance e reconhecimento de desvios. **Não mede credibilidade; mede esforço.** Usado para estimar o repasse do esforço à credibilidade percebida: $\hat{C}^{LLM}_t = c + d\,\hat{S}^{LLM}_t + \text{controles} + \omega_t$.

### 4.2 Arquitetura interna do LLM (⚠️ EM ABERTO — próximo passo)
Ainda **não definida**. A decidir: dimensões exatas e escala; esquema de anotação; modelo(s) de linguagem; engenharia de prompts; tratamento de *look-ahead* e de *viés de veículo*; pipeline de agregação para série temporal. **É o gargalo do caminho crítico.**

### 4.3 Validação independente (DEFINIDO)
Ancorar não em mais texto, mas em **comportamento revelado**: *breakeven* de inflação (NTN-B vs. prefixados), CDS soberano, inclinação da estrutura a termo — além das expectativas do Focus. "Preço é percepção sem retórica."

---

## 5. Sistema de equações

### Bloco 1 — Formação de expectativas (núcleo)
$$\tilde{E}_t[\pi_{t+1}] = C_t\,\pi^{*}_t + (1-C_t)\,\pi_{t-1}$$
Combinação convexa: peso $C_t$ na meta (forward), $(1-C_t)$ na inflação defasada (adaptativo). $\tilde{E}$ = expectativa subjetiva; $\pi^{*}_t$ = meta vigente (indexada em $t$: 4,5% → 3% → meta contínua desde 2025); $\pi_{t-1}$ = IPCA 12m defasado.

### Bloco 2 — Validação por espaço de estados (filtro de Kalman)
$$\pi^{Focus}_t = C_t\,\pi^{*}_t + (1-C_t)\,\pi_{t-1} + \eta_t, \qquad \eta_t\sim N(0,\sigma^2_\eta)$$
$$C_t = C_{t-1} + \nu_t, \qquad \nu_t\sim N(0,\sigma^2_\nu)$$
Regressão de parâmetro variável no tempo; produz o estado latente $\hat{C}^{KF}_t$ **sem usar o índice LLM** (usa só Focus, meta e inflação defasada — logo, pode ser prototipada antes do índice existir). O latente é uma medida do **lado da audiência** (Focus = percepção de profissionais).

### Bloco 3 — Encompassing (validação do índice)
$$\hat{C}^{KF}_t = a + b_1\,\hat{C}^{LLM}_t + b_2\,\hat{C}^{rival}_t + u_t$$
Índice validado se $b_1$ permanece significativo com cada rival incluído. Rivais: de Mendonça (2007) e dispersão do Focus (ambos derivados do Focus), Dincer-Eichengreen-Geraats (institucional), *breakeven*/CDS (mercado). Erro com Newey-West.

### Bloco 4 — Modelo estrutural Novo-Keynesiano (3 equações)
**Curva de Phillips (preços livres, com repasse cambial):**
$$\pi^{L}_t = \beta\,\tilde{E}_t[\pi_{t+1}] + \kappa\,\tilde{y}_t + \theta\,\Delta e_t + \varepsilon^{\pi}_t$$
Substituindo (1), o coeficiente sobre $\pi_{t-1}$ vira $\beta(1-C_t)$ → **persistência inflacionária endógena à credibilidade** (predição testável central).

**Curva IS (Euler linearizada):**
$$\tilde{y}_t = E_t[\tilde{y}_{t+1}] - \sigma^{-1}\big(i_t - \tilde{E}_t[\pi_{t+1}] - r^{*}_t\big) + u^{y}_t$$

**Regra de Taylor (forward-looking com suavização):**
$$i_t = \rho\,i_{t-1} + (1-\rho)\big[r^{*}_t + \pi^{*}_t + \phi_\pi(\tilde{E}_t[\pi_{t+1}] - \pi^{*}_t) + \phi_y\,\tilde{y}_t\big] + v_t$$
$\beta$≈0,99; $\kappa$ = inclinação (Calvo); $\tilde{y}$ = hiato (IBC-Br); $\theta$ = repasse cambial; $\sigma^{-1}$ = elast. sub. intertemporal; $r^{*}$ = juro neutro; $\rho$ = suavização (0,7–0,9); $\phi_\pi>1$ (princípio de Taylor).

### Bloco 5 — Choque identificado (Kuttner via DI)
$$\varepsilon^{MP}_t = i^{DI}_{\tau+\Delta} - i^{DI}_{\tau-\Delta}$$
Surpresa em janela estreita ao redor do anúncio do Copom, no DI futuro curto (B3).

### Bloco 6 — Projeções locais com dependência de estado (Jordà)
$$z_{t+h} - z_{t-1} = \alpha_h + \beta_h\,\varepsilon^{MP}_t + \gamma_h\big(\varepsilon^{MP}_t \times \hat{C}^{LLM}_{t-1}\big) + \delta_h\,\hat{C}^{LLM}_{t-1} + \Gamma_h X_t + e_{t+h}$$
Para $z\in\{\text{IPCA},\text{IBC-Br}\}$. **$\gamma_h$ é o objeto de interesse**: amplificação/atenuação da transmissão por unidade de credibilidade. $\delta_h$ obrigatório (efeito de nível). Índice **defasado** (dependência de estado, não causalidade estrita). Erro Newey-West.

### Fechamento — Contrafactual de política
IRFs do sistema (4)–(6) com $C$ no p25 vs. p75 → **quantos bps de Selic a credibilidade "economiza" para a mesma desinflação** (razão de sacrifício decrescente em $C$).

---

## 6. Notas metodológicas / armadilhas conhecidas

1. **Identificação fraca perto da meta** — no Bloco 2, quando $\pi_{t-1}\approx\pi^{*}_t$ o regressor $\to 0$ e $C_t$ é pouco identificado; o filtro recosta-se no prior. Índice menos informativo nos "bons tempos".
2. **Domínio de $C_t$** — pode escapar de $[0,1]$; usar estado latente irrestrito $x_t$ com $C_t=\Lambda(x_t)$ (logística).
3. **Validação quase tautológica** — latente e parte dos rivais derivam do Focus; âncoras decisivas devem ser **institucional e de mercado**.
4. **Timing do Copom** — anúncio **após** o fechamento da B3 → sem janela intradiária estrita; usar D−1→D+1; extrair a surpresa ajustando pelo CDI médio do contrato (não diferença bruta).
5. **Descompasso de frequência** — choque de reunião (~8/ano) vs. dados mensais; padronizar em frequência mensal.
6. **Viés de veículo** — notícia confunde *pessimismo macroeconômico* com *descrença na autoridade*; prompt e validação manual precisam separar. Research de sell-side tem incentivos próprios → ancorar em preços.
7. **Look-ahead / circularidade** — LLM de fronteira "sabe" desfechos passados; mitigar com prompts restritos, encoder fine-tuned de cutoff conhecido. Circularidade resolvida por construção (índice de uma fonte, validação de outra).
8. **Ponto Fiocca (ver Seção 8)** — controlar indexação da dívida em $X_t$ para $\gamma_h$ não absorver esse canal.

---

## 7. Escolha do modelo (justificativa registrada)

Três famílias distintas: **FRB/US** (modelo grande do Fed); **modelos do BCB** (não há "um" oficial — há suíte; fundacional é o **Modelo de Pequeno Porte de Bogdanski, Tombini & Werlang, 2000**; DSGE **SAMBA**, de Castro et al. 2015); e o **NK de 3 equações** (Galí, 2015) — o adotado.

**Por que o de 3 equações:**
- É a **linhagem do próprio modelo de pequeno porte do BCB** (IS, Phillips com repasse cambial, Taylor). O $\theta\,\Delta e_t$ é a adaptação brasileira. Não é um modelo "não-brasileiro".
- O índice é o **objeto**; o modelo é o **veículo**. Num modelo de 3 equações, $C_t$ entra em **um** parâmetro identificado e o canal de credibilidade é isolável. Em FRB/US ou SAMBA ficaria soterrado.
- **Estimabilidade** com amostra de um país (~2000–2026): modelo grande seria calibrado, não estimado.
- Permite cruzar limpo o contrafactual estrutural com o $\gamma_h$ das projeções locais.

**Robustez opcional (fora do caminho crítico):** FRB/US como segundo modelo — natural porque tem seletor de expectativas (VAR-based vs. model-consistent), e **Bomfim & Rudebusch (2000) já modelaram credibilidade imperfeita nesse modelo** como mistura dos dois modos → análogo direto do nosso $C_t$. Ressalva: modelos não são evidência independente (dados/esqueleto compartilhados); recalibrar FRB/US p/ Brasil é custoso. Deixar para depois do Paper 2.

---

## 8. Ponto Fiocca (WP 30 / MADE, 2025)

Fiocca ("A anomalia na política monetária do Brasil") argumenta que os juros reais brasileiros são anômalos (6–8× a média de países com RMI) porque a **dívida pública indexada à Selic enfraquece os canais de transmissão** (efeito riqueza fraco, erosão do canal de crédito, canal de renda perverso). Usa uma **regra de Taylor aumentada**, não o FRB/US.

**Consequência para nós:** é uma explicação **concorrente/complementar** para a heterogeneidade de transmissão. Risco de $\gamma_h$ capturar o "efeito-Fiocca". **Mitigação:** incluir em $X_t$ (Bloco 6) uma proxy da **fração da dívida indexada à Selic** (ou sua interação com o choque).

---

## 9. Dados e séries necessárias

- **Corpus de terceiros** (imprensa + research) com metadados temporais.
- **Focus**: mediana e dispersão das expectativas de inflação (BCB/SGS).
- **Mercado**: breakeven NTN-B vs. prefixados, CDS soberano, estrutura a termo (ANBIMA/B3).
- **Macro**: IPCA livres, hiato (IBC-Br vs. tendência), Selic, DI futuro (B3), série de metas, fração da dívida indexada à Selic (Tesouro).
- Fontes: SGS/BCB, ANBIMA, B3, Tesouro Nacional.

---

## 10. Etapas de execução (sem prazos)

- **Etapa 0 — Dados e corpus.** Independe do índice; começar já, em paralelo à Etapa 1.
- **Etapa 1 — Arquitetura do índice LLM** *(EM ABERTO; gargalo)*.
- **Etapa 2 — Piloto de anotação** *(gate)*. ~30–50 itens, κ de Cohen; **se κ > 0,6 prossegue, senão volta à Etapa 1**.
- **Etapa 3 — Índice em escala.** Séries $\hat{C}^{LLM}$ e (opcional) $\hat{S}^{LLM}$ com bandas.
- **Etapa 4 — Validação.** Kalman + encompassing → **Paper 1** (nota de construção e validação). Infra de Kalman pode ser feita antes do índice.
- **Etapa 5 — Modelo estrutural NK.** GMM/bayesiano; testar persistência endógena.
- **Etapa 6 — Transmissão / projeções locais.** $\gamma_h$ p/ IPCA e IBC-Br; controle de indexação da dívida.
- **Etapa 7 — Contrafactuais.** Razão de sacrifício / resultado em bps → **Paper 2**.
- **Etapa 8 — Redação e disseminação.**

**Caminho crítico:** 1 → 2 → 3 → 4 → 5/6 → 7. Etapas 5–6 podem ser prototipadas com placeholder antes do índice real.

---

## 11. Referências (verificadas, com DOI)

- BARRO, R. J.; GORDON, D. B. (1983). *Journal of Monetary Economics*, 12(1), 101–121. DOI: 10.1016/0304-3932(83)90051-X
- BERNANKE, B.; LAUBACH, T.; MISHKIN, F.; POSEN, A. (1999). *Inflation Targeting*. Princeton U. Press. ISBN 978-0-691-05955-6
- BIANCHI, F.; MELOSI, L. (2022). *Inflation as a Fiscal Limit*. Jackson Hole / FRB Chicago WP 2022-37. DOI: 10.2139/ssrn.4205158
- BIANCHI, F.; FACCINI, R.; MELOSI, L. (2023). *Quarterly Journal of Economics*, 138(4), 2127–2179.
- BLINDER, A. S. (1998). *Central Banking in Theory and Practice*. MIT Press. ISBN 978-0-262-02439-6
- BLINDER, A.; EHRMANN, M.; FRATZSCHER, M.; DE HAAN, J.; JANSEN, D.-J. (2008). *Journal of Economic Literature*, 46(4), 910–945. DOI: 10.1257/jel.46.4.910
- BOGDANSKI, J.; TOMBINI, A.; WERLANG, S. (2000). *Implementing Inflation Targeting in Brazil*. BCB Working Paper Series nº 1.
- BOMFIM, A. N.; RUDEBUSCH, G. D. (2000). *Journal of Money, Credit and Banking*, 32(4), 707–721.
- COIBION, O.; GORODNICHENKO, Y. (2015). *American Economic Review*, 105(8), 2644–2678. DOI: 10.1257/aer.20110306
- DE CASTRO, M. R. et al. (2015). *SAMBA: Stochastic Analytical Model with a Bayesian Approach*. BCB.
- DE MENDONÇA, H. F. (2007). *Applied Economics*, 39(20), 2599–2615. DOI: 10.1080/00036840600707324
- DE MENDONÇA, H. F.; GUIMARÃES E SOUZA, G. J. (2009). *Economic Modelling*, 26(6), 1228–1238. DOI: 10.1016/j.econmod.2009.05.010
- DINCER, N.; EICHENGREEN, B. (2014). *International Journal of Central Banking*, 10(1), 189–259.
- DINCER, N.; EICHENGREEN, B.; GERAATS, P. (2022). *International Journal of Central Banking*, 18(1), 331–348.
- FIOCCA, D. (2025). *A anomalia na política monetária do Brasil*. Made/USP, Working Paper nº 30.
- GABAIX, X. (2020). *American Economic Review*, 110(8), 2271–2327. DOI: 10.1257/aer.20162005
- GALÍ, J. (2015). *Monetary Policy, Inflation, and the Business Cycle*. 2ª ed. Princeton U. Press. ISBN 978-0-691-16478-6
- GALÍ, J.; GERTLER, M. (1999). *Journal of Monetary Economics*, 44(2), 195–222. DOI: 10.1016/S0304-3932(99)00023-9
- HANSEN, S.; McMAHON, M. (2016). *Journal of International Economics*, 99(S1), S114–S133. DOI: 10.1016/j.jinteco.2015.12.008
- JORDÀ, Ò. (2005). *American Economic Review*, 95(1), 161–182. DOI: 10.1257/0002828053828518
- KUTTNER, K. N. (2001). *Journal of Monetary Economics*, 47(3), 523–544. DOI: 10.1016/S0304-3932(01)00055-1
- KYDLAND, F.; PRESCOTT, E. (1977). *Journal of Political Economy*, 85(3), 473–491. DOI: 10.1086/260580
- LAUBACH, T.; WILLIAMS, J. (2003). *Review of Economics and Statistics*, 85(4), 1063–1070.
- LEEPER, E. M. (1991). *Journal of Monetary Economics*, 27(1), 129–147. DOI: 10.1016/0304-3932(91)90007-B
- PLAGBORG-MØLLER, M.; WOLF, C. (2021). *Econometrica*, 89(2), 955–980. DOI: 10.3982/ECTA17813
- ROGOFF, K. (1985). *Quarterly Journal of Economics*, 100(4), 1169–1189. DOI: 10.2307/1885679
- SILVA, T. C.; MORIYA, K.; VEYRUNE, R. (2025). *From Text to Quantified Insights*. IMF WP 2025/109. DOI: 10.5089/9798229013802.001
- TAYLOR, J. B. (1993). *Carnegie-Rochester Conf. Series*, 39, 195–214. DOI: 10.1016/0167-2231(93)90009-L
- WOODFORD, M. (2003). *Interest and Prices*. Princeton U. Press. ISBN 978-0-691-01049-6

> DOIs verificados na fonte. Sem DOI: os dois do *International Journal of Central Banking* (o periódico não atribui DOI); Bomfim-Rudebusch, Bianchi-Faccini-Melosi e Laubach-Williams (citados por coordenadas completas); e os working papers do BCB/Made (identificados por número de série).

---

## 12. Estado atual e próximo passo

- **Concluído:** pergunta de pesquisa; fundamentação conceitual (incl. correção resposta vs. sinalização); fonte do índice; sistema de equações (Blocos 1–6 + fechamento); notas metodológicas; escolha e justificativa do modelo; incorporação do ponto Fiocca; etapas de execução. Existe um PDF de desenho de pesquisa (Seções 1–4 + referências).
- **Em aberto / próximo passo:** **Etapa 1 — arquitetura interna do índice LLM** (Seção 4.2). É o gargalo. Começar por aqui, com a Etapa 0 (dados) rodando em paralelo.

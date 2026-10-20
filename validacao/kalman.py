# -*- coding: utf-8 -*-
r"""Bloco 2 — credibilidade latente por espaço de estados (filtro de Kalman).

Modelo (Seção 5, Bloco 2, com a correção de domínio da nota metodológica 2):

.. math::

    \pi^{Focus}_t - \pi_{t-1} = \Lambda(x_t)\,(\pi^*_t - \pi_{t-1}) + \eta_t,
    \qquad x_t = x_{t-1} + \nu_t,

com :math:`C_t = \Lambda(x_t) = 1/(1+e^{-x_t})`. Reescrito assim, é uma
regressão de coeficiente variável no tempo em que a variável dependente é
:math:`y_t = \pi^{Focus}_t - \pi_{t-1}` e o regressor é
:math:`d_t = \pi^*_t - \pi_{t-1}` — a distância entre meta e inflação
corrente. **Sem usar o índice LLM**: só Focus, meta e IPCA defasado.

Estimação: filtro de Kalman estendido (linearização de :math:`\Lambda` em
torno da previsão do estado), com :math:`\sigma_\eta` e :math:`\sigma_\nu`
escolhidos por máxima verossimilhança (aproximação gaussiana do EKF), e
suavizador de Rauch-Tung-Striebel para a série de dois lados.

Identificação fraca perto da meta (nota metodológica 1): quando
:math:`d_t \approx 0` o ganho de Kalman colapsa e o estado segue o prior. O
módulo devolve :math:`|d_t|` e a variância filtrada por período para que isso
seja **reportado como quantidade**, não escondido — mesma filosofia do
tratamento de vazamento no ``llm/``.

``link="identidade"`` roda o modelo linear (C irrestrito, Kalman exato) como
robustez: se as duas versões discordarem só onde o logístico satura, o
domínio importa; se discordarem no meio, algo está errado.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import optimize


def _logistica(x: np.ndarray | float) -> np.ndarray | float:
    return 1.0 / (1.0 + np.exp(-np.clip(x, -40.0, 40.0)))


def _dlogistica(x: np.ndarray | float) -> np.ndarray | float:
    s = _logistica(x)
    return s * (1.0 - s)


def _logit(c: float) -> float:
    c = min(max(c, 1e-6), 1 - 1e-6)
    return float(np.log(c / (1 - c)))


@dataclass
class SaidaFiltro:
    x_pred: np.ndarray
    P_pred: np.ndarray
    x_filt: np.ndarray
    P_filt: np.ndarray
    inovacao: np.ndarray
    F: np.ndarray
    ganho: np.ndarray
    loglik: float


class TVPCredibilidade:
    """Regressão de parâmetro variável no tempo com elo logístico (ou identidade).

    Parâmetros
    ----------
    link : "logistica" | "identidade"
    x0, P0 : média e variância do estado inicial. Padrão: prior difuso
        centrado em C=0,5 (x=0) com variância grande.
    """

    def __init__(self, link: str = "logistica", x0: float | None = None, P0: float = 10.0):
        if link not in ("logistica", "identidade"):
            raise ValueError("link deve ser 'logistica' ou 'identidade'")
        self.link = link
        self.x0 = (0.0 if link == "logistica" else 0.5) if x0 is None else float(x0)
        self.P0 = float(P0)
        self.sigma_eta: float | None = None
        self.sigma_nu: float | None = None
        self.resultado_otim: dict | None = None

    # ── elo ──────────────────────────────────────────────────────────────
    def g(self, x):
        return _logistica(x) if self.link == "logistica" else x

    def dg(self, x):
        return _dlogistica(x) if self.link == "logistica" else np.ones_like(np.asarray(x, float))

    # ── filtro ───────────────────────────────────────────────────────────
    def filtrar(self, y: np.ndarray, d: np.ndarray, sigma_eta: float, sigma_nu: float) -> SaidaFiltro:
        """EKF. Observações NaN em ``y`` são tratadas como faltantes (só predição)."""
        T = len(y)
        q, r = sigma_nu ** 2, sigma_eta ** 2
        x_pred = np.empty(T); P_pred = np.empty(T)
        x_filt = np.empty(T); P_filt = np.empty(T)
        inov = np.full(T, np.nan); Fs = np.full(T, np.nan); K = np.zeros(T)
        x, P = self.x0, self.P0
        ll = 0.0
        for t in range(T):
            # predição (passeio aleatório)
            xp, Pp = x, P + q
            x_pred[t], P_pred[t] = xp, Pp
            if np.isnan(y[t]) or np.isnan(d[t]):
                x, P = xp, Pp
            else:
                H = self.dg(xp) * d[t]
                yhat = self.g(xp) * d[t]
                v = y[t] - yhat
                F = H * Pp * H + r
                k = Pp * H / F
                x = xp + k * v
                P = (1.0 - k * H) * Pp
                inov[t], Fs[t], K[t] = v, F, k
                ll += -0.5 * (np.log(2 * np.pi) + np.log(F) + v * v / F)
            x_filt[t], P_filt[t] = x, P
        return SaidaFiltro(x_pred, P_pred, x_filt, P_filt, inov, Fs, K, float(ll))

    def suavizar(self, s: SaidaFiltro) -> tuple[np.ndarray, np.ndarray]:
        """Rauch-Tung-Striebel (transição identidade)."""
        T = len(s.x_filt)
        xs = s.x_filt.copy(); Ps = s.P_filt.copy()
        for t in range(T - 2, -1, -1):
            if s.P_pred[t + 1] <= 0:
                continue
            J = s.P_filt[t] / s.P_pred[t + 1]
            xs[t] = s.x_filt[t] + J * (xs[t + 1] - s.x_pred[t + 1])
            Ps[t] = s.P_filt[t] + J * J * (Ps[t + 1] - s.P_pred[t + 1])
        return xs, Ps

    # ── estimação ────────────────────────────────────────────────────────
    def estimar(self, y: np.ndarray, d: np.ndarray, chutes: tuple[tuple[float, float], ...] = (
            (0.5, 0.1), (0.3, 0.05), (1.0, 0.3), (0.2, 0.02))) -> "TVPCredibilidade":
        """Máxima verossimilhança em (log σ_η, log σ_ν), com vários chutes iniciais."""
        y = np.asarray(y, float); d = np.asarray(d, float)

        def neg_ll(theta):
            se, sn = np.exp(theta)
            if not (np.isfinite(se) and np.isfinite(sn)):
                return 1e12
            return -self.filtrar(y, d, se, sn).loglik

        melhor = None
        for se0, sn0 in chutes:
            r = optimize.minimize(neg_ll, x0=np.log([se0, sn0]), method="L-BFGS-B",
                                  bounds=[(np.log(1e-4), np.log(50.0))] * 2)
            if melhor is None or r.fun < melhor.fun:
                melhor = r
        self.sigma_eta, self.sigma_nu = map(float, np.exp(melhor.x))
        self.resultado_otim = {"loglik": -float(melhor.fun), "sucesso": bool(melhor.success),
                               "mensagem": str(melhor.message)}
        return self

    # ── conveniência ─────────────────────────────────────────────────────
    def ajustar(self, painel: pd.DataFrame, col_focus: str = "pi_focus", col_lag: str = "pi_lag",
                col_meta: str = "pi_star", estimar: bool = True) -> pd.DataFrame:
        """Roda tudo sobre o painel e devolve um DataFrame por mês.

        Colunas: y, d (regressor), x_filt/x_suav (estado), c_kf_filtrado,
        c_kf_suavizado, ep_filtrado/ep_suavizado (delta method), ganho,
        identificacao (=|d|), inovacao padronizada.
        """
        df = painel[[col_focus, col_lag, col_meta]].copy()
        y = (df[col_focus] - df[col_lag]).to_numpy(float)
        d = (df[col_meta] - df[col_lag]).to_numpy(float)
        if estimar or self.sigma_eta is None:
            self.estimar(y, d)
        s = self.filtrar(y, d, self.sigma_eta, self.sigma_nu)
        xs, Ps = self.suavizar(s)
        out = pd.DataFrame(index=painel.index)
        out["y"] = y; out["d"] = d
        out["x_filt"] = s.x_filt; out["x_suav"] = xs
        out["c_kf_filtrado"] = self.g(s.x_filt)
        out["c_kf_suavizado"] = self.g(xs)
        out["ep_filtrado"] = np.abs(self.dg(s.x_filt)) * np.sqrt(np.maximum(s.P_filt, 0))
        out["ep_suavizado"] = np.abs(self.dg(xs)) * np.sqrt(np.maximum(Ps, 0))
        out["ganho"] = s.ganho
        out["identificacao"] = np.abs(d)
        out["inovacao_padr"] = s.inovacao / np.sqrt(s.F)
        out.attrs["sigma_eta"] = self.sigma_eta
        out.attrs["sigma_nu"] = self.sigma_nu
        out.attrs["loglik"] = s.loglik
        out.attrs["link"] = self.link
        return out


def diagnostico_identificacao(saida: pd.DataFrame, limiar_pp: float = 1.0) -> dict:
    """Quanto da amostra está na zona de identificação fraca (|d_t| < limiar)?

    Devolve fração de meses fracos, ganho médio dentro/fora da zona e o
    erro-padrão médio do estado dentro/fora. Reportar junto da série.
    """
    fraco = saida["identificacao"] < limiar_pp
    return {
        "limiar_pp": limiar_pp,
        "frac_meses_fracos": float(fraco.mean()),
        "ganho_medio_fraco": float(saida.loc[fraco, "ganho"].abs().mean()) if fraco.any() else np.nan,
        "ganho_medio_forte": float(saida.loc[~fraco, "ganho"].abs().mean()) if (~fraco).any() else np.nan,
        "ep_medio_fraco": float(saida.loc[fraco, "ep_suavizado"].mean()) if fraco.any() else np.nan,
        "ep_medio_forte": float(saida.loc[~fraco, "ep_suavizado"].mean()) if (~fraco).any() else np.nan,
    }


def simular(T: int = 240, sigma_eta: float = 0.4, sigma_nu: float = 0.15, seed: int = 0,
            d_escala: float = 3.0) -> tuple[pd.DataFrame, np.ndarray]:
    """Gera um painel sintético (pi_focus, pi_lag, pi_star) com C_t conhecido.

    Usado nos testes: o filtro tem de recuperar a trajetória de C_t.
    ``d_escala`` controla a distância típica meta−inflação (identificação).
    """
    rng = np.random.default_rng(seed)
    x = np.cumsum(rng.normal(0, sigma_nu, T))
    c = _logistica(x)
    pi_star = np.full(T, 4.5)
    pi_lag = pi_star + d_escala * np.sin(np.linspace(0, 6 * np.pi, T)) + rng.normal(0, 0.5, T)
    pi_focus = c * pi_star + (1 - c) * pi_lag + rng.normal(0, sigma_eta, T)
    idx = pd.period_range("2002-01", periods=T, freq="M")
    painel = pd.DataFrame({"pi_focus": pi_focus, "pi_lag": pi_lag, "pi_star": pi_star}, index=idx)
    return painel, c

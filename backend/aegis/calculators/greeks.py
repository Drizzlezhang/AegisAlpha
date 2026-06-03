# ruff: noqa: N803, N806
# S, K, T are standard Black-Scholes notation (spot, strike, time).
"""Black-Scholes Greeks and implied volatility via Newton-Raphson.

Frozen at M1. Changes require owner review.
"""

import math
from typing import Literal

from aegis.calculators.models import GreeksResult


def _norm_pdf(x: float) -> float:
    """Standard normal probability density function."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def _norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function via math.erf."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _bs_price(
    option_type: Literal["call", "put"],
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> float:
    """Black-Scholes option price."""
    if T <= 0:
        if option_type == "call":
            return max(0.0, S - K)
        return max(0.0, K - S)

    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        return S * math.exp(-q * T) * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * math.exp(-q * T) * _norm_cdf(-d1)


def compute_greeks(
    option_type: Literal["call", "put"],
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    q: float = 0.0,
) -> GreeksResult:
    """Compute Black-Scholes Greeks for a European option.

    Args:
        option_type: "call" or "put".
        S: Spot price of the underlying.
        K: Strike price.
        T: Time to expiration in years.
        r: Risk-free interest rate (decimal, e.g. 0.05 for 5%).
        sigma: Volatility (decimal, e.g. 0.20 for 20%).
        q: Dividend yield (decimal, default 0.0).

    Returns:
        GreeksResult with delta, gamma, theta, vega, rho, implied_volatility.
    """
    if T < 1e-6:
        # T → 0 boundary: delta becomes step function, others → 0
        if option_type == "call":
            delta = 1.0 if S > K else (0.0 if S < K else 0.5)
        else:
            delta = -1.0 if S < K else (0.0 if S > K else -0.5)
        return GreeksResult(
            delta=delta,
            gamma=0.0,
            theta=0.0,
            vega=0.0,
            rho=0.0,
            implied_volatility=sigma,
        )

    sqrt_t = math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrt_t)
    d2 = d1 - sigma * sqrt_t

    pdf_d1 = _norm_pdf(d1)
    cdf_d1 = _norm_cdf(d1)
    cdf_d2 = _norm_cdf(d2)
    neg_cdf_d1 = _norm_cdf(-d1)
    neg_cdf_d2 = _norm_cdf(-d2)

    e_neg_qt = math.exp(-q * T)
    e_neg_rt = math.exp(-r * T)

    # Gamma (same for call and put)
    gamma = pdf_d1 * e_neg_qt / (S * sigma * sqrt_t)

    # Vega (same for call and put, scaled by 0.01 for 1% vol change)
    vega = S * e_neg_qt * pdf_d1 * sqrt_t * 0.01

    if option_type == "call":
        delta = e_neg_qt * cdf_d1
        theta = (
            -(S * pdf_d1 * sigma * e_neg_qt) / (2 * sqrt_t)
            - r * K * e_neg_rt * cdf_d2
            + q * S * e_neg_qt * cdf_d1
        )
        rho = K * T * e_neg_rt * cdf_d2 * 0.01
    else:
        delta = e_neg_qt * (cdf_d1 - 1)
        theta = (
            -(S * pdf_d1 * sigma * e_neg_qt) / (2 * sqrt_t)
            + r * K * e_neg_rt * neg_cdf_d2
            - q * S * e_neg_qt * neg_cdf_d1
        )
        rho = -K * T * e_neg_rt * neg_cdf_d2 * 0.01

    return GreeksResult(
        delta=delta,
        gamma=gamma,
        theta=theta,
        vega=vega,
        rho=rho,
        implied_volatility=sigma,
    )


def compute_implied_volatility(
    option_type: Literal["call", "put"],
    market_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float = 0.0,
    max_iter: int = 100,
    tolerance: float = 1e-6,
) -> float:
    """Compute implied volatility via Newton-Raphson iteration.

    Args:
        option_type: "call" or "put".
        market_price: Observed market price of the option.
        S: Spot price of the underlying.
        K: Strike price.
        T: Time to expiration in years.
        r: Risk-free interest rate (decimal).
        q: Dividend yield (decimal, default 0.0).
        max_iter: Maximum number of iterations (default 100).
        tolerance: Convergence tolerance (default 1e-6).

    Returns:
        Implied volatility as a decimal.

    Raises:
        ValueError: If the iteration fails to converge.
    """
    sigma = 0.3  # Initial guess

    for _ in range(max_iter):
        price = _bs_price(option_type, S, K, T, r, sigma, q)
        diff = price - market_price

        if abs(diff) < tolerance:
            return sigma

        # Vega (unscaled, for Newton step)
        if T < 1e-6:
            break
        sqrt_t = math.sqrt(T)
        d1 = (math.log(S / K) + (r - q + 0.5 * sigma * sigma) * T) / (sigma * sqrt_t)
        vega = S * math.exp(-q * T) * _norm_pdf(d1) * sqrt_t

        if abs(vega) < 1e-12:
            break

        sigma = sigma - diff / vega

        # Clamp to reasonable range
        sigma = max(0.001, min(sigma, 5.0))

    raise ValueError(
        f"Implied volatility did not converge after {max_iter} iterations. "
        f"Last sigma={sigma:.6f}, price diff={diff:.6f}"
    )

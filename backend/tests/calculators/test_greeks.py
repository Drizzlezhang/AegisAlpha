"""Tests for Black-Scholes Greeks calculator."""


import pytest

from aegis.calculators.greeks import compute_greeks, compute_implied_volatility

# ── Call option tests ──────────────────────────────────────────────

def test_greeks_call_atm():
    """ATM call: S=K=100, T=0.5, r=0.05, sigma=0.20."""
    result = compute_greeks("call", S=100.0, K=100.0, T=0.5, r=0.05, sigma=0.20)

    # ATM call delta ≈ 0.5 + small drift
    assert result.delta == pytest.approx(0.597, rel=1e-2)
    # Gamma positive
    assert result.gamma > 0
    assert result.gamma == pytest.approx(0.0274, rel=1e-2)
    # Theta negative (time decay)
    assert result.theta < 0
    # Vega positive
    assert result.vega > 0
    # Rho positive for call
    assert result.rho > 0
    # implied_volatility equals input sigma
    assert result.implied_volatility == 0.20


def test_greeks_call_deep_itm():
    """Deep ITM call: S=150, K=100, T=0.5, r=0.05, sigma=0.20."""
    result = compute_greeks("call", S=150.0, K=100.0, T=0.5, r=0.05, sigma=0.20)

    # Deep ITM call delta ≈ 1.0
    assert result.delta == pytest.approx(1.0, rel=1e-2)
    # Gamma near 0 for deep ITM
    assert result.gamma < 0.01
    # Theta negative
    assert result.theta < 0
    # Vega small for deep ITM
    assert result.vega < 1.0
    # Rho positive
    assert result.rho > 0


def test_greeks_call_deep_otm():
    """Deep OTM call: S=50, K=100, T=0.5, r=0.05, sigma=0.20."""
    result = compute_greeks("call", S=50.0, K=100.0, T=0.5, r=0.05, sigma=0.20)

    # Deep OTM call delta ≈ 0
    assert result.delta == pytest.approx(0.0, abs=0.05)
    # Gamma near 0 for deep OTM
    assert result.gamma < 0.01
    # Theta near 0
    assert abs(result.theta) < 0.5
    # Vega near 0
    assert result.vega < 1.0
    # Rho near 0
    assert abs(result.rho) < 0.5


# ── Put option tests ────────────────────────────────────────────────

def test_greeks_put_atm():
    """ATM put: S=K=100, T=0.5, r=0.05, sigma=0.20."""
    result = compute_greeks("put", S=100.0, K=100.0, T=0.5, r=0.05, sigma=0.20)

    # ATM put delta ≈ -0.5 + small drift
    assert result.delta == pytest.approx(-0.403, rel=1e-2)
    # Gamma positive (same as call)
    assert result.gamma > 0
    assert result.gamma == pytest.approx(0.0274, rel=1e-2)
    # Theta negative
    assert result.theta < 0
    # Vega positive
    assert result.vega > 0
    # Rho negative for put
    assert result.rho < 0


def test_greeks_put_deep_itm():
    """Deep ITM put: S=50, K=100, T=0.5, r=0.05, sigma=0.20."""
    result = compute_greeks("put", S=50.0, K=100.0, T=0.5, r=0.05, sigma=0.20)

    # Deep ITM put delta ≈ -1.0
    assert result.delta == pytest.approx(-1.0, rel=1e-2)
    # Gamma near 0
    assert result.gamma < 0.01
    # Theta can be positive for deep ITM puts (r*K component dominates)
    # Vega small
    assert result.vega < 1.0
    # Rho negative
    assert result.rho < 0


def test_greeks_put_deep_otm():
    """Deep OTM put: S=150, K=100, T=0.5, r=0.05, sigma=0.20."""
    result = compute_greeks("put", S=150.0, K=100.0, T=0.5, r=0.05, sigma=0.20)

    # Deep OTM put delta ≈ 0
    assert result.delta == pytest.approx(0.0, abs=0.05)
    # Gamma near 0
    assert result.gamma < 0.01
    # Theta near 0
    assert abs(result.theta) < 0.5
    # Vega near 0
    assert result.vega < 1.0
    # Rho near 0
    assert abs(result.rho) < 0.5


# ── Boundary cases ──────────────────────────────────────────────────

def test_greeks_t_near_zero():
    """T → 0: delta becomes step function, others → 0."""
    result = compute_greeks("call", S=105.0, K=100.0, T=1e-7, r=0.05, sigma=0.20)

    assert result.delta == 1.0  # ITM → 1
    assert result.gamma == 0.0
    assert result.theta == 0.0
    assert result.vega == 0.0
    assert result.rho == 0.0


def test_greeks_t_near_zero_otm():
    """T → 0 OTM: delta → 0."""
    result = compute_greeks("put", S=105.0, K=100.0, T=1e-7, r=0.05, sigma=0.20)

    assert result.delta == 0.0  # OTM put → 0
    assert result.gamma == 0.0


def test_greeks_put_call_parity_gamma():
    """Gamma should be identical for call and put with same parameters."""
    call = compute_greeks("call", S=100.0, K=100.0, T=0.5, r=0.05, sigma=0.20)
    put = compute_greeks("put", S=100.0, K=100.0, T=0.5, r=0.05, sigma=0.20)

    assert call.gamma == pytest.approx(put.gamma)
    assert call.vega == pytest.approx(put.vega)


# ── Implied volatility tests ────────────────────────────────────────

def test_implied_volatility_call():
    """IV should recover the input sigma from a BS price."""
    sigma_true = 0.25
    # Compute price using our own BS
    from aegis.calculators.greeks import _bs_price

    price = _bs_price("call", S=100.0, K=100.0, T=0.5, r=0.05, sigma=sigma_true)

    iv = compute_implied_volatility("call", price, S=100.0, K=100.0, T=0.5, r=0.05)

    assert iv == pytest.approx(sigma_true, rel=1e-4)


def test_implied_volatility_put():
    """IV should recover the input sigma for a put."""
    sigma_true = 0.30
    from aegis.calculators.greeks import _bs_price

    price = _bs_price("put", S=100.0, K=95.0, T=0.25, r=0.03, sigma=sigma_true)

    iv = compute_implied_volatility("put", price, S=100.0, K=95.0, T=0.25, r=0.03)

    assert iv == pytest.approx(sigma_true, rel=1e-4)


def test_implied_volatility_no_convergence():
    """IV should raise ValueError for impossible prices."""
    with pytest.raises(ValueError, match="did not converge"):
        # Call price > spot (arbitrage bound violated for deep ITM)
        compute_implied_volatility("call", 200.0, S=100.0, K=100.0, T=0.5, r=0.05)

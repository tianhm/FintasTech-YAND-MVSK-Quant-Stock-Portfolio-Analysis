from __future__ import annotations

import numpy as np

from quant_core.oracle import MVSKCoefficients, MVSKOracle
from quant_core.simplex import alpha_max_for_simplex, project_simplex


def test_mvsk_gradient_matches_finite_difference() -> None:
    rng = np.random.default_rng(7)
    returns = rng.normal(0.001, 0.02, size=(80, 5))
    oracle = MVSKOracle(returns, MVSKCoefficients(mean=1.1, variance=0.7, skewness=0.4, kurtosis=0.9))
    x = np.ones(5) / 5
    direction = rng.normal(size=5)
    direction = direction - direction.mean()
    direction = direction / np.linalg.norm(direction)
    _, grad = oracle.value_grad(x)
    eps = 1e-6
    fd = (oracle.value(x + eps * direction) - oracle.value(x - eps * direction)) / (2 * eps)
    assert np.isclose(fd, grad @ direction, rtol=1e-4, atol=1e-6)


def test_hvp_matches_gradient_difference() -> None:
    rng = np.random.default_rng(11)
    returns = rng.normal(0.0, 0.015, size=(100, 6))
    oracle = MVSKOracle(returns, MVSKCoefficients())
    x = np.ones(6) / 6
    v = rng.normal(size=6)
    eps = 1e-6
    _, grad_plus = oracle.value_grad(x + eps * v)
    _, grad_minus = oracle.value_grad(x - eps * v)
    fd = (grad_plus - grad_minus) / (2 * eps)
    assert np.allclose(fd, oracle.hvp(x, v), rtol=1e-4, atol=1e-6)


def test_third_order_kernel_matches_hvp_difference() -> None:
    rng = np.random.default_rng(13)
    returns = rng.normal(0.0, 0.015, size=(90, 5))
    oracle = MVSKOracle(returns, MVSKCoefficients(mean=0.9, variance=1.1, skewness=0.8, kurtosis=1.3))
    x = np.ones(5) / 5
    u = rng.normal(size=5)
    v = rng.normal(size=5)
    eps = 1e-6
    hvp_plus = oracle.hvp(x + eps * u, v)
    hvp_minus = oracle.hvp(x - eps * u, v)
    fd = (hvp_plus - hvp_minus) / (2 * eps)
    assert np.allclose(fd, oracle.third(x, u, v), rtol=1e-4, atol=1e-6)


def test_crra_coefficients_follow_taylor_calibration() -> None:
    gamma = 6.0
    c = MVSKCoefficients.crra(gamma)
    assert np.isclose(c.mean, 1.0)
    assert np.isclose(c.variance, 3.0)
    assert np.isclose(c.skewness, 7.0)
    assert np.isclose(c.kurtosis, 14.0)


def test_convexity_certificate_matches_paper_condition() -> None:
    # CRRA calibrations satisfy 3 c3^2 < 8 c2 c4 for reasonable gamma.
    assert MVSKCoefficients.crra(6.0).convexity_certified
    # A skew-heavy profile with weak kurtosis fails the certificate.
    assert not MVSKCoefficients(mean=1.0, variance=1.0, skewness=1.2, kurtosis=0.2).convexity_certified
    # Pure mean-variance (c3 = c4 = 0) is trivially convex.
    assert MVSKCoefficients(mean=1.0, variance=1.0, skewness=0.0, kurtosis=0.0).convexity_certified


def test_simplex_projection_and_alpha_cap() -> None:
    projected = project_simplex(np.array([0.8, -0.2, 0.7]))
    assert np.isclose(projected.sum(), 1.0)
    assert np.all(projected >= 0.0)
    x = np.array([0.4, 0.4, 0.2])
    d = np.array([0.2, -0.1, -0.1])
    cap = alpha_max_for_simplex(x, d, tau=1e-8)
    assert cap > 0
    assert np.all(x + cap * d >= -1e-8)

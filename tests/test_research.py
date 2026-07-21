from __future__ import annotations

import numpy as np
import pandas as pd

from quant_core.data import MarketDataConfig, prices_to_returns
from quant_core.backtest import run_static_backtest
from quant_core.mv import solve_mean_variance
from quant_core.optimizer import YANDConfig, YANDMVSKOptimizer
from quant_core.oracle import MVSKCoefficients, MVSKOracle
from quant_core.research import ResearchConfig, run_research
from quant_core.screening import ScreenerConfig, screen_universe


def test_optimizer_returns_simplex_weights() -> None:
    rng = np.random.default_rng(21)
    returns = rng.normal(0.0005, 0.012, size=(120, 8))
    oracle = MVSKOracle(returns, MVSKCoefficients.preset("balanced"))
    result = YANDMVSKOptimizer(oracle, YANDConfig(max_iter=20)).solve()
    assert np.isclose(result.weights.sum(), 1.0)
    assert np.all(result.weights >= -1e-8)
    assert np.isfinite(result.objective)


def test_yand_converges_on_certified_convex_crra_instance() -> None:
    rng = np.random.default_rng(5)
    returns = rng.normal(0.0004, 0.01, size=(250, 6))
    coefficients = MVSKCoefficients.crra(6.0)
    assert coefficients.convexity_certified
    oracle = MVSKOracle(returns, coefficients)
    result = YANDMVSKOptimizer(oracle, YANDConfig(max_iter=200, tolerance=1e-7)).solve()
    assert result.converged
    assert result.kkt_residual <= 1e-7
    # The exact line search accepts only non-increasing objective values.
    objectives = [h["objective"] for h in result.history]
    assert objectives[-1] <= objectives[0] + 1e-12


def test_yand_pcg_mode_matches_direct_solution() -> None:
    rng = np.random.default_rng(9)
    returns = rng.normal(0.0004, 0.01, size=(250, 6))
    oracle = MVSKOracle(returns, MVSKCoefficients.crra(6.0))
    direct = YANDMVSKOptimizer(oracle, YANDConfig(max_iter=200, tolerance=1e-7)).solve()
    pcg = YANDMVSKOptimizer(
        oracle, YANDConfig(max_iter=400, tolerance=1e-7, use_pcg_threshold=2)
    ).solve()
    assert pcg.method == "pcg"
    assert pcg.converged
    # Convex objective: both configurations must reach the same optimum.
    assert np.isclose(direct.objective, pcg.objective, rtol=1e-6, atol=1e-9)
    assert np.allclose(direct.weights, pcg.weights, atol=1e-4)


def test_screen_mv_and_backtest_pipeline() -> None:
    rng = np.random.default_rng(42)
    frame = pd.DataFrame(
        rng.normal(0.0008, 0.02, size=(160, 10)),
        columns=[f"T{i}" for i in range(10)],
        index=pd.date_range("2022-01-01", periods=160, freq="B"),
    )
    selected = screen_universe(frame, ScreenerConfig(max_assets=6))
    assert len(selected) >= 2
    train = frame[selected].iloc[:100]
    test = frame[selected].iloc[100:]
    weights = solve_mean_variance(train.to_numpy())
    result = run_static_backtest(test, weights)
    assert result.equity_curve
    assert "sharpe" in result.metrics


def test_screen_keeps_two_asset_universe() -> None:
    frame = pd.DataFrame(
        {
            "MSFT": [0.01, 0.002, -0.004, 0.006, 0.003, 0.005],
            "NVDA": [0.02, -0.01, 0.015, -0.004, 0.007, 0.012],
        },
        index=pd.date_range("2024-01-01", periods=6, freq="B"),
    )
    selected = screen_universe(frame, ScreenerConfig(max_assets=2))
    assert set(selected) == {"MSFT", "NVDA"}


def test_research_supports_single_asset(monkeypatch) -> None:
    prices = pd.DataFrame(
        {"MSFT": np.linspace(100.0, 125.0, 80)},
        index=pd.date_range("2023-01-01", periods=80, freq="B"),
    )

    def fake_loader(_config: MarketDataConfig) -> pd.DataFrame:
        return prices

    monkeypatch.setattr("quant_core.research.load_price_history", fake_loader)
    report = run_research(
        ResearchConfig(
            market_data=MarketDataConfig(tickers=("MSFT",)),
            screener=ScreenerConfig(max_assets=1),
        )
    )
    assert report.selected_tickers == ["MSFT"]
    assert report.mv_weights == {"MSFT": 1.0}
    assert report.mvsk_weights == {"MSFT": 1.0}
    assert report.diagnostics["mvsk_method"] == "single_asset_no_optimization"
    assert report.equity_curves["mvsk"]


def test_screening_only_sees_training_window(monkeypatch) -> None:
    rng = np.random.default_rng(33)
    periods = 160
    index = pd.date_range("2023-01-02", periods=periods + 1, freq="B")
    frame = {}
    for i in range(6):
        returns = rng.normal(0.001, 0.01, size=periods)
        frame[f"GOOD{i}"] = 100.0 * np.cumprod(1.0 + np.concatenate(([0.0], returns)))
    # LEAK collapses during the training window but rallies hard in the test window. Screening
    # with test-period knowledge would rank it near the top; honest screening must drop it.
    leak = np.concatenate((np.full(120, -0.005), np.full(periods - 120, 0.05)))
    frame["LEAK"] = 100.0 * np.cumprod(1.0 + np.concatenate(([0.0], leak)))
    prices = pd.DataFrame(frame, index=index)

    monkeypatch.setattr("quant_core.research.load_price_history", lambda _config: prices)
    report = run_research(
        ResearchConfig(
            market_data=MarketDataConfig(tickers=tuple(prices.columns)),
            screener=ScreenerConfig(max_assets=4),
            train_ratio=0.75,
        )
    )
    assert "LEAK" not in report.selected_tickers


def test_research_report_includes_baselines_and_history(monkeypatch) -> None:
    rng = np.random.default_rng(77)
    periods = 200
    index = pd.date_range("2022-01-03", periods=periods + 1, freq="B")
    returns = rng.normal(0.0006, 0.012, size=(periods, 6))
    prices = pd.DataFrame(
        100.0 * np.cumprod(1.0 + np.vstack((np.zeros(6), returns)), axis=0),
        columns=[f"T{i}" for i in range(6)],
        index=index,
    )
    monkeypatch.setattr("quant_core.research.load_price_history", lambda _config: prices)
    report = run_research(
        ResearchConfig(
            market_data=MarketDataConfig(tickers=tuple(prices.columns)),
            screener=ScreenerConfig(max_assets=5),
        )
    )
    assert "sharpe" in report.ew_metrics
    assert "realized_skewness" in report.mvsk_metrics
    assert "realized_excess_kurtosis" in report.mv_metrics
    assert "ew" in report.equity_curves
    assert report.solver_history
    assert {"iteration", "objective", "kkt_residual"} <= set(report.solver_history[0])
    assert isinstance(report.diagnostics["convexity_certified"], bool)


def test_returns_are_percent_changes_for_full_market_tickers() -> None:
    prices = pd.DataFrame(
        {"600519.SS": [100.0, 110.0, 99.0], "0700.HK": [200.0, 220.0, 242.0]},
        index=pd.date_range("2024-01-01", periods=3, freq="B"),
    )
    returns = prices_to_returns(prices)
    assert np.isclose(returns.loc[returns.index[0], "600519.SS"], 0.10)
    assert np.isclose(returns.loc[returns.index[1], "600519.SS"], -0.10)
    assert np.isclose(returns.loc[returns.index[1], "0700.HK"], 0.10)

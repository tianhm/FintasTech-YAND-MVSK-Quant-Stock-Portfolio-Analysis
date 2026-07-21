from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from .backtest import BacktestConfig, run_static_backtest
from .data import MarketDataConfig, load_price_history, prices_to_returns
from .mv import solve_mean_variance
from .optimizer import YANDConfig, YANDMVSKOptimizer
from .oracle import MVSKCoefficients, MVSKOracle
from .screening import ScreenerConfig, screen_universe
from .simplex import effective_number


@dataclass(frozen=True)
class ResearchConfig:
    market_data: MarketDataConfig = MarketDataConfig()
    screener: ScreenerConfig = ScreenerConfig()
    backtest: BacktestConfig = BacktestConfig()
    mvsk_preset: str = "kurtosis-focused"
    crra_gamma: float = 6.0
    train_ratio: float = 0.7
    max_history_points: int = 200


@dataclass
class ResearchReport:
    selected_tickers: list[str]
    mv_weights: dict[str, float]
    mvsk_weights: dict[str, float]
    mv_metrics: dict[str, float]
    mvsk_metrics: dict[str, float]
    ew_metrics: dict[str, float]
    diagnostics: dict[str, float | int | str | bool]
    equity_curves: dict[str, list[dict[str, float | str]]]
    solver_history: list[dict[str, float]]

    def to_dict(self) -> dict:
        return asdict(self)


def run_research(config: ResearchConfig) -> ResearchReport:
    prices = load_price_history(config.market_data)
    returns = prices_to_returns(prices)
    if returns.empty:
        raise RuntimeError("No usable return history for the requested tickers")

    # Split before screening so that ranking (mean, momentum, volatility) only sees the training
    # window. Screening on the full sample would leak test-period information into selection.
    split = _train_test_split_index(len(returns), config.train_ratio)
    selected = screen_universe(returns.iloc[:split], config.screener)
    if len(selected) < 1:
        raise RuntimeError("Screening left no assets")

    selected_returns = returns[selected]
    train = selected_returns.iloc[:split]
    test = selected_returns.iloc[split:]

    if len(selected) == 1:
        return _single_asset_report(selected, train, test, config)

    coefficients = _resolve_coefficients(train, config)
    oracle = MVSKOracle(train.to_numpy(dtype=float), coefficients)
    optimizer = YANDMVSKOptimizer(oracle, YANDConfig(max_iter=100))
    mvsk_result = optimizer.solve()
    mv_weights = solve_mean_variance(train.to_numpy(dtype=float))
    ew_weights = np.ones(len(selected), dtype=float) / len(selected)

    mv_backtest = run_static_backtest(test, mv_weights, config.backtest)
    mvsk_backtest = run_static_backtest(test, mvsk_result.weights, config.backtest)
    ew_backtest = run_static_backtest(test, ew_weights, config.backtest)

    diagnostics: dict[str, float | int | str | bool] = {
        "mvsk_objective": mvsk_result.objective,
        "mvsk_kkt_residual": mvsk_result.kkt_residual,
        "mvsk_iterations": mvsk_result.iterations,
        "mvsk_converged": mvsk_result.converged,
        "mvsk_method": mvsk_result.method,
        "convexity_certified": coefficients.convexity_certified,
        "mv_effective_assets": effective_number(mv_weights),
        "mvsk_effective_assets": effective_number(mvsk_result.weights),
        "active_share": 0.5 * float(np.abs(mvsk_result.weights - mv_weights).sum()),
        "train_samples": int(len(train)),
        "test_samples": int(len(test)),
    }

    return ResearchReport(
        selected_tickers=selected,
        mv_weights=_weight_map(selected, mv_weights),
        mvsk_weights=_weight_map(selected, mvsk_result.weights),
        mv_metrics=mv_backtest.metrics,
        mvsk_metrics=mvsk_backtest.metrics,
        ew_metrics=ew_backtest.metrics,
        diagnostics=diagnostics,
        equity_curves={
            "mv": mv_backtest.equity_curve,
            "mvsk": mvsk_backtest.equity_curve,
            "ew": ew_backtest.equity_curve,
        },
        solver_history=_compress_history(mvsk_result.history, config.max_history_points),
    )


def _single_asset_report(
    selected: list[str],
    train: pd.DataFrame,
    test: pd.DataFrame,
    config: ResearchConfig,
) -> ResearchReport:
    weights = np.ones(1, dtype=float)
    backtest = run_static_backtest(test, weights, config.backtest)
    weight_map = _weight_map(selected, weights)
    diagnostics: dict[str, float | int | str | bool] = {
        "mvsk_objective": 0.0,
        "mvsk_kkt_residual": 0.0,
        "mvsk_iterations": 0,
        "mvsk_converged": True,
        "mvsk_method": "single_asset_no_optimization",
        "convexity_certified": True,
        "mv_effective_assets": 1.0,
        "mvsk_effective_assets": 1.0,
        "active_share": 0.0,
        "train_samples": int(len(train)),
        "test_samples": int(len(test)),
    }
    return ResearchReport(
        selected_tickers=selected,
        mv_weights=weight_map,
        mvsk_weights=weight_map,
        mv_metrics=backtest.metrics,
        mvsk_metrics=backtest.metrics,
        ew_metrics=backtest.metrics,
        diagnostics=diagnostics,
        equity_curves={
            "mv": backtest.equity_curve,
            "mvsk": backtest.equity_curve,
            "ew": backtest.equity_curve,
        },
        solver_history=[],
    )


def _train_test_split_index(length: int, train_ratio: float) -> int:
    if length < 2:
        raise RuntimeError("Not enough return samples for a train/test split")
    return max(1, min(int(length * train_ratio), length - 1))


def _resolve_coefficients(returns: pd.DataFrame, config: ResearchConfig) -> MVSKCoefficients:
    if config.mvsk_preset == "crra":
        # Paper-standard CRRA calibration acts on raw sample moments and is not rescaled.
        return MVSKCoefficients.crra(config.crra_gamma)
    return _scale_coefficients(returns, MVSKCoefficients.preset(config.mvsk_preset))


def _scale_coefficients(returns: pd.DataFrame, base: MVSKCoefficients) -> MVSKCoefficients:
    equal = np.ones(returns.shape[1]) / returns.shape[1]
    oracle = MVSKOracle(returns.to_numpy(dtype=float), MVSKCoefficients())
    moments = oracle.moments(equal)
    eps = 1e-10
    return MVSKCoefficients(
        mean=base.mean / max(abs(moments["mean"]), eps),
        variance=base.variance / max(abs(moments["variance"]), eps),
        skewness=base.skewness / max(abs(moments["skewness"]), eps),
        kurtosis=base.kurtosis / max(abs(moments["kurtosis"]), eps),
    )


def _compress_history(history: list[dict[str, float]], max_points: int) -> list[dict[str, float]]:
    entries = [
        {"iteration": i, "objective": h["objective"], "kkt_residual": h["kkt_residual"]}
        for i, h in enumerate(history)
    ]
    if len(entries) <= max_points:
        return entries
    stride = int(np.ceil(len(entries) / max_points))
    sampled = entries[::stride]
    if sampled[-1]["iteration"] != entries[-1]["iteration"]:
        sampled.append(entries[-1])
    return sampled


def _weight_map(tickers: list[str], weights: np.ndarray) -> dict[str, float]:
    return {ticker: float(weight) for ticker, weight in zip(tickers, weights, strict=False)}

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

DEFAULT_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "JPM",
    "LLY",
    "V",
    "XOM",
    "AVGO",
    "COST",
]

PRESETS = ["balanced", "skew-focused", "kurtosis-focused", "defensive", "crra"]


class ResearchRequest(BaseModel):
    tickers: list[str] = Field(default_factory=lambda: list(DEFAULT_TICKERS), max_length=100)
    start: str = "2020-01-01"
    end: str | None = None
    interval: Literal["1d", "1wk", "1mo"] = "1d"
    max_assets: int = Field(default=10, ge=1, le=80)
    mvsk_preset: Literal["balanced", "skew-focused", "kurtosis-focused", "defensive", "crra"] = (
        "kurtosis-focused"
    )
    crra_gamma: float = Field(default=6.0, gt=0.0, le=50.0)
    train_ratio: float = Field(default=0.7, gt=0.2, lt=0.95)
    transaction_cost_bps: float = Field(default=5.0, ge=0.0, le=200.0)

    @field_validator("tickers")
    @classmethod
    def _clean_tickers(cls, tickers: list[str]) -> list[str]:
        cleaned = [ticker.strip().upper() for ticker in tickers if ticker.strip()]
        if not cleaned:
            raise ValueError("At least one ticker is required")
        return cleaned


class DemoConfigResponse(BaseModel):
    tickers: list[str]
    presets: list[str]
    start: str
    interval: str

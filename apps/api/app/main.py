from __future__ import annotations

import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from quant_core import BacktestConfig, MarketDataConfig, ResearchConfig, ScreenerConfig, run_research

from .schemas import PRESETS, DemoConfigResponse, ResearchRequest

app = FastAPI(
    title="FintasTech YAND-MVSK API",
    description="Research API for YAND-MVSK higher-moment portfolio optimization.",
    version="0.2.0",
)

_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("FINTASTECH_CORS_ORIGINS", _default_origins).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/demo-config", response_model=DemoConfigResponse)
def demo_config() -> DemoConfigResponse:
    defaults = MarketDataConfig()
    return DemoConfigResponse(
        tickers=list(defaults.tickers),
        presets=list(PRESETS),
        start=defaults.start,
        interval=defaults.interval,
    )


@app.post("/research/run")
def run_research_endpoint(request: ResearchRequest) -> dict:
    config = ResearchConfig(
        market_data=MarketDataConfig(
            tickers=tuple(request.tickers),
            start=request.start,
            end=request.end,
            interval=request.interval,
        ),
        screener=ScreenerConfig(max_assets=request.max_assets),
        backtest=BacktestConfig(transaction_cost_bps=request.transaction_cost_bps),
        mvsk_preset=request.mvsk_preset,
        crra_gamma=request.crra_gamma,
        train_ratio=request.train_ratio,
    )
    started = time.perf_counter()
    try:
        report = run_research(config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Data-layer failures (no data returned, screening emptied the universe, ...) are
        # client-visible research errors, not server crashes.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    payload = report.to_dict()
    payload["diagnostics"]["elapsed_seconds"] = round(time.perf_counter() - started, 3)
    return payload

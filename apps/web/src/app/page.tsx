"use client";

import { LanguageToggle } from "@/components/LanguageToggle";
import { formatPercent, type Language, useLanguage } from "@/lib/i18n";
import Link from "next/link";
import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

type Report = {
  selected_tickers: string[];
  mv_weights: Record<string, number>;
  mvsk_weights: Record<string, number>;
  mv_metrics: Record<string, number>;
  mvsk_metrics: Record<string, number>;
  ew_metrics: Record<string, number>;
  diagnostics: Record<string, number | string | boolean>;
  equity_curves: {
    mv: { date: string; equity: number }[];
    mvsk: { date: string; equity: number }[];
    ew?: { date: string; equity: number }[];
  };
  solver_history?: { iteration: number; objective: number; kkt_residual: number }[];
};

type MessageKey = "demo" | "running" | "live" | "error";

type Copy = {
  navConsole: string;
  tutorial: string;
  eyebrow: string;
  headline: string;
  intro: string;
  chips: string[];
  traceTitle: string;
  traceSteps: string[];
  setup: string;
  tickers: string;
  tickerHint: string;
  profile: string;
  profiles: Record<string, string>;
  gamma: string;
  gammaHint: string;
  startDate: string;
  endDate: string;
  endDateHint: string;
  maxAssets: string;
  costBps: string;
  trainRatio: string;
  run: string;
  runningButton: string;
  messages: Record<MessageKey, string>;
  metrics: { mvskReturn: string; mvReturn: string; sharpeLift: string; activeShare: string };
  backtest: string;
  curveTitle: string;
  selectedAssets: string;
  tableTitle: string;
  tableMetric: string;
  metricNames: Record<string, string>;
  weights: string;
  weightsLegendMvsk: string;
  weightsLegendMv: string;
  convergence: string;
  convergenceHint: string;
  diagnostics: string;
};

const copy: Record<Language, Copy> = {
  en: {
    navConsole: "Launch Console",
    tutorial: "Tutorial",
    eyebrow: "Paper-to-product: exact higher-moment portfolio optimization",
    headline: "Quant research without tensor explosions.",
    intro:
      "This platform implements the YAND-MVSK algorithm: evaluate mean, variance, skewness and kurtosis directly from the return matrix, assemble affine-normal descent directions on the simplex, and compare higher-moment allocations against exact mean-variance and equal-weight baselines.",
    chips: ["Exact sample oracle", "Affine-normal direction", "Quartic line search", "MV + 1/N baselines"],
    traceTitle: "Optimization Trace",
    traceSteps: ["Return matrix R", "Centered map A", "Affine-normal direction", "MVSK weights"],
    setup: "Research Setup",
    tickers: "Tickers",
    tickerHint: "Enter full Yahoo Finance tickers. US: AAPL/MSFT. A-shares: 600519.SS/000001.SZ. HK: 0700.HK/9988.HK.",
    profile: "MVSK profile",
    profiles: {
      balanced: "Balanced",
      "skew-focused": "Skew focused",
      "kurtosis-focused": "Kurtosis focused",
      defensive: "Defensive",
      crra: "CRRA utility (paper)"
    },
    gamma: "CRRA risk aversion γ",
    gammaHint: "Paper-standard Taylor calibration: c=(1, γ/2, γ(γ+1)/6, γ(γ+1)(γ+2)/24).",
    startDate: "Start date",
    endDate: "End date",
    endDateHint: "Leave empty for latest data.",
    maxAssets: "Max assets",
    costBps: "Cost (bps)",
    trainRatio: "Train ratio",
    run: "Run research",
    runningButton: "Running...",
    messages: {
      demo: "Demo report loaded. Connect the API to run live yfinance research.",
      running: "Running FastAPI research pipeline...",
      live: "Live report generated from yfinance data.",
      error: "Using built-in demo because API is unavailable"
    },
    metrics: {
      mvskReturn: "MVSK Return",
      mvReturn: "MV Return",
      sharpeLift: "Sharpe Lift",
      activeShare: "Active Share"
    },
    backtest: "Backtest",
    curveTitle: "MVSK vs MV vs 1/N equity curve",
    selectedAssets: "selected assets",
    tableTitle: "Out-of-sample comparison",
    tableMetric: "Metric",
    metricNames: {
      annual_return: "Annual return",
      annual_volatility: "Annual volatility",
      sharpe: "Sharpe",
      sortino: "Sortino",
      max_drawdown: "Max drawdown",
      calmar: "Calmar",
      cvar_5: "CVaR 5%",
      realized_skewness: "Realized skewness",
      realized_excess_kurtosis: "Realized excess kurtosis",
      effective_assets: "Effective assets"
    },
    weights: "Portfolio Weights",
    weightsLegendMvsk: "MVSK",
    weightsLegendMv: "MV",
    convergence: "Solver Convergence",
    convergenceHint: "Projected KKT residual per YAND iteration (log scale).",
    diagnostics: "YAND Diagnostics"
  },
  zh: {
    navConsole: "进入控制台",
    tutorial: "新手教程",
    eyebrow: "论文方法产品化：精确高阶矩组合优化",
    headline: "不用张量爆炸，也能做高阶矩量化研究。",
    intro:
      "本平台实现 YAND-MVSK 算法：直接从收益率矩阵计算均值、方差、偏度和峰度，在 simplex 上组装 affine-normal 下降方向，并将高阶矩组合与精确均值-方差、等权 1/N 两个基线对照。",
    chips: ["精确样本 Oracle", "Affine-normal 方向", "精确四次线搜索", "MV + 1/N 基线"],
    traceTitle: "优化流程",
    traceSteps: ["收益矩阵 R", "中心化映射 A", "Affine-normal 方向", "MVSK 权重"],
    setup: "研究参数",
    tickers: "股票代码",
    tickerHint: "请输入 Yahoo Finance 完整 ticker。美股：AAPL/MSFT；A股：600519.SS/000001.SZ；港股：0700.HK/9988.HK。",
    profile: "MVSK 偏好配置",
    profiles: {
      balanced: "均衡型",
      "skew-focused": "偏度优先",
      "kurtosis-focused": "峰度优先",
      defensive: "防御型",
      crra: "CRRA 效用（论文标准）"
    },
    gamma: "CRRA 风险厌恶系数 γ",
    gammaHint: "论文标准 Taylor 校准：c=(1, γ/2, γ(γ+1)/6, γ(γ+1)(γ+2)/24)。",
    startDate: "开始日期",
    endDate: "结束日期",
    endDateHint: "留空表示取最新数据。",
    maxAssets: "最大持仓数",
    costBps: "成本 (bps)",
    trainRatio: "训练占比",
    run: "运行研究",
    runningButton: "运行中...",
    messages: {
      demo: "已加载内置演示报告。连接 API 后可运行真实 yfinance 数据研究。",
      running: "正在运行 FastAPI 研究流程...",
      live: "已基于 yfinance 数据生成实时报告。",
      error: "API 暂不可用，当前使用内置演示"
    },
    metrics: {
      mvskReturn: "MVSK 年化收益",
      mvReturn: "MV 年化收益",
      sharpeLift: "Sharpe 提升",
      activeShare: "主动份额"
    },
    backtest: "回测",
    curveTitle: "MVSK / MV / 1N 净值曲线对比",
    selectedAssets: "只入选资产",
    tableTitle: "样本外指标对比",
    tableMetric: "指标",
    metricNames: {
      annual_return: "年化收益",
      annual_volatility: "年化波动率",
      sharpe: "Sharpe",
      sortino: "Sortino",
      max_drawdown: "最大回撤",
      calmar: "Calmar",
      cvar_5: "CVaR 5%",
      realized_skewness: "实现偏度",
      realized_excess_kurtosis: "实现超额峰度",
      effective_assets: "有效持仓数"
    },
    weights: "持仓权重对比",
    weightsLegendMvsk: "MVSK",
    weightsLegendMv: "MV",
    convergence: "求解器收敛",
    convergenceHint: "每次 YAND 迭代的投影 KKT 残差（对数坐标）。",
    diagnostics: "YAND 诊断"
  }
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// Series colors validated for a white surface (CVD-safe pair); 1/N is a dashed
// neutral reference line, distinguished by dash pattern and legend, not hue.
const SERIES = {
  mvsk: "#0d9488",
  mv: "#4a3aa7",
  ew: "#898781"
};

const CHART_CHROME = {
  grid: "#e1e0d9",
  axis: "#898781",
  tooltip: {
    background: "#ffffff",
    border: "1px solid rgba(11,11,11,0.1)",
    borderRadius: 12,
    color: "#0b0b0b"
  }
};

const defaultReport: Report = {
  selected_tickers: ["NVDA", "MSFT", "AAPL", "AVGO", "LLY", "JPM", "COST", "META"],
  mv_weights: {
    NVDA: 0.21,
    MSFT: 0.16,
    AAPL: 0.13,
    AVGO: 0.11,
    LLY: 0.1,
    JPM: 0.1,
    COST: 0.1,
    META: 0.09
  },
  mvsk_weights: {
    NVDA: 0.18,
    MSFT: 0.17,
    AAPL: 0.12,
    AVGO: 0.14,
    LLY: 0.13,
    JPM: 0.07,
    COST: 0.11,
    META: 0.08
  },
  mv_metrics: {
    annual_return: 0.214,
    annual_volatility: 0.223,
    sharpe: 0.96,
    sortino: 1.21,
    max_drawdown: -0.188,
    calmar: 1.14,
    cvar_1: -0.034,
    cvar_5: -0.024,
    realized_skewness: -0.42,
    realized_excess_kurtosis: 2.9,
    effective_assets: 6.7
  },
  mvsk_metrics: {
    annual_return: 0.268,
    annual_volatility: 0.219,
    sharpe: 1.22,
    sortino: 1.58,
    max_drawdown: -0.151,
    calmar: 1.77,
    cvar_1: -0.029,
    cvar_5: -0.021,
    realized_skewness: -0.18,
    realized_excess_kurtosis: 1.9,
    effective_assets: 7.1
  },
  ew_metrics: {
    annual_return: 0.187,
    annual_volatility: 0.201,
    sharpe: 0.93,
    sortino: 1.18,
    max_drawdown: -0.173,
    calmar: 1.08,
    cvar_1: -0.031,
    cvar_5: -0.022,
    realized_skewness: -0.35,
    realized_excess_kurtosis: 2.4,
    effective_assets: 8.0
  },
  diagnostics: {
    mvsk_objective: -0.742,
    mvsk_kkt_residual: 0.000003,
    mvsk_iterations: 48,
    mvsk_converged: true,
    mvsk_method: "direct",
    convexity_certified: false,
    active_share: 0.11,
    train_samples: 864,
    test_samples: 371
  },
  equity_curves: {
    mv: [
      { date: "2023-01", equity: 1 },
      { date: "2023-04", equity: 1.04 },
      { date: "2023-07", equity: 1.08 },
      { date: "2023-10", equity: 1.03 },
      { date: "2024-01", equity: 1.16 },
      { date: "2024-04", equity: 1.23 },
      { date: "2024-07", equity: 1.28 }
    ],
    mvsk: [
      { date: "2023-01", equity: 1 },
      { date: "2023-04", equity: 1.06 },
      { date: "2023-07", equity: 1.13 },
      { date: "2023-10", equity: 1.1 },
      { date: "2024-01", equity: 1.24 },
      { date: "2024-04", equity: 1.35 },
      { date: "2024-07", equity: 1.44 }
    ],
    ew: [
      { date: "2023-01", equity: 1 },
      { date: "2023-04", equity: 1.03 },
      { date: "2023-07", equity: 1.07 },
      { date: "2023-10", equity: 1.04 },
      { date: "2024-01", equity: 1.13 },
      { date: "2024-04", equity: 1.19 },
      { date: "2024-07", equity: 1.24 }
    ]
  },
  solver_history: [
    { iteration: 0, objective: -0.31, kkt_residual: 0.19 },
    { iteration: 8, objective: -0.58, kkt_residual: 0.021 },
    { iteration: 16, objective: -0.68, kkt_residual: 0.0043 },
    { iteration: 24, objective: -0.72, kkt_residual: 0.00071 },
    { iteration: 32, objective: -0.736, kkt_residual: 0.00009 },
    { iteration: 40, objective: -0.741, kkt_residual: 0.00001 },
    { iteration: 48, objective: -0.742, kkt_residual: 0.000003 }
  ]
};

const TABLE_ROWS = [
  "annual_return",
  "annual_volatility",
  "sharpe",
  "sortino",
  "max_drawdown",
  "calmar",
  "cvar_5",
  "realized_skewness",
  "realized_excess_kurtosis",
  "effective_assets"
] as const;

const PERCENT_ROWS = new Set(["annual_return", "annual_volatility", "max_drawdown", "cvar_5"]);

export default function Home() {
  const { language, setLanguage } = useLanguage();
  const t = copy[language];
  const [tickers, setTickers] = useState("AAPL,MSFT,NVDA,AMZN,GOOGL,META,JPM,LLY,V,XOM,AVGO,COST");
  const [preset, setPreset] = useState("kurtosis-focused");
  const [gamma, setGamma] = useState(6);
  const [startDate, setStartDate] = useState("2020-01-01");
  const [endDate, setEndDate] = useState("");
  const [maxAssets, setMaxAssets] = useState(10);
  const [costBps, setCostBps] = useState(5);
  const [trainRatio, setTrainRatio] = useState(0.7);
  const [report, setReport] = useState<Report>(defaultReport);
  const [loading, setLoading] = useState(false);
  const [messageKey, setMessageKey] = useState<MessageKey>("demo");
  const [errorText, setErrorText] = useState("");

  const chartData = useMemo(() => {
    const mvByDate = new Map(report.equity_curves.mv.map((point) => [point.date, point.equity]));
    const ewByDate = new Map((report.equity_curves.ew ?? []).map((point) => [point.date, point.equity]));
    return report.equity_curves.mvsk.map((point) => ({
      date: point.date,
      MVSK: point.equity,
      MV: mvByDate.get(point.date) ?? point.equity,
      "1/N": ewByDate.get(point.date)
    }));
  }, [report]);

  const convergenceData = useMemo(
    () => (report.solver_history ?? []).filter((point) => point.kkt_residual > 0),
    [report]
  );

  async function runLiveResearch() {
    setLoading(true);
    setMessageKey("running");
    setErrorText("");
    try {
      const response = await fetch(`${API_BASE}/research/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tickers: tickers.split(",").map((ticker) => ticker.trim()).filter(Boolean),
          start: startDate,
          end: endDate || null,
          interval: "1d",
          max_assets: maxAssets,
          mvsk_preset: preset,
          crra_gamma: gamma,
          train_ratio: trainRatio,
          transaction_cost_bps: costBps
        })
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail ? String(detail.detail) : `API returned ${response.status}`);
      }
      setReport((await response.json()) as Report);
      setMessageKey("live");
    } catch (error) {
      setMessageKey("error");
      setErrorText((error as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const message =
    messageKey === "error" && errorText
      ? `${t.messages.error}: ${errorText}`
      : t.messages[messageKey];

  return (
    <main className="min-h-screen bg-paper px-6 py-6 text-ink md:px-10">
      <nav className="mx-auto flex max-w-7xl items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="brand-logo grid h-12 w-12 place-items-center rounded-2xl p-1.5">
            <img className="h-full w-full object-contain" src="/fintastech-logo-white-bg.svg" alt="FintasTech logo" />
          </div>
          <div>
            <p className="brand-wordmark text-base font-semibold uppercase italic text-violet">Finta$tech</p>
            <h1 className="font-display text-xl italic text-ink">YAND-MVSK Research OS</h1>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Link className="hidden rounded-full border border-line bg-card px-4 py-2 text-sm text-sub transition hover:text-ink md:inline-flex" href="/tutorial">
            {t.tutorial}
          </Link>
          <LanguageToggle language={language} onChange={setLanguage} />
          <a className="rounded-full border border-line bg-card px-4 py-2 text-sm text-sub transition hover:text-ink" href="#dashboard">
            {t.navConsole}
          </a>
        </div>
      </nav>

      <section className="mx-auto grid max-w-7xl gap-8 py-16 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <p className="mb-5 inline-flex rounded-full bg-accent-soft px-4 py-2 text-sm font-medium text-accent-deep">
            {t.eyebrow}
          </p>
          <h2 className="display-tight max-w-4xl font-display text-5xl font-medium leading-[1.02] md:text-7xl">
            {t.headline}
          </h2>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-sub">
            {t.intro}
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            {t.chips.map((item) => (
              <span key={item} className="rounded-full border border-line bg-card px-4 py-2 text-sm text-sub">
                {item}
              </span>
            ))}
          </div>
        </div>
        <div className="card rounded-[2rem] p-5">
          <div className="rounded-[1.5rem] border border-line bg-paper p-5">
            <div className="mb-6 flex items-center justify-between">
              <p className="text-sm uppercase tracking-[0.3em] text-muted">{t.traceTitle}</p>
              <span className="rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent-deep">KKT 3e-6</span>
            </div>
            <div className="grid gap-3">
              {t.traceSteps.map((item, index) => (
                <div key={item} className="flex items-center gap-4 rounded-2xl border border-line bg-card p-4">
                  <span className="grid h-8 w-8 place-items-center rounded-full bg-violet-soft text-sm font-semibold text-violet">
                    {index + 1}
                  </span>
                  <span className="text-ink">{item}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section id="dashboard" className="mx-auto grid max-w-7xl gap-5 pb-12 lg:grid-cols-[320px_1fr]">
        <aside className="card h-fit rounded-[1.75rem] p-5">
          <p className="mb-4 text-sm uppercase tracking-[0.26em] text-muted">{t.setup}</p>
          <label className="block text-sm font-medium text-sub">{t.tickers}</label>
          <textarea
            className="mt-2 min-h-28 w-full rounded-2xl border border-line bg-paper p-3 text-sm outline-none transition focus:border-accent"
            value={tickers}
            onChange={(event) => setTickers(event.target.value)}
          />
          <p className="mt-2 text-xs leading-5 text-muted">{t.tickerHint}</p>

          <label className="mt-5 block text-sm font-medium text-sub">{t.profile}</label>
          <select
            className="mt-2 w-full rounded-2xl border border-line bg-paper p-3 outline-none transition focus:border-accent"
            value={preset}
            onChange={(event) => setPreset(event.target.value)}
          >
            {Object.entries(t.profiles).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>

          {preset === "crra" && (
            <div className="mt-4">
              <label className="block text-sm font-medium text-sub">
                {t.gamma}: <span className="font-semibold text-accent-deep">{gamma}</span>
              </label>
              <input
                className="mt-2 w-full accent-[#0d9488]"
                type="range"
                min={1}
                max={20}
                step={1}
                value={gamma}
                onChange={(event) => setGamma(Number(event.target.value))}
              />
              <p className="mt-1 text-xs leading-5 text-muted">{t.gammaHint}</p>
            </div>
          )}

          <div className="mt-5 grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-sub">{t.startDate}</label>
              <input
                className="mt-2 w-full rounded-2xl border border-line bg-paper p-3 text-sm outline-none transition focus:border-accent"
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-sub">{t.endDate}</label>
              <input
                className="mt-2 w-full rounded-2xl border border-line bg-paper p-3 text-sm outline-none transition focus:border-accent"
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
              />
            </div>
          </div>
          <p className="mt-2 text-xs leading-5 text-muted">{t.endDateHint}</p>

          <div className="mt-4 grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-sub">{t.maxAssets}</label>
              <input
                className="mt-2 w-full rounded-2xl border border-line bg-paper p-3 text-sm outline-none transition focus:border-accent"
                type="number"
                min={2}
                max={80}
                value={maxAssets}
                onChange={(event) => setMaxAssets(Number(event.target.value))}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-sub">{t.costBps}</label>
              <input
                className="mt-2 w-full rounded-2xl border border-line bg-paper p-3 text-sm outline-none transition focus:border-accent"
                type="number"
                min={0}
                max={200}
                value={costBps}
                onChange={(event) => setCostBps(Number(event.target.value))}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-sub">{t.trainRatio}</label>
              <input
                className="mt-2 w-full rounded-2xl border border-line bg-paper p-3 text-sm outline-none transition focus:border-accent"
                type="number"
                min={0.3}
                max={0.9}
                step={0.05}
                value={trainRatio}
                onChange={(event) => setTrainRatio(Number(event.target.value))}
              />
            </div>
          </div>

          <button
            className="mt-5 w-full rounded-2xl bg-accent-deep px-5 py-3 font-semibold text-white transition hover:bg-accent disabled:opacity-60"
            disabled={loading}
            onClick={runLiveResearch}
          >
            {loading ? t.runningButton : t.run}
          </button>
          <p className="mt-4 text-sm leading-6 text-muted">{message}</p>
        </aside>

        <div className="grid gap-5">
          <div className="grid gap-4 md:grid-cols-4">
            <Metric label={t.metrics.mvskReturn} value={percent(report.mvsk_metrics.annual_return, language)} accent />
            <Metric label={t.metrics.mvReturn} value={percent(report.mv_metrics.annual_return, language)} />
            <Metric label={t.metrics.sharpeLift} value={(report.mvsk_metrics.sharpe - report.mv_metrics.sharpe).toFixed(2)} accent />
            <Metric label={t.metrics.activeShare} value={percent(Number(report.diagnostics.active_share), language)} />
          </div>

          <div className="card rounded-[1.75rem] p-5">
            <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="text-sm uppercase tracking-[0.26em] text-muted">{t.backtest}</p>
                <h3 className="font-display text-3xl">{t.curveTitle}</h3>
              </div>
              <div className="flex items-center gap-4 text-sm text-sub">
                <LegendSwatch color={SERIES.mvsk} label="MVSK" />
                <LegendSwatch color={SERIES.mv} label="MV" />
                <LegendSwatch color={SERIES.ew} label="1/N" dashed />
                <span className="text-muted">
                  {report.selected_tickers.length} {t.selectedAssets}
                </span>
              </div>
            </div>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="mvsk" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="5%" stopColor={SERIES.mvsk} stopOpacity={0.16} />
                      <stop offset="95%" stopColor={SERIES.mvsk} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={CHART_CHROME.grid} vertical={false} />
                  <XAxis dataKey="date" stroke={CHART_CHROME.axis} tickLine={false} axisLine={{ stroke: CHART_CHROME.grid }} />
                  <YAxis stroke={CHART_CHROME.axis} domain={["auto", "auto"]} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={CHART_CHROME.tooltip} />
                  <Area type="monotone" dataKey="MVSK" stroke={SERIES.mvsk} fill="url(#mvsk)" strokeWidth={2} />
                  <Area type="monotone" dataKey="MV" stroke={SERIES.mv} fill="transparent" strokeWidth={2} />
                  <Area type="monotone" dataKey="1/N" stroke={SERIES.ew} fill="transparent" strokeWidth={1.5} strokeDasharray="6 4" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card rounded-[1.75rem] p-5">
            <h3 className="mb-4 font-display text-2xl">{t.tableTitle}</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm [font-variant-numeric:tabular-nums]">
                <thead>
                  <tr className="border-b border-line text-left text-muted">
                    <th className="py-2 pr-4 font-normal">{t.tableMetric}</th>
                    <th className="py-2 pr-4 font-semibold text-accent-deep">MVSK</th>
                    <th className="py-2 pr-4 font-semibold text-violet">MV</th>
                    <th className="py-2 font-normal">1/N</th>
                  </tr>
                </thead>
                <tbody>
                  {TABLE_ROWS.map((row) => (
                    <tr key={row} className="border-b border-line/60">
                      <td className="py-2.5 pr-4 text-sub">{t.metricNames[row]}</td>
                      <td className="py-2.5 pr-4 font-medium text-accent-deep">{formatMetric(row, report.mvsk_metrics[row], language)}</td>
                      <td className="py-2.5 pr-4 text-violet">{formatMetric(row, report.mv_metrics[row], language)}</td>
                      <td className="py-2.5 text-sub">{formatMetric(row, report.ew_metrics?.[row], language)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <WeightsCompare
              title={t.weights}
              mvskLabel={t.weightsLegendMvsk}
              mvLabel={t.weightsLegendMv}
              mvskWeights={report.mvsk_weights}
              mvWeights={report.mv_weights}
              language={language}
            />
            <div className="grid gap-5">
              {convergenceData.length > 1 && (
                <div className="card rounded-[1.75rem] p-5">
                  <h3 className="font-display text-2xl">{t.convergence}</h3>
                  <p className="mb-3 mt-1 text-xs text-muted">{t.convergenceHint}</p>
                  <div className="h-44">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={convergenceData}>
                        <CartesianGrid stroke={CHART_CHROME.grid} vertical={false} />
                        <XAxis dataKey="iteration" stroke={CHART_CHROME.axis} tickLine={false} axisLine={{ stroke: CHART_CHROME.grid }} />
                        <YAxis
                          stroke={CHART_CHROME.axis}
                          scale="log"
                          domain={["auto", "auto"]}
                          tickFormatter={(value: number) => value.toExponential(0)}
                          width={52}
                          tickLine={false}
                          axisLine={false}
                        />
                        <Tooltip
                          contentStyle={CHART_CHROME.tooltip}
                          formatter={(value) => [Number(value).toExponential(2), "KKT"]}
                        />
                        <Line type="monotone" dataKey="kkt_residual" stroke={SERIES.mvsk} strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              )}
              <Diagnostics title={t.diagnostics} diagnostics={report.diagnostics} />
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function LegendSwatch({ color, label, dashed = false }: { color: string; label: string; dashed?: boolean }) {
  return (
    <span className="flex items-center gap-1.5">
      {dashed ? (
        <svg width="16" height="4" aria-hidden>
          <line x1="0" y1="2" x2="16" y2="2" stroke={color} strokeWidth="2" strokeDasharray="4 3" />
        </svg>
      ) : (
        <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
      )}
      {label}
    </span>
  );
}

function Metric({ label, value, accent = false }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="card rounded-3xl p-5">
      <p className="text-sm text-muted">{label}</p>
      <p className={accent ? "mt-3 text-3xl font-semibold text-accent-deep" : "mt-3 text-3xl font-semibold text-ink"}>
        {value}
      </p>
    </div>
  );
}

function WeightsCompare({
  title,
  mvskLabel,
  mvLabel,
  mvskWeights,
  mvWeights,
  language
}: {
  title: string;
  mvskLabel: string;
  mvLabel: string;
  mvskWeights: Record<string, number>;
  mvWeights: Record<string, number>;
  language: Language;
}) {
  const entries = Object.entries(mvskWeights).sort((a, b) => b[1] - a[1]);
  return (
    <div className="card rounded-[1.75rem] p-5">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-display text-2xl">{title}</h3>
        <div className="flex items-center gap-3 text-xs text-sub">
          <LegendSwatch color={SERIES.mvsk} label={mvskLabel} />
          <LegendSwatch color={SERIES.mv} label={mvLabel} />
        </div>
      </div>
      <div className="space-y-4">
        {entries.map(([ticker, weight]) => {
          const mvWeight = mvWeights[ticker] ?? 0;
          return (
            <div key={ticker}>
              <div className="mb-1 flex justify-between text-sm">
                <span className="font-medium text-ink">{ticker}</span>
                <span className="text-sub [font-variant-numeric:tabular-nums]">
                  {percent(weight, language)} <span className="text-muted">/ {percent(mvWeight, language)}</span>
                </span>
              </div>
              <div className="h-2 rounded-full bg-ink/[0.06]">
                <div className="h-2 rounded-full" style={{ width: `${Math.max(2, weight * 100)}%`, background: SERIES.mvsk }} />
              </div>
              <div className="mt-1 h-2 rounded-full bg-ink/[0.06]">
                <div className="h-2 rounded-full" style={{ width: `${Math.max(2, mvWeight * 100)}%`, background: SERIES.mv }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Diagnostics({ title, diagnostics }: { title: string; diagnostics: Report["diagnostics"] }) {
  return (
    <div className="card rounded-[1.75rem] p-5">
      <h3 className="mb-4 font-display text-2xl">{title}</h3>
      <div className="grid grid-cols-2 gap-3">
        {Object.entries(diagnostics).map(([key, value]) => (
          <div key={key} className="rounded-2xl border border-line bg-paper p-3">
            <p className="text-xs uppercase tracking-[0.18em] text-muted">{key.replaceAll("_", " ")}</p>
            <p className="mt-2 truncate text-sm font-medium text-ink [font-variant-numeric:tabular-nums]">{formatDiagnostic(value)}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function formatDiagnostic(value: number | string | boolean) {
  if (typeof value === "number" && !Number.isInteger(value)) {
    return Math.abs(value) < 0.001 && value !== 0 ? value.toExponential(2) : value.toFixed(4);
  }
  return String(value);
}

function formatMetric(row: string, value: number | undefined, language: Language) {
  if (value === undefined || Number.isNaN(value)) {
    return "—";
  }
  if (PERCENT_ROWS.has(row)) {
    return percent(value, language);
  }
  return value.toFixed(2);
}

function percent(value: number, language: Language) {
  return formatPercent(value, language);
}

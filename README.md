# FintasTech YAND-MVSK

<p align="center">
  <img src="logo/logo.svg" alt="FintasTech logo" width="132" />
</p>

<p align="center">
  <strong>把丘成桐团队的大规模高阶矩组合优化算法（YAND-MVSK），变成一个开箱即用的量化研究系统。</strong>
</p>

<p align="center">
  <a href="#english">English</a> ·
  <a href="https://arxiv.org/abs/2604.25378">Paper</a> ·
  <a href="./docs/paper-to-code.md">Paper-to-Code</a> ·
  <a href="LICENSE">MIT License</a>
</p>

> FintasTech 是研究与教育工具，不是投资顾问，也不提供投资建议。它的价值在于帮助你更快发现、比较和验证组合配置假设，而不是承诺任何收益。

输入一组股票 ticker，FintasTech 会自动完成数据下载、训练窗口内筛选、MV/MVSK/等权三方权重对比、样本外回测和风险诊断，让你用几分钟完成一次原本需要大量手工拼接的量化组合研究。

## 出发点

很多量化工具只做"均值-方差"或普通回测。FintasTech 实现了
[Yau's Affine-Normal Descent for Large-Scale Unrestricted Higher-Moment Portfolio Optimization](https://arxiv.org/abs/2604.25378)
（Wang, Niu, Sheshmani, Yau, 2026）的完整求解器，让高阶矩组合优化真正可用。

传统 MVSK 很强，但难落地：偏度和峰度能捕捉非对称收益与尾部风险，可显式协偏度/协峰度张量会随资产数量爆炸（`Θ(n³+n⁴)` 系数）。论文的突破是直接在收益矩阵上做精确 sample-oracle 计算（每次调用 `O(Tn)`），再配合 simplex 上的 affine-normal 下降方向与精确四次线搜索。本项目将论文 Algorithm 1 的四个模块全部落地：

1. **Oracle 模块**：目标值、梯度、Hessian-向量积、三阶方向核，全部走中心化收益矩阵，零张量。
2. **Affine-normal 模块**：约化坐标 + Householder 标架 + 切向系统求解，含 exact-trace **log-determinant 修正向量**（affine-normal 名字的来源），保证方向恒为下降方向。
3. **四次线搜索模块**：沿可行方向的目标是显式四次多项式，由混合幂和闭式给出，线搜索精确求解。
4. **边界模块**：活动面延拓（face continuation）——权重触及下界时在暴露的子面上重组方向，边界解也保持 Newton 型收敛。

公式与代码的逐条映射见 [docs/paper-to-code.md](./docs/paper-to-code.md)。

### 与官方代码的关系

截至 2026 年 7 月，论文承诺的官方复现包**尚未发布**（论文 "Code and data availability" 一节为将来时表述，作者 GitHub 上也没有对应仓库；牛一帅教授早年的 MVSKOPT 工具箱使用的是 DC 规划方法，与 YAND 不是同一算法）。本项目是**独立的第三方开源实现**，与论文作者无关联，定位是：

- 忠实实现论文 Algorithm 1（含现有其他开源复现普遍缺失的 simplex 约化、Householder 标架、log-det 修正与活动面延拓）；
- 在算法之外补齐一整套工程系统：数据管线、无未来函数的筛选、三基线对比回测、API 与可视化前端。

## 核心功能

**求解器（`packages/quant_core`）**

- 精确 sample oracle：`O(Tn)` 的目标/梯度/HVP/三阶核，不构造任何高阶张量。
- YAND affine-normal 方向：exact-trace log-determinant 修正、自适应正则化、direct（Cholesky）与 PCG（matrix-free）双配置。
- 精确四次线搜索 + simplex 边界活动面延拓，凸性认证实例上收敛到 KKT ≤ 1e-7。
- CRRA(γ) 论文标准系数校准，以及系数级凸性证书（`3c₃² < 8c₂c₄` ⇒ 全局最优保证）。

**研究管线**

- **无 look-ahead 筛选**：先切分训练/测试窗口，筛选只看训练数据——选股不允许偷看未来。
- **三方基线对比**：MVSK vs 精确均值-方差 vs 等权 1/N（学术上出了名难打败的基线）。
- **实现矩验证**：报告样本外组合收益的实现偏度与超额峰度——检验 MVSK 是否真的改善了分布形状，而不只是表面收益。
- 完整风险指标：年化收益/波动、Sharpe、Sortino、Calmar、最大回撤、CVaR 1%/5%、主动份额、有效持仓数。
- 求解器全程诊断：逐迭代 KKT 残差与目标值、收敛标志、凸性证书、求解耗时。

**平台**

- 多市场支持：美股 `AAPL`、A 股 `600519.SS`/`000001.SZ`、港股 `0700.HK` 等 Yahoo Finance ticker。
- 本地 Parquet 缓存（哈希 key 防冲突，开放区间数据自动过期刷新）。
- FastAPI 服务：请求校验、结构化错误、可配置 CORS。
- 双语 Next.js 前端：参数面板（日期区间、成本、训练比例、CRRA γ）、净值曲线、样本外对比表、MV/MVSK 权重对照、KKT 收敛图、新手教程页。

## 快速开始

第一次安装依赖：

```bash
make setup
```

之后日常启动只需要：

```bash
make dev
```

打开 `http://localhost:3000`，点击 **Run research** 即可运行完整研究流程。

常用命令：

```bash
make api    # 只启动 FastAPI（:8000）
make web    # 只启动前端（:3000）
make test   # Python tests + Next.js build
make lint   # ruff 静态检查
```

没有 `make` 时：

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
npm --prefix apps/web install
.venv/bin/uvicorn apps.api.app.main:app --reload
npm --prefix apps/web run dev
```

环境变量：前端用 `NEXT_PUBLIC_API_BASE` 指定 API 地址（默认 `http://localhost:8000`）；API 用 `FINTASTECH_CORS_ORIGINS` 配置跨域白名单。

## 方法论说明（为什么结果可信）

- 筛选、系数缩放、优化全部只使用训练窗口；测试窗口仅用于回测。
- 回测计入单边建仓交易成本（可调 bps）。
- 平台如实报告"MVSK 没赢"的窗口。论文本身的结论也是条件性的：高阶矩的价值取决于收益目标留出的配置自由度，且随市场窗口变化。如果某个窗口上 MVSK 连 1/N 都跑不赢，dashboard 会原样展示——这正是研究工具应有的诚实。
- 已知局限（也是路线图）：单次静态切分而非滚动 walk-forward；PCG 大规模模式默认省略 log-det 修正；尚无收益目标匹配的 frontier 对比。

## 输入格式

请直接输入 Yahoo Finance 完整 ticker：

- 美股：`AAPL`, `MSFT`, `NVDA`
- A 股：`600519.SS`, `000001.SZ`
- 港股：`0700.HK`, `9988.HK`

## 项目结构

```text
apps/
  api/                 FastAPI research service
  web/                 Next.js bilingual dashboard
packages/
  quant_core/          Python quant engine and YAND-MVSK solver
    oracle.py          Exact sample oracle + CRRA calibration + convexity certificate
    optimizer.py       YAND affine-normal solver (Algorithm 1)
    simplex.py         Projection, tangent basis, KKT residual
    mv.py              Long-only mean-variance baseline
    screening.py       Train-window-only universe screening
    backtest.py        Metrics incl. realized higher moments
    research.py        End-to-end research pipeline
docs/                  Paper-to-code mapping and usage notes
tests/                 Oracle/solver/pipeline verification tests
logo/                  Original FintasTech logo assets
```

## 学术来源与引用

本项目受以下论文启发，非论文作者官方实现。请优先引用原论文：

```bibtex
@article{wang2026yandmvsk,
  title   = {Yau's Affine-Normal Descent for Large-Scale Unrestricted Higher-Moment Portfolio Optimization},
  author  = {Wang, Ya-Juan and Niu, Yi-Shuai and Sheshmani, Artan and Yau, Shing-Tung},
  journal = {arXiv preprint arXiv:2604.25378},
  year    = {2026},
  url     = {https://arxiv.org/abs/2604.25378}
}
```

相关背景：

- Niu, Yi-Shuai, Artan Sheshmani, and Shing-Tung Yau. *Yau's Affine Normal Descent: Algorithmic Framework and Convergence Analysis*. arXiv:2603.28448.
- Niu, Yi-Shuai, Artan Sheshmani, and Shing-Tung Yau. *Affine Normal Directions via Log-Determinant Geometry: Scalable Computation under Sparse Polynomial Structure*. arXiv:2604.01163.
- DeMiguel, Garlappi, Uppal. *Optimal Versus Naive Diversification: How Inefficient is the 1/N Portfolio Strategy?* RFS 2009.（1/N 基线的出处）

## License

代码与文档采用 MIT License，见 [`LICENSE`](LICENSE)。

FintasTech logo 和品牌素材为本项目原创品牌资产，不包含在 MIT License 中。未经项目所有者明确许可，不得复制、改作、再分发或用于其他项目品牌；引用本项目时的合理展示除外。

## 免责声明

本项目帮助用户研究组合配置假设，但它不是投资顾问，不提供投资建议，也不是实盘交易系统。回测结果可能受到数据质量、幸存者偏差、交易成本、流动性、过拟合和市场状态变化影响。任何真实资金决策都应经过独立验证、压力测试和风险控制。

---

## English

**Turn the YAND-MVSK large-scale higher-moment portfolio algorithm into a usable quant research system.**

[中文](#fintastech-yand-mvsk) · [Paper](https://arxiv.org/abs/2604.25378) · [Paper-to-Code](docs/paper-to-code.md) · [MIT License](LICENSE)

> FintasTech is a research and education tool. It is not an investment adviser and does not provide investment advice.

Enter a list of stock tickers. FintasTech downloads market data, screens the universe on the training window only, optimizes MVSK weights with the paper's affine-normal solver, compares against exact mean-variance and equal-weight baselines, and reports out-of-sample risk diagnostics — a research run that used to require manual stitching, completed in minutes.

## Motivation

Most quant tools stop at mean-variance. FintasTech implements the full solver from
[Yau's Affine-Normal Descent for Large-Scale Unrestricted Higher-Moment Portfolio Optimization](https://arxiv.org/abs/2604.25378)
(Wang, Niu, Sheshmani, Yau, 2026).

MVSK is powerful but hard to scale: explicit coskewness/cokurtosis tensors need `Θ(n³+n⁴)` coefficients. The paper's breakthrough is exact sample-oracle computation directly on the return matrix (`O(Tn)` per call), combined with affine-normal descent on the simplex and exact quartic line search. This project implements all four blocks of the paper's Algorithm 1:

1. **Oracle block** — value, gradient, Hessian-vector products, and third-order directional kernels through the centered return matrix; no tensors.
2. **Affine-normal block** — reduced coordinates, Householder frame, regularized tangent solve with the exact-trace **log-determinant correction vector** (where the "affine-normal" name comes from); the assembled direction is provably a descent direction.
3. **Quartic step block** — the restricted objective is an explicit quartic from mixed sample power sums; line search is solved exactly.
4. **Boundary block** — face continuation: when weights hit the long-only floor, the direction is reassembled on the exposed face, so boundary solutions keep Newton-type convergence.

See [docs/paper-to-code.md](docs/paper-to-code.md) for the equation-by-equation mapping.

### Relationship to the official code

As of July 2026 the paper's promised replication package has **not been released** (the "Code and data availability" section is written in future tense, and no repository exists on the authors' GitHub; Prof. Niu's earlier MVSKOPT toolbox uses DC programming, a different algorithm). This project is an **independent third-party open-source implementation**, unaffiliated with the authors. It aims to be a faithful implementation of Algorithm 1 — including the simplex reduction, Householder frame, log-det correction, and face continuation that other public reimplementations omit — wrapped in a complete research platform: data pipeline, leakage-free screening, three-way baseline backtesting, API, and dashboard.

## Core Features

**Solver (`packages/quant_core`)**

- Exact sample oracle: `O(Tn)` value/gradient/HVP/third-order kernels, no higher-order tensors.
- YAND affine-normal direction with exact-trace log-determinant correction, adaptive regularization, and direct (Cholesky) / PCG (matrix-free) configurations.
- Exact quartic line search plus active-face continuation on the simplex; converges to KKT ≤ 1e-7 on convexity-certified instances.
- Paper-standard CRRA(γ) coefficient calibration and the coefficient-only convexity certificate (`3c₃² < 8c₂c₄` ⇒ certified global optimum).

**Research pipeline**

- **No look-ahead screening**: the train/test split happens first; screening only sees the training window.
- **Three-way comparison**: MVSK vs exact mean-variance vs equal-weight 1/N (the famously hard-to-beat naive baseline).
- **Realized-moment verification**: out-of-sample realized skewness and excess kurtosis — the direct test of whether MVSK actually improved the distribution shape.
- Full risk metrics: annual return/vol, Sharpe, Sortino, Calmar, max drawdown, CVaR 1%/5%, active share, effective assets.
- Complete solver diagnostics: per-iteration KKT residual and objective, convergence flag, convexity certificate, wall-clock time.

**Platform**

- Multi-market Yahoo Finance tickers (US / A-shares / HK).
- Local Parquet caching (hash keys, TTL refresh for open-ended ranges).
- FastAPI service with request validation, structured errors, configurable CORS.
- Bilingual Next.js dashboard: full parameter panel (date range, costs, train ratio, CRRA γ), equity curves, out-of-sample comparison table, MV/MVSK weight comparison, KKT convergence chart, and a beginner tutorial.

## Quick Start

```bash
make setup   # once
make dev     # daily: API at :8000, web at :3000
```

Open `http://localhost:3000` and click **Run research**.

```bash
make api    # FastAPI only
make web    # Frontend only
make test   # Python tests + Next.js build
make lint   # ruff static checks
```

Without `make`:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
npm --prefix apps/web install
.venv/bin/uvicorn apps.api.app.main:app --reload
npm --prefix apps/web run dev
```

Environment variables: `NEXT_PUBLIC_API_BASE` points the frontend at the API (default `http://localhost:8000`); `FINTASTECH_CORS_ORIGINS` configures the API's CORS allowlist.

## Methodology notes (why the numbers can be trusted)

- Screening, coefficient scaling, and optimization use the training window only; the test window is reserved for backtesting.
- Backtests charge one-time entry transaction costs (configurable bps).
- The platform reports windows where MVSK loses. The paper's own conclusion is conditional: higher moments add value only when the mandate leaves enough allocation freedom, and the separation from MV is market-window dependent. If MVSK cannot beat 1/N on your window, the dashboard shows exactly that.
- Known limitations (also the roadmap): single static split rather than rolling walk-forward; PCG mode omits the log-det correction by default; no return-targeted frontier comparison yet.

## Ticker Format

Full Yahoo Finance tickers: US `AAPL`/`MSFT`/`NVDA`; A-shares `600519.SS`/`000001.SZ`; Hong Kong `0700.HK`/`9988.HK`.

## Project Layout

```text
apps/
  api/                 FastAPI research service
  web/                 Next.js bilingual dashboard
packages/
  quant_core/          Python quant engine and YAND-MVSK solver
    oracle.py          Exact sample oracle + CRRA calibration + convexity certificate
    optimizer.py       YAND affine-normal solver (Algorithm 1)
    simplex.py         Projection, tangent basis, KKT residual
    mv.py              Long-only mean-variance baseline
    screening.py       Train-window-only universe screening
    backtest.py        Metrics incl. realized higher moments
    research.py        End-to-end research pipeline
docs/                  Paper-to-code mapping and usage notes
tests/                 Oracle/solver/pipeline verification tests
logo/                  Original FintasTech logo assets
```

## Citation

This project is inspired by the following paper and is not the authors' official implementation. Please cite the original paper first:

```bibtex
@article{wang2026yandmvsk,
  title   = {Yau's Affine-Normal Descent for Large-Scale Unrestricted Higher-Moment Portfolio Optimization},
  author  = {Wang, Ya-Juan and Niu, Yi-Shuai and Sheshmani, Artan and Yau, Shing-Tung},
  journal = {arXiv preprint arXiv:2604.25378},
  year    = {2026},
  url     = {https://arxiv.org/abs/2604.25378}
}
```

Related background:

- Niu, Yi-Shuai, Artan Sheshmani, and Shing-Tung Yau. *Yau's Affine Normal Descent: Algorithmic Framework and Convergence Analysis*. arXiv:2603.28448.
- Niu, Yi-Shuai, Artan Sheshmani, and Shing-Tung Yau. *Affine Normal Directions via Log-Determinant Geometry: Scalable Computation under Sparse Polynomial Structure*. arXiv:2604.01163.
- DeMiguel, Garlappi, Uppal. *Optimal Versus Naive Diversification: How Inefficient is the 1/N Portfolio Strategy?* RFS 2009 (source of the 1/N baseline).

## License

Code and documentation are released under the MIT License. See [`LICENSE`](LICENSE).

The FintasTech logo and brand assets are original project assets and are not covered by the MIT License. They may not be copied, modified, redistributed, or used as another project's brand without explicit permission from the project owner, except for reasonable references to this project.

## Disclaimer

This project helps users research portfolio configuration hypotheses. It is not an investment adviser, does not provide investment advice, and is not a live trading system. Backtest results can be distorted by data quality, survivorship bias, transaction costs, liquidity, overfitting, and regime changes. Any real-money decision should be made only after independent validation, stress testing, and risk control.

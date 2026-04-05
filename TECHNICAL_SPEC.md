# Technical Implementation Specification: V11 Trading System
**Project Identifier:** `institutional_trading_loop_v11`
**Status:** Production, "Data Accumulation" Mode

This document explicitly defines the source code, file structures, schemas, class behavior, integration pipelines, and module inter-dependencies required to perfectly reconstruct the trading implementation.

---

## 1. Directory & Service Architecture

The system operates across a clear folder hierarchy where the core abstractions run statically, while the `arena` orchestrates virtual loops and ML handles state-recalculation.

```text
d:\TRADING_SIGNAL\trading_system\
├── .env                        # Root keys, thresholds, settings
├── requirements.txt            # Package definitions (pandas, ccxt, sklearn, scipy, flask, etc)
├── run_247.py                  # Primary entrypoint, fault-tolerant continuous loop + web dashboard
├── run_arena.py                # Standalone arena runner (no ML learning)
├── backtest.py                 # Historical backtest simulator
├── main.py                     # Deprecated entrypoint (redirects to run_247.py)
├── agentsprompt.txt            # Agent design reference (human-readable, NOT consumed at runtime)
├── PRD.md                      # Product Requirements Document
├── TECHNICAL_SPEC.md           # This file
├── GAPs.md                     # Audit findings and remediation tracking
├── PROJECT_AUDIT_REPORT.md     # Final audit summary
├── DEPLOY.md                   # Deployment guide
├── 24_7_DEPLOYMENT_GUIDE.md    # 24/7 deployment instructions
├── Procfile                    # Heroku/Railway process definition
├── runtime.txt                 # Python runtime version pin
├── vercel.json                 # Vercel deployment config
├── deploy/
│   └── railway.toml            # Railway deployment config
├── core/
│   ├── __init__.py
│   ├── logger.py               # Central execution logger (trading_system.log)
│   ├── config.py               # Config singleton via load_dotenv()
│   ├── orchestrator.py         # Legacy orchestration wrapper
│   ├── regime_classifier.py    # 5-regime market state detection
│   ├── tail_risk_sentinel.py   # 7-trigger system-wide kill-switch
│   ├── risk_governor.py        # 6 portfolio-level risk checks
│   ├── diagnostics_engine.py   # PSI drift, performance attribution, error decomposition
│   └── execution_logger.py     # Slippage, market impact, latency tracking
├── engine/                     # Signal & indicator computation
│   ├── __init__.py
│   ├── indicators.py           # Technical indicators (EMA, RSI, MACD, BB, ATR, ADX, Fibonacci)
│   ├── signal_engine.py        # Rule-based signal scoring engine
│   └── risk_calculator.py      # Position sizing & risk validation
├── agents/                     # Data/IO interfaces (legacy, superseded by arena agents)
│   ├── __init__.py
│   ├── data_agent.py           # Async CCXT data puller + engine indicators
│   ├── signal_agent.py         # Signal extraction wrapper
│   ├── risk_agent.py           # Portfolio state constraints
│   ├── execution_agent.py      # Real orders (disabled in Arena mode)
│   ├── journal_agent.py        # Database logger
│   └── briefing_agent.py       # Market briefing generation
├── arena/                      # Competition Environment
│   ├── __init__.py
│   ├── base_agent.py           # Core ABC class with paper logic + ML gate + 4-factor sizing
│   ├── arena_runner.py         # Multi-timeframe cycle orchestrator
│   ├── config.py               # Arena config: symbols, timeframes, TF_SL_MULT, TF_MAX_HOLD
│   ├── leaderboard.py          # ASCII table reporting
│   ├── training_export.py      # CSV performance export + training data loader
│   └── agents/                 # 6 strategy implementations
│       ├── __init__.py
│       ├── ajay.py             # Momentum strategy
│       ├── vijay.py            # Mean-reversion strategy
│       ├── sanjay.py           # Breakout strategy
│       ├── rama.py             # Trend-following strategy
│       ├── meenakshi.py        # Sentiment strategy
│       └── rani.py             # Volatility strategy
├── ml/                         # ML Training & Governance
│   ├── __init__.py
│   ├── trainer.py              # RF/GB pipeline with walk-forward + permutation pruning
│   ├── retrain_scheduler.py    # Stability Contract (6 conditions) + governance + canary
│   ├── strategy_updater.py     # Agent-level performance analysis
│   ├── ab_testing.py           # A/B/AZ capital-isolated partition testing
│   ├── performance_governance.py # 5-gate model evaluation pipeline
│   ├── canary.py               # Staged deployment (10-20% allocation, auto promote/rollback)
│   ├── model_registry.py       # Champion archive, version tracking
│   ├── models/
│   │   ├── trading_model.pkl   # Serialized best model
│   │   └── metrics.json        # Model performance metrics
│   └── strategy_adjustments.json # Per-agent risk adjustment data
├── orders/                     # State persistence (gitignored)
│   ├── (agent)_orders.json     # Serialized agent states
│   ├── training_data.jsonl     # Enriched 28-field training data
│   └── agent_performance_summary.csv # CSV performance export
├── web/                        # Flask Dashboard
│   ├── app.py                  # 14 API routes + SSE + C2 controls + JWT auth
│   ├── templates/
│   │   ├── dashboard.html      # Multi-panel dashboard with MTF matrix
│   │   └── login.html          # JWT login page
│   └── static/
│       ├── css/dashboard.css   # Dark trading theme
│       └── js/dashboard.js     # Live data fetching, SSE, auto-refresh
├── logs/                       # Runtime logs (gitignored)
│   ├── trading_system.log      # Main application log
│   ├── ml_predictions.jsonl    # ML prediction audit trail
│   ├── sentinel_events.jsonl   # Tail-risk trigger events
│   ├── diagnostics.jsonl       # Drift detection alerts
│   ├── governance_decisions.jsonl # Model promotion/rollback decisions
│   ├── canary_events.jsonl     # Canary deployment events
│   ├── stability_contract.jsonl # Retrain contract check results
│   ├── execution_log.jsonl     # Fill-level execution data
│   ├── crash_log.jsonl         # Crash diagnostics
│   ├── c2_actions.jsonl        # Command & Control action audit trail
│   ├── run_state.json          # 24/7 runner state
│   ├── arena_restart_state.json # Arena restart persistence
│   └── health_report.json      # Health check output
├── storage/
│   ├── __init__.py
│   └── database.py             # SQLite journal (legacy, superseded by JSONL)
├── monitor/                    # System health & monitoring
│   ├── __init__.py
│   ├── health_check.py         # System health diagnostics
│   ├── status_dashboard.py     # Terminal status display
│   └── auto_upgrade.py         # Auto-upgrade mechanism
├── alerts/                     # Notification services
│   ├── __init__.py
│   ├── telegram.py             # Telegram bot alerts
│   └── email_alert.py          # SMTP email alerts
└── tests/                      # Unit test suite
    ├── __init__.py
    ├── test_arena.py           # Arena agent tests (18 tests)
    ├── test_indicators.py      # Indicator computation tests (9 tests)
    ├── test_risk.py            # Risk calculator tests (10 tests)
    └── test_signal.py          # Signal engine tests (6 tests)
```

---

## 2. Core Operational Configs & Stack

**Stack Dependencies (`requirements.txt`)**
- Data / Exchange: `ccxt>=4.0.0`, `pandas>=2.0.0`, `numpy>=1.24.0`, `ta>=0.11.0`
- AI / ML: `scikit-learn>=1.3.0`, `scipy>=1.11.0`, `joblib>=1.3.0`
- Web / Automation: `flask>=3.0.0`, `flask-cors>=4.0.0`, `PyJWT>=2.8.0`, `APScheduler>=3.10.0`
- Alerts: `python-telegram-bot>=20.0`, `requests>=2.31.0`
- Testing: `pytest>=7.4.0`, `pytest-asyncio>=0.21.0`
- Utilities: `python-dotenv>=1.0.0`, `pytz>=2023.3`, `aiosqlite>=0.19.0`

**Environment Variables (`.env`)**
Variables are statically instantiated in `core/config.py` as a `Config` singleton class:
- `TRADING_SYMBOLS=BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT`
- `MAX_PORTFOLIO_EXPOSURE=0.30`
- `DAILY_LOSS_CAP=0.03`
- `MAX_DRAWDOWN=0.08`
- `RISK_PER_TRADE=0.01`
- `MIN_CONFIDENCE=65`
- `CYCLE_HOURS=4`

---

## 3. Database & Payload Schemas

### 3.1 Trading Data & Logs
Generated by `BaseAgent._append_training_row()` onto `orders/training_data.jsonl`.
**Format:** Flat JSON Lines (JSONL).
**Schema:**
```json
{
  "agent": "Ajay",
  "strategy": "mean_reversion",
  "symbol": "BTC/USDT",
  "side": "BUY",
  "confidence": 85,
  "features": { "rsi_14": 42.1, "macd_hist": -0.01, "volatility_60": 0.05 },
  "outcome": "WIN",
  "pnl_pct": 2.5,
  "label": 1, 
  "timestamp": "2026-04-05T00:00:00Z",
  "ml_prob_win": 0.65,
  "ml_prediction": 1,
  "regime_at_entry": "mean_reversion",
  "regime_at_exit": "mean_reversion",
  "timeframe": "4h",
  "tf_risk_mult": 1.0,
  "ml_gate_score": 0.65,
  "risk_governor_outcome": "PASS",
  "position_size": 1500,
  "entry_price": 60000,
  "exit_price": 61000,
  "gross_pnl": 1500,
  "net_pnl": 1500,
  "slippage": 0,
  "attribution_label": "signal_alpha",
  "stop_out": false,
  "ml_confidence_factor": 1.5,
  "agent_risk_factor": 1.0,
  "regime_strength_factor": 0.5,
  "vol_scalar_factor": 1.0
}
```

### 3.2 State Object Storage
Managed by `BaseAgent._save_state()` generating e.g. `orders/ajay_orders.json`.
**Schema Overview:**
```json
{
  "agent": "Ajay",
  "strategy": "StrategyName",
  "virtual_capital": 10000.0,
  "peak_capital": 10500.0,
  "daily_start_capital": 10000.0,
  "open_positions": {
    "uuid4_hex": {
      "order_id": "8xhex",
      "symbol": "BTC/USDT",
      "status": "open",
      "entry_price": 60000.0,
      "stop_loss": 58000.0,
      "take_profit": 65000.0
      // ... plus ML scores and regime stamps ...
    }
  },
  "closed_positions": { /* uuid keys mapped to closed order blobs */ },
  "last_updated": "2026-04-05T00:00:00Z"
}
```

---

## 4. Class-Level Execution Pipelines

### 4.1 Continuous State Wrapper (`run_247.py`)
1. **Fault Tolerance**: `check_crash_limits()` uses `logs/run_state.json` to monitor faults (`MAX_RESTARTS_PER_HOUR = 5`, `MAX_CONSECUTIVE_CRASHES = 10`), applying exponential backoff for cooldowns (max 300s).
2. **Initialization**: It establishes the 6 `BaseAgent` implementations and boots the `RetrainScheduler` thread (`interval=3600`, `min_samples=500`). The `RetrainScheduler` now includes `PerformanceGovernance` (5-gate evaluation) and `CanaryDeployer` integration.
3. **Web Dashboard**: Flask app auto-starts as a daemon thread on port 5000 (configurable via `DASHBOARD_PORT` env var).
4. **Execution**: Fires `asyncio.run(runner._run_all_timeframes())`.

### 4.2 MTF Concurrency (`arena/arena_runner.py` & `agents/data_agent.py`)
1. **Asynchronous Scheduling**: `ArenaRunner` maps array elements defined in `TIMEFRAMES` logic to distinct `TimeframeCycle` classes.
2. **Data Pulls**: During each loop, `DataAgent.get_all_indicators()` is called with `asyncio`, utilizing `ccxt` to get exact OHLCV slices from the exchange and recalculating the `ta` indicators specific to each timeframe concurrently.
3. Every Timeframe operates purely decoupled from others natively within the same process.

### 4.3 Position Exit Flow (`arena/base_agent.py:check_exits`)
Positions close through three mechanisms, checked every cycle for every open position:
1. **Stop Loss**: Price hits the predefined stop-loss level → exit with `stop_loss` reason
2. **Take Profit**: Price hits the predefined take-profit level → exit with `take_profit` reason
3. **Max Holding Period**: Position exceeds timeframe-specific time limit → forced exit with `max_holding_period` reason

**Timeframe-Scaled SL/TP**: The base SL/TP from the agent's signal is multiplied by `TF_SL_MULT`:
- 1m: 0.20x, 5m: 0.30x, 15m: 0.40x, 30m: 0.55x, 1h: 0.70x, 2h: 0.85x, 4h: 1.00x

**Max Holding Periods** (`TF_MAX_HOLD`):
- 1m: 1 hour, 5m: 2 hours, 15m: 4 hours, 30m: 8 hours, 1h: 12 hours, 2h: 24 hours, 4h: 48 hours

On exit, `close_position()` calculates PnL, updates capital, and appends an enriched training row with `exit_reason`, regime stamps, and sizing factors.

### 4.4 UI Dashboard (`web/app.py`)
- Standard Flask frontend routing live variables from the arena engine (`get_system_status()`, `get_leaderboard_data()`) to HTML interfaces.

---

## 5. ML Subsystem Details (`ml/trainer.py`)

The ML subsystem exclusively trains on closed-trade metadata.
**Pipeline Operations:**
1. Loads `orders/training_data.jsonl`.
2. Flattens `features` nested dictionary into `X_dicts` appending `.get(label, 0)` to `y`.
3. Limits timeline via `WALK_FORWARD_WINDOW = 500`.
4. Executes Feature Pruning (`_prune_weak_features`): strips columns falling into the bottom 20% (`FEATURE_PRUNE_BOTTOM = 0.20`) of target correlation to prevent overfitting.
5. Employs `RandomForestClassifier(n_estimators=100, max_depth=10)` and `GradientBoostingClassifier(n_estimators=100, max_depth=5, learning_rate=0.1)`.
6. Uses `f1 * 0.6 + accuracy * 0.4` weighting function to declare the best model.
7. Serializes to `ml/models/trading_model.pkl` and `ml/models/metrics.json`.

**ML Cold Start Safety (BaseAgent Execution):**
When the ML model loads, it evaluates its own accuracy. If `accuracy < 0.50`, it assumes the "Cold Start" sequence:
Instead of strictly rejecting sub-threshold signals, it applies a defensive **risk multiplier**:
- `prob_win < 0.35` -> 0.3x Risk
- `prob_win < 0.45` -> 0.6x Risk
- Otherwise -> 0.8x Risk

---

## 6. Logic Integration: The Order Formula

When a Signal Agent produces a directional flag, `BaseAgent.submit_paper_order()` constructs the exact size using:

1. **Stop Distance**: `distance = current_price * stop_loss_pct`
2. **Vol Scalar**: Computes `target_vol(0.02) / realized_vol`. Capped at `min(2.0, max(0.3, scalar))`.
3. **Agent Risk Adj**: Dynamically fetched from `ml/strategy_adjustments.json`.
4. **Final Formula**: 
   `Risk Amount = Virtual Capital * Risk Per Trade (0.01) * ML Risk Multiplier * Agent Risk Adj * Regime Strength * Vol Scalar`
5. **Quantity**: `risk_amount / stop_distance`
6. Concurrently caps absolute portfolio exposure against `MAX_EXPOSURE` (30%).

--- 

## 7. Agent Design Reference (`agentsprompt.txt`)

The `agentsprompt.txt` is a **human-readable specification document** describing the intended behavior, persona, and strategy logic for each of the 6 trading agents. It is **NOT consumed at runtime** — it serves as documentation for developers to understand the design intent behind each agent's signal generation logic. The actual agent implementations live in `arena/agents/*.py`.

---

## 8. Dashboard & Command Center (`web/`)

### 8.1 Authentication
- **Login page** at `/login` with password-based JWT authentication
- **Default password**: `admin` (configurable via `DASHBOARD_PASSWORD` env var or `DASHBOARD_SECRET` for JWT key)
- **Token storage**: localStorage with 24h expiry
- **Auto-login**: On page load, attempts silent login with default password before redirecting
- **Route protection**: All API routes require `Authorization: Bearer <token>` header
- **Role-based access**: Admin role required for C2 controls (`@require_admin` decorator)

### 8.2 API Endpoints
| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/login` | GET | None | Login page |
| `/api/login` | POST | None | Authenticate, returns JWT token |
| `/` | GET | JWT | Dashboard HTML |
| `/api/dashboard` | GET | JWT | Full dashboard data (agents, summary, training, model, V11) |
| `/api/agents` | GET | JWT | Agent status table |
| `/api/health` | GET | JWT | System health check |
| `/api/signals` | GET | JWT | Recent signals with timeframe, regime, ML approval |
| `/api/trades` | GET | JWT | Recent trades with exit reason, sizing factors |
| `/api/model` | GET | JWT | ML model status and metrics |
| `/api/v11` | GET | JWT | Full V11 system status (sentinel, governance, ML stats, C2 log) |
| `/api/mtf-matrix` | GET | JWT | 5×7 asset×timeframe heatmap data |
| `/api/stream` | GET | JWT | SSE real-time event stream |
| `/api/c2/halt-all` | POST | Admin | Halt all new entries |
| `/api/c2/resume-all` | POST | Admin | Resume trading |
| `/api/c2/close-all-positions` | POST | Admin | Force-close all open positions |
| `/api/c2/retrain` | POST | Admin | Force ML model retrain |

### 8.3 SSE Real-Time Events
The `/api/stream` endpoint pushes events to all connected clients:
- `alert` events with types: `HALT`, `RESUME`, `CLOSE_ALL`, `RETRAIN`
- Heartbeat every 30s to keep connection alive
- Auto-reconnect on disconnect with 5s backoff

### 8.4 C2 Action Audit Trail
All admin actions logged to `logs/c2_actions.jsonl`:
```json
{"action": "halt_all", "details": {"triggered_by": "admin"}, "user": "admin", "timestamp": "2026-04-05T02:00:00"}
```

---

## 9. GAP Audit Implementation Status

### Original GAPs (9 gaps) — All Fixed
| # | Gap | File Changed | Status |
|---|---|---|---|
| 1 | min_samples 50→500 | `run_247.py` | ✅ |
| 2 | TF-scaled SL/TP + Max Hold | `arena/config.py`, `arena/base_agent.py` | ✅ |
| 3 | Cold-start prediction bypass | `arena/base_agent.py` | ✅ Verified correct |
| 4 | Permutation importance pruning | `ml/trainer.py` | ✅ |
| 5 | MAX_DRAWDOWN 0.08 | `arena/config.py` | ✅ |
| 6 | File structure update | `TECHNICAL_SPEC.md` §1 | ✅ |
| 7 | Stability Contract 6 conditions | `PRD.md` Stage 10 | ✅ |
| 8 | agentsprompt.txt clarification | `TECHNICAL_SPEC.md` §7 | ✅ |
| 9 | exit_reason in training schema | `arena/base_agent.py` | ✅ |

### Dashboard GAPs (GAPs.md v2) — 5 gaps
| # | Gap | Decision | Rationale |
|---|---|---|---|
| 1 | WebSockets + React | ⏸ Deferred | SSE provides 80% of real-time benefit at 20% effort. React justified only for multi-user. |
| 2 | TradingView Charts | ⏸ Deferred | MTF matrix heatmap provides equivalent clarity. Will add when OHLCV overlay needed. |
| 3 | Risk Visualizations | ✅ Implemented | MTF heatmap + TF performance table + C2 log |
| 4 | JWT Auth | ✅ Implemented | Login page, JWT tokens, protected routes, admin roles |
| 5 | Command & Control | ✅ Implemented | Halt/Resume/Close All/Retrain with audit logging + SSE alerts |

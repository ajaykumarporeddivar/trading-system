# Product Requirements Document (PRD)
## Autonomous Trading Loop v11 (Institutional Grade)

---

## 1. Product Overview
**Name**: V11 Institutional Trading System
**Goal**: A fully autonomous, closed-loop, self-improving, regime-aware, risk-controlled, and tail-risk-protected quantitative trading engine.
**Asset Class**: Cryptocurrencies (BTC, ETH, SOL, BNB, XRP).
**Execution Mode / Timeframe**: 24/7 continuous operation via `run_247.py` operating on 4-hour timeframes and multiple cycling timeframes (MTF).
**Current Status**: Production-Ready / "Data Accumulation" Phase. The system is deployed and currently awaiting sufficient statistical data (N > 500 closed trades) to initiate its first autonomous Retrain Cycle.

---

## 2. Core Architecture & Components
The overarching system revolves around a 17-stage continuous loop combining market regime awareness, agent-based signal generation, machine learning gates, and rigid risk invariant controls.

### 2.1 Multi-Agent Signal Generation
The system utilizes an Arena Runner incorporating 6 individual AI agents:
- **AjayAgent**, **VijayAgent**, **SanjayAgent**, **RamaAgent**, **MeenakshiAgent**, and **RaniAgent**.
- They execute within an isolated `ORDER_DIR` tracking system, continuously computing signals and logging their individual states, outputs, and performance on the leaderboard.

### 2.2 Operational Engine (`run_247.py`) & Arena Runner
- **Continuous Environment**: `run_247.py` provides an automated runstate capable of 24/7 continuity with resilient crash logic (e.g. `MAX_RESTARTS_PER_HOUR = 5`).
- **MTF (Multiple Time Frame) Architecture**: Executed by the `ArenaRunner`, which uses Python `asyncio` to simultaneously manage cycles across distinct timeframes (e.g., `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`).
- **Data Intake**: The `DataAgent` natively fetches Live OHLCV through `ccxt` and computes concurrent mathematical indicators on the fly before passing it down the gauntlet.

### 2.3 Command Dashboard (Web Application)
- A separate Flask-based UI (`web/` directory) exists to visualize the runtime, leaderboard states, and system statistics in a real-time portal.

---

## 3. The 17-Stage Continuous Loop Specification

The trading logic is highly formalized into 17 interconnected bit-level gates. No signal can progress without mathematically clearing each checkpoint. 

### Stage 1: Signal Generation
Agents output a unified, stateless payload containing direction (+1/-1), raw confidence score (0-1), feature vector hashes, and an instrument ID.

### Stage 2: Market Regime Classifier
Strictly categorizes current market conditions into 5 distinct regimes:
1. **Trending** (sustained directional action)
2. **Mean-reversion** (range-bound)
3. **High-volatility** (realized vol > 1.5x 60-day median)
4. **Low-volatility** (realized vol < 0.6x 60-day median)
5. **News/noise-driven** (microstructure noise dominancy)

### Stage 3: ML Gate (Prediction + Regime Alignment)
Evaluates signal approval via the ML model. The gate operates in three modes based on model accuracy:

**Bootstrap Mode** (model accuracy < 50%): Gate acts as scorer only. All signals pass. Position size floored at 15-80% of normal based on prob_win. Risk Governor and Tail-Risk Sentinel remain fully enforced.

**Probation Mode** (50-55% accuracy): Gate blocks if prob_win < 0.30. Position size at 50% of normal.

**Live Mode** (> 55% accuracy): Full blocking at prob_win < 0.30 or prediction == 0. Full dynamic sizing (0.5x-1.5x).

- `P(approve)` must exceed a model-specific threshold (often ~0.55-0.65).
- Regime alignment score must be ≥ 0.5.

### Stage 4: Risk Governor
A strict, downstream risk application logic ensuring portfolio-level safety. 
- Gross/Net Exposure limits.
- Asset concentration ≤ 15% of gross.
- Correlation to existing book ≤ 0.65.
- Max Drawdown ≤ 8% from HWM.

### Stage 5: Tail-Risk Sentinel
An asynchronous, global kill-switch checking for macro breakdowns (1-day 99% VaR, vol spikes > 2.5x, spread explosions > 3x, or liquidity dry-ups). Triggers cause an immediate system-wide halt for new entries.

### Stage 6: Dynamic Position Sizing
Applies a robust sizing formula: `Base Capital x ML Confidence x Risk Adjustment (0-1) x Regime Strength x Volatility Target Scalar`.

### Stage 7: Trade Execution
Logs estimated slippage using market impact models against actual post-fill outcomes. Focuses on minimizing and logging latency from signal-to-execution.

### Stage 8: Trade Close & Data Enrichment
Compiles comprehensive training vectors post-trade (Feature Vector, Entry/Exit, Slippage, Attribution Label, Missing flags). This generates the "causally-complete" data required for the next ML step.

### Stage 9: Diagnostics Engine
A real-time health-monitoring mechanism tracking Drift Detection (PSI > 0.2 alerts, KS-Tests), Performance Attribution, and Error Decomposition (Model vs. Execution vs. Regime error).

### Stage 10: RetrainScheduler + Stability Contract
Blocks retraining until ALL six scientific conditions are satisfied:
- Minimum of 500 new sample enrichments.
- Regime distribution balance (No single regime > 40%).
- Recency weighting > 60% of samples within the last 90 days.
- Variance floor ≥ 80% of historical baseline.
- Data quality < 1% missing values in recent 200 samples.
- PSI/KS drift trigger active OR retrain interval reached.

### Stage 11: Walk-Forward Retrain + Feature Pruning
Generates ML candidates (Top-K = 3-5) via forward-step optimization using regime-specific training windows. Automatically prunes features with <1% relative importance.

### Stage 12: Capital-Isolated A/B/AZ Testing
Orchestrates live evaluation: **A** (Champion), **B** (Candidate), and **AZ** (Always-Zero Baseline) partitions. Limits pairwise return correlation to < 0.5.

### Stage 13: Performance Governance
Enforces a grueling 5-gate pipeline for any candidate to replace the current champion:
1. **Robustness**: OOS Sharpe > 1.2, Calmar > 0.6.
2. **Statistical Power**: Cohen's D > 0.35, p-value < 0.05.
3. **Regime Balance**: Broad testing coverage across structural market behaviors.
4. **Washout**: 30 Days / 100 Trades maintaining a steady Sharpe.
5. **Canary Pass**: Safe execution with 0 Sentinel warnings.

### Stage 14: Canary Deployment
Routes 10-20% live capital flow to the candidate prior to total deployment to benchmark latent slippage/scaling behaviors.

### Stage 15/16: Full Deployment & Recalibration
Candidate model achieves Champion status parameterization updates propagate down, and loop lifecycle statistics gracefully reset for the Next Cycle. 

---

## 4. System Invariants (Non-Negotiable Constraints)
To maintain the required Institutional Grade standard, the platform architecture enforces absolute operational invariants:
1. **Causal Fidelity**: Zero leakages of future data in `training_data.jsonl`, achieved through strict execution timestamping.
2. **Mandatory Clearance Checkpoints**: No execution can bypass ML gating *or* Risk Gov clearances.
3. **Transparent Traceability**: Explicit reason logging (e.g., `ML_SCORE_BELOW_THRESHOLD`, `DRAWDOWN_LIMIT_BREACH`, `max_holding_period`) is permanently mandated.
4. **Timeframe-Aware Exits**: Every position has a max holding period (1m→1h, 4h→48h) to prevent indefinite open positions.

### 4.1 Training Data Quality Management
When V11-enriched rows reach 333+, the system automatically purges all pre-V11 rows (which lack regime stamps, timeframe tags, and sizing factors). This ensures the ML model trains only on high-quality, causally-complete data.

## 5. Deployment / Roadmap Action Plan
- **Implementation Status**: 100% components mapped and active. `main.py` is fully superseded by `run_247.py`.
- **Immediate Path**: Operational waiting state for ML model data accumulation (~48% starting accuracy expected). The current runstate protects base capital purely through dynamic risk discounting (multiplier 0.3x-0.8x) while building the dataset library towards the N=500 target.
- **Exit Mechanism**: Positions close via SL/TP (timeframe-scaled) or max holding period. 1m positions close within 1 hour max, 4h within 48 hours.

## 6. Dashboard & Command Center
- **Authentication**: JWT-based login at `/login` (default password: `admin`). All API routes protected. Token auto-refreshes on page load via silent auto-login.
- **SSE Real-Time Alerts**: Server-sent events push instant notifications for sentinel triggers, ML retrains, C2 actions, and position closes.
- **MTF Matrix**: 5 assets × 7 timeframes heatmap showing regime state, open positions, and ML probability per cell.
- **C2 Controls** (Admin only): Halt All Entries, Resume Trading, Close All Positions, Force ML Retrain. All actions logged to `logs/c2_actions.jsonl`.
- **Auto-Refresh**: Dashboard data every 10s, MTF matrix every 15s, SSE for instant alerts.

## 7. GAP Audit Status

### Original 9 Gaps — All Fixed ✅
| Gap | Fix | File |
|---|---|---|
| 1. min_samples 50→500 | Default changed to 500 | `run_247.py` |
| 2. TF-scaled SL/TP + Max Hold | `TF_SL_MULT` + `TF_MAX_HOLD` | `arena/config.py`, `base_agent.py` |
| 3. Cold-start prediction bypass | Already correct — verified | `base_agent.py` |
| 4. Permutation importance pruning | sklearn permutation_importance | `ml/trainer.py` |
| 5. MAX_DRAWDOWN 0.08 | Aligned to 0.08 | `arena/config.py` |
| 6. File structure updated | Full 25+ file listing | `TECHNICAL_SPEC.md` §1 |
| 7. Stability Contract 6 conditions | All 6 documented | `PRD.md` Stage 10 |
| 8. agentsprompt.txt clarified | Human-readable spec note | `TECHNICAL_SPEC.md` §7 |
| 9. exit_reason in training schema | Added field | `base_agent.py` |

### Dashboard GAPs (GAPs.md v2) — 3 Implemented, 2 Deferred
| Gap | Status | Details |
|---|---|---|
| 1. WebSockets + React | ⏸ Deferred | SSE provides 80% real-time benefit at 20% effort. React justified only for multi-user external clients. |
| 2. TradingView Charts | ⏸ Deferred | MTF matrix heatmap provides equivalent visual clarity. Will add when OHLCV overlay needed. |
| 3. Risk Visualizations | ✅ Implemented | MTF heatmap (5×7 grid) + per-TF performance table + C2 action log |
| 4. JWT Auth | ✅ Implemented | Login page, JWT tokens, protected routes, admin vs view-only roles, auto-login |
| 5. Command & Control | ✅ Implemented | Halt/Resume/Close All/Retrain with audit logging + SSE broadcast |

## 6. Dashboard & Command Center
- **Authentication**: JWT-based login at `/login` (default password: `admin`). All API routes protected. Token auto-refreshes on page load.
- **SSE Real-Time Alerts**: Server-sent events push instant notifications for sentinel triggers, ML retrains, C2 actions, and position closes.
- **MTF Matrix**: 5 assets × 7 timeframes heatmap showing regime state, open positions, and ML probability per cell.
- **C2 Controls** (Admin only): Halt All Entries, Resume Trading, Close All Positions, Force ML Retrain. All actions logged to `logs/c2_actions.jsonl`.
- **Auto-Refresh**: Dashboard data every 10s, MTF matrix every 15s, SSE for instant alerts.

## 7. GAP Audit Status (from GAPs.md)

### Implemented (All 9 Gaps Fixed)
| Gap | Status | Implementation |
|---|---|---|
| 1. min_samples 50→500 | ✅ Done | `run_247.py` default changed to 500 |
| 2. TF-scaled SL/TP + Max Hold | ✅ Done | `TF_SL_MULT` (0.20x-1.00x) + `TF_MAX_HOLD` (1h-48h) |
| 3. Cold-start prediction bypass | ✅ Verified | Already correct — prediction==0 only checked after accuracy >= 0.50 |
| 4. Permutation importance pruning | ✅ Done | `_prune_weak_features()` now uses sklearn permutation_importance |
| 5. MAX_DRAWDOWN 0.08 | ✅ Done | `arena/config.py` aligned to 0.08 |
| 6. File structure in TECHNICAL_SPEC | ✅ Done | Updated with all 25+ files, correct paths |
| 7. Stability Contract conditions | ✅ Done | PRD Stage 10 now lists all 6 conditions |
| 8. agentsprompt.txt role clarified | ✅ Done | TECHNICAL_SPEC §7 clarified as human-readable spec |
| 9. exit_reason in training schema | ✅ Done | Added `exit_reason` field to training row |

### Dashboard GAPs (GAPs.md v2)
| Gap | Status | Implementation |
|---|---|---|
| 1. WebSockets + React | ⏸ Deferred | SSE provides real-time push at 20% effort for 80% benefit. React rewrite justified only for multi-user. |
| 2. TradingView Charts | ⏸ Deferred | MTF matrix heatmap provides equivalent visual clarity for current data density. Will add when OHLCV overlay needed. |
| 3. Risk Visualizations | ✅ Done | MTF matrix heatmap + per-timeframe performance table + C2 action log |
| 4. JWT Auth | ✅ Done | Login page, JWT tokens, protected API routes, admin vs view-only roles |
| 5. Command & Control | ✅ Done | Halt/Resume/Close All/Retrain buttons with audit logging and SSE alerts |

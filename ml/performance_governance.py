# ml/performance_governance.py
import json
import os
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.logger import logger

GOVERNANCE_LOG = 'logs/governance_decisions.jsonl'

GATE1_OOS_SHARPE = 1.2
GATE1_OOS_CALMAR = 0.6
GATE1_MAX_DD = 0.08
GATE1_TURNOVER_VAR = 0.15
GATE1_MIN_TRADES_LOW_VOL = 180
GATE1_MIN_TRADES_HIGH_VOL = 250

GATE2_COHENS_D = 0.35
GATE2_P_VALUE = 0.05
GATE2_VARIANCE_RATIO = 1.6
GATE2_CORRELATION = 0.5

GATE3_MIN_REGIME_COVERAGE = 0.20
GATE3_MAX_NOISE = 0.20

GATE4_WASHOUT_DAYS = 30
GATE4_WASHOUT_TRADES = 100
GATE4_SHARPE_FLOOR = 0.7
GATE4_DD_MULTIPLIER = 1.25
GATE4_STOP_OUT_RATE = 0.15

GATE5_LATENCY_MS = 5
GATE5_SLIPPAGE_DRIFT = 0.10


class PerformanceGovernance:
    def __init__(self):
        self._partition_returns: Dict[str, List[float]] = {}
        self._partition_trades: Dict[str, List[Dict[str, Any]]] = {}

    def record_partition_trade(self, partition: str, trade: Dict[str, Any]):
        if partition not in self._partition_returns:
            self._partition_returns[partition] = []
            self._partition_trades[partition] = []
        self._partition_returns[partition].append(trade.get('pnl_pct', 0))
        self._partition_trades[partition].append(trade)

    def evaluate_candidate(self, candidate_model: str, champion_model: str = 'A',
                           az_model: str = 'AZ') -> Dict[str, Any]:
        if candidate_model not in self._partition_trades:
            return {'status': 'insufficient_data', 'reason': f'No trades for {candidate_model}'}

        gates = {
            'gate1_robustness': self._gate1_robustness(candidate_model),
            'gate2_statistical_power': self._gate2_statistical_power(candidate_model, az_model),
            'gate3_regime_balance': self._gate3_regime_balance(candidate_model),
            'gate4_washout': self._gate4_washout(candidate_model),
            'gate5_canary': self._gate5_canary(candidate_model)
        }

        all_pass = all(g.get('passed', False) for g in gates.values())
        decision = 'PROMOTED' if all_pass else 'RETURNED'

        result = {
            'candidate': candidate_model,
            'champion': champion_model,
            'decision': decision,
            'gates': gates,
            'timestamp': datetime.now().isoformat()
        }

        self._log_decision(result)
        logger.info(f'Governance: {candidate_model} -> {decision} | Gates: {sum(1 for g in gates.values() if g.get("passed"))}/5')
        return result

    def _gate1_robustness(self, model: str) -> Dict[str, Any]:
        trades = self._partition_trades.get(model, [])
        returns = self._partition_returns.get(model, [])
        if len(returns) < 50:
            return {'passed': False, 'reason': 'insufficient_trades', 'trades': len(returns)}

        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0

        cumulative = np.cumsum(returns)
        peak = np.maximum.accumulate(cumulative)
        drawdowns = peak - cumulative
        max_dd = np.max(drawdowns) if len(drawdowns) > 0 else 0
        calmar = (cumulative[-1] / max_dd) if max_dd > 0 else 0

        regime = self._get_dominant_regime(trades)
        min_trades = GATE1_MIN_TRADES_HIGH_VOL if regime == 'high_volatility' else GATE1_MIN_TRADES_LOW_VOL

        passed = (
            sharpe >= GATE1_OOS_SHARPE and
            calmar >= GATE1_OOS_CALMAR and
            max_dd <= GATE1_MAX_DD and
            len(returns) >= min_trades
        )

        return {
            'passed': passed,
            'sharpe': round(sharpe, 3),
            'calmar': round(calmar, 3),
            'max_drawdown': round(max_dd, 4),
            'trades': len(returns),
            'min_required': min_trades
        }

    def _gate2_statistical_power(self, model: str, az_model: str) -> Dict[str, Any]:
        model_returns = self._partition_returns.get(model, [])
        az_returns = self._partition_returns.get(az_model, [0])

        if len(model_returns) < 30:
            return {'passed': False, 'reason': 'insufficient_samples'}

        from scipy import stats
        t_stat, p_value = stats.ttest_ind(model_returns, az_returns)

        model_mean = np.mean(model_returns)
        model_std = np.std(model_returns)
        az_mean = np.mean(az_returns)
        az_std = np.std(az_returns)

        pooled_std = np.sqrt((model_std**2 + az_std**2) / 2) if (model_std**2 + az_std**2) > 0 else 1
        cohens_d = abs(model_mean - az_mean) / pooled_std

        if len(model_returns) > 1 and len(az_returns) > 1:
            variance_ratio = max(np.var(model_returns), np.var(az_returns)) / min(np.var(model_returns), np.var(az_returns)) if min(np.var(model_returns), np.var(az_returns)) > 0 else 0
        else:
            variance_ratio = 0

        passed = (
            cohens_d >= GATE2_COHENS_D and
            p_value <= GATE2_P_VALUE and
            variance_ratio < GATE2_VARIANCE_RATIO
        )

        return {
            'passed': passed,
            'cohens_d': round(cohens_d, 3),
            'p_value': round(p_value, 4),
            'variance_ratio': round(variance_ratio, 3)
        }

    def _gate3_regime_balance(self, model: str) -> Dict[str, Any]:
        trades = self._partition_trades.get(model, [])
        if len(trades) < 50:
            return {'passed': False, 'reason': 'insufficient_trades'}

        regime_counts = {}
        for t in trades:
            regime = t.get('regime_at_entry', 'unknown')
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        total = len(trades)
        required_regimes = ['trending', 'mean_reversion', 'high_volatility', 'low_volatility']
        balanced = True
        coverage = {}

        for regime in required_regimes:
            pct = regime_counts.get(regime, 0) / total
            coverage[regime] = round(pct, 3)
            if pct < GATE3_MIN_REGIME_COVERAGE:
                balanced = False

        noise_pct = regime_counts.get('news_noise', 0) / total
        if noise_pct > GATE3_MAX_NOISE:
            balanced = False

        return {
            'passed': balanced,
            'coverage': coverage,
            'noise_pct': round(noise_pct, 3),
            'total_trades': total
        }

    def _gate4_washout(self, model: str) -> Dict[str, Any]:
        trades = self._partition_trades.get(model, [])
        if len(trades) < GATE4_WASHOUT_TRADES:
            return {'passed': False, 'reason': 'insufficient_washout_trades', 'trades': len(trades)}

        washout_trades = trades[:GATE4_WASHOUT_TRADES]
        returns = [t.get('pnl_pct', 0) for t in washout_trades]

        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0

        cumulative = np.cumsum(returns)
        peak = np.maximum.accumulate(cumulative)
        max_dd = np.max(peak - cumulative) if len(cumulative) > 0 else 0

        stop_outs = sum(1 for t in washout_trades if t.get('stop_out', False))
        stop_rate = stop_outs / len(washout_trades) if washout_trades else 0

        passed = (
            sharpe >= GATE4_SHARPE_FLOOR and
            max_dd <= GATE4_DD_MULTIPLIER * 0.08 and
            stop_rate <= GATE4_STOP_OUT_RATE
        )

        return {
            'passed': passed,
            'washout_sharpe': round(sharpe, 3),
            'washout_max_dd': round(max_dd, 4),
            'stop_out_rate': round(stop_rate, 3),
            'trades_analyzed': len(washout_trades)
        }

    def _gate5_canary(self, model: str) -> Dict[str, Any]:
        trades = self._partition_trades.get(model, [])
        if not trades:
            return {'passed': False, 'reason': 'no_canary_data'}

        sentinel_triggers = sum(1 for t in trades if t.get('sentinel_triggered', False))
        latency_breaches = sum(1 for t in trades if t.get('latency_ms', 0) > GATE5_LATENCY_MS * 1000)

        passed = sentinel_triggers == 0 and latency_breaches == 0
        return {
            'passed': passed,
            'sentinel_triggers': sentinel_triggers,
            'latency_breaches': latency_breaches,
            'canary_trades': len(trades)
        }

    def _get_dominant_regime(self, trades: List[Dict[str, Any]]) -> str:
        counts = {}
        for t in trades:
            regime = t.get('regime_at_entry', 'unknown')
            counts[regime] = counts.get(regime, 0) + 1
        return max(counts, key=counts.get) if counts else 'unknown'

    def _log_decision(self, result: Dict[str, Any]):
        try:
            os.makedirs('logs', exist_ok=True)
            with open(GOVERNANCE_LOG, 'a') as f:
                f.write(json.dumps(result) + '\n')
        except Exception as e:
            logger.error(f'Failed to log governance decision: {e}')

# core/diagnostics_engine.py
import json
import os
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from core.logger import logger

DIAGNOSTICS_LOG = 'logs/diagnostics.jsonl'
PSI_ALERT_THRESHOLD = 0.20
KS_P_THRESHOLD = 0.05


class DiagnosticsEngine:
    def __init__(self):
        self._feature_baselines: Dict[str, Dict[str, float]] = {}
        self._score_baselines: List[float] = []
        self._trade_records: List[Dict[str, Any]] = []
        self._diagnostics_history: List[Dict[str, Any]] = []

    def update_feature_baseline(self, features: Dict[str, float]):
        for key, value in features.items():
            if isinstance(value, (int, float)) and value is not None and not np.isnan(value):
                if key not in self._feature_baselines:
                    self._feature_baselines[key] = {'values': [], 'count': 0}
                self._feature_baselines[key]['values'].append(value)
                self._feature_baselines[key]['count'] += 1
                if len(self._feature_baselines[key]['values']) > 1000:
                    self._feature_baselines[key]['values'] = self._feature_baselines[key]['values'][-1000:]

    def check_drift(self, current_features: Dict[str, float]) -> Dict[str, Any]:
        drift_alerts = []

        for key, value in current_features.items():
            if key not in self._feature_baselines:
                continue
            baseline = self._feature_baselines[key]
            if baseline['count'] < 30:
                continue

            baseline_values = baseline['values']
            psi = self._compute_psi(baseline_values, [value])
            if psi > PSI_ALERT_THRESHOLD:
                drift_alerts.append({
                    'feature': key,
                    'psi': round(psi, 4),
                    'threshold': PSI_ALERT_THRESHOLD,
                    'baseline_mean': round(np.mean(baseline_values), 6),
                    'current_value': round(value, 6)
                })

        score_ks = self._check_score_drift(current_features)

        result = {
            'drift_detected': len(drift_alerts) > 0,
            'psi_alerts': drift_alerts,
            'ks_alert': score_ks,
            'timestamp': datetime.now().isoformat()
        }

        if drift_alerts or score_ks:
            logger.warning(f'Drift detected: {len(drift_alerts)} PSI alerts, KS={score_ks}')

        self._diagnostics_history.append(result)
        if len(self._diagnostics_history) > 500:
            self._diagnostics_history = self._diagnostics_history[-500:]

        self._log_diagnostic(result)
        return result

    def record_trade(self, trade: Dict[str, Any]):
        self._trade_records.append(trade)
        if len(self._trade_records) > 5000:
            self._trade_records = self._trade_records[-5000:]

    def compute_attribution(self) -> Dict[str, Any]:
        if len(self._trade_records) < 10:
            return {'status': 'insufficient_data', 'trades_analyzed': len(self._trade_records)}

        closed = [t for t in self._trade_records if t.get('pnl') is not None and t.get('status') == 'closed']
        if len(closed) < 10:
            return {'status': 'insufficient_closed_trades', 'closed_count': len(closed)}

        total_pnl = sum(t.get('pnl', 0) for t in closed)
        wins = [t for t in closed if t.get('pnl', 0) > 0]
        losses = [t for t in closed if t.get('pnl', 0) <= 0]

        signal_alpha = sum(t.get('pnl', 0) for t in closed)
        execution_cost = sum(t.get('slippage', 0) for t in closed if t.get('slippage'))
        regime_contribution = self._estimate_regime_contribution(closed)

        pnls = [t.get('pnl', 0) for t in closed]
        rolling_sharpe = self._compute_rolling_sharpe(pnls, window=50)
        calmar = self._compute_calmar(closed)

        return {
            'total_pnl': round(total_pnl, 2),
            'total_trades': len(closed),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(len(wins) / len(closed) * 100, 1) if closed else 0,
            'avg_pnl': round(total_pnl / len(closed), 2) if closed else 0,
            'signal_alpha': round(signal_alpha, 2),
            'execution_cost': round(execution_cost, 2),
            'regime_contribution': round(regime_contribution, 2),
            'rolling_sharpe': round(rolling_sharpe, 3),
            'calmar_ratio': round(calmar, 3),
            'best_trade': round(max(pnls), 2) if pnls else 0,
            'worst_trade': round(min(pnls), 2) if pnls else 0,
            'timestamp': datetime.now().isoformat()
        }

    def decompose_errors(self) -> Dict[str, Any]:
        if len(self._trade_records) < 10:
            return {'status': 'insufficient_data'}

        closed = [t for t in self._trade_records if t.get('pnl') is not None and t.get('status') == 'closed']
        if len(closed) < 10:
            return {'status': 'insufficient_closed_trades'}

        model_errors = 0
        execution_errors = 0
        regime_errors = 0

        for t in closed:
            ml_prob = t.get('ml_prob_win', 0.5)
            pnl = t.get('pnl', 0)
            regime_entry = t.get('regime_at_entry', '')
            regime_exit = t.get('regime_at_exit', '')

            if ml_prob > 0.6 and pnl < 0:
                model_errors += 1
            elif ml_prob > 0.6 and pnl > 0 and t.get('slippage', 0) > abs(pnl) * 0.5:
                execution_errors += 1
            elif regime_entry != regime_exit and pnl < 0:
                regime_errors += 1

        total = len(closed)
        return {
            'total_trades_analyzed': total,
            'model_errors': model_errors,
            'model_error_rate': round(model_errors / total * 100, 1) if total else 0,
            'execution_errors': execution_errors,
            'execution_error_rate': round(execution_errors / total * 100, 1) if total else 0,
            'regime_errors': regime_errors,
            'regime_error_rate': round(regime_errors / total * 100, 1) if total else 0,
            'unclassified': total - model_errors - execution_errors - regime_errors,
            'timestamp': datetime.now().isoformat()
        }

    def get_diagnostics_summary(self) -> Dict[str, Any]:
        return {
            'attribution': self.compute_attribution(),
            'error_decomposition': self.decompose_errors(),
            'drift_alerts_count': sum(1 for d in self._diagnostics_history if d.get('drift_detected')),
            'total_diagnostics': len(self._diagnostics_history),
            'timestamp': datetime.now().isoformat()
        }

    def _compute_psi(self, baseline: List[float], current: List[float]) -> float:
        if len(baseline) < 10 or len(current) < 1:
            return 0.0

        baseline_mean = np.mean(baseline)
        baseline_std = np.std(baseline)
        if baseline_std == 0:
            return 0.0

        bins = np.linspace(baseline_mean - 3 * baseline_std, baseline_mean + 3 * baseline_std, 11)
        baseline_hist, _ = np.histogram(baseline, bins=bins)
        current_hist, _ = np.histogram(current, bins=bins)

        baseline_pct = (baseline_hist + 1) / (len(baseline) + len(bins))
        current_pct = (current_hist + 1) / (len(current) + len(bins))

        psi = sum((c - b) * np.log(c / b) for c, b in zip(current_pct, baseline_pct))
        return max(0, psi)

    def _check_score_drift(self, current_features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        ml_prob = current_features.get('ml_prob_win')
        if ml_prob is None:
            return None

        self._score_baselines.append(ml_prob)
        if len(self._score_baselines) > 500:
            self._score_baselines = self._score_baselines[-500:]

        if len(self._score_baselines) < 100:
            return None

        from scipy import stats
        recent = self._score_baselines[-50:]
        older = self._score_baselines[:-50]

        ks_stat, p_value = stats.ks_2samp(older, recent)
        if p_value < KS_P_THRESHOLD:
            return {
                'detected': True,
                'ks_statistic': round(ks_stat, 4),
                'p_value': round(p_value, 4),
                'threshold': KS_P_THRESHOLD
            }
        return None

    def _estimate_regime_contribution(self, closed_trades: List[Dict[str, Any]]) -> float:
        regime_pnls = {}
        for t in closed_trades:
            regime = t.get('regime_at_entry', 'unknown')
            if regime not in regime_pnls:
                regime_pnls[regime] = []
            regime_pnls[regime].append(t.get('pnl', 0))

        total = 0
        for regime, pnls in regime_pnls.items():
            total += sum(pnls) * (1 if regime == 'trending' else 0.5)
        return total

    def _compute_rolling_sharpe(self, pnls: List[float], window: int = 50) -> float:
        if len(pnls) < window:
            window = len(pnls)
        if window < 5:
            return 0.0
        recent = pnls[-window:]
        mean = np.mean(recent)
        std = np.std(recent)
        if std == 0:
            return 0.0
        return mean / std * np.sqrt(252)

    def _compute_calmar(self, closed_trades: List[Dict[str, Any]]) -> float:
        if not closed_trades:
            return 0.0

        cumulative = 0
        peak = 0
        max_dd = 0
        for t in closed_trades:
            cumulative += t.get('pnl', 0)
            peak = max(peak, cumulative)
            dd = peak - cumulative
            max_dd = max(max_dd, dd)

        if max_dd == 0:
            return 0.0
        return cumulative / max_dd

    def _log_diagnostic(self, result: Dict[str, Any]):
        try:
            os.makedirs('logs', exist_ok=True)
            with open(DIAGNOSTICS_LOG, 'a') as f:
                f.write(json.dumps(result) + '\n')
        except Exception as e:
            logger.error(f'Failed to log diagnostic: {e}')

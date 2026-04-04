# ml/ab_testing.py
import json
import os
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.logger import logger

AB_LOG = 'logs/ab_test_results.jsonl'
MIN_TEST_DAYS = 30
MIN_TEST_TRADES = 100
MAX_VARIANCE_RATIO = 1.6
MAX_CORRELATION = 0.5


class ABTesting:
    def __init__(self, total_capital: float = 60000, n_candidates: int = 2):
        self.total_capital = total_capital
        self.n_candidates = n_candidates
        self.champion_allocation = 0.60
        self.candidate_allocation = (1.0 - self.champion_allocation - 0.05) / n_candidates
        self.az_allocation = 0.05
        self._partitions: Dict[str, Dict[str, Any]] = {}
        self._setup_partitions()

    def _setup_partitions(self):
        self._partitions = {
            'A': {
                'model': 'champion',
                'allocation': self.champion_allocation,
                'capital': self.total_capital * self.champion_allocation,
                'trades': [],
                'returns': [],
                'start_date': datetime.now().isoformat()
            },
            'AZ': {
                'model': 'zero_baseline',
                'allocation': self.az_allocation,
                'capital': self.total_capital * self.az_allocation,
                'trades': [],
                'returns': [],
                'start_date': datetime.now().isoformat()
            }
        }
        for i in range(self.n_candidates):
            name = f'B{i+1}'
            self._partitions[name] = {
                'model': f'candidate_{i+1}',
                'allocation': self.candidate_allocation,
                'capital': self.total_capital * self.candidate_allocation,
                'trades': [],
                'returns': [],
                'start_date': datetime.now().isoformat()
            }

    def record_trade(self, partition: str, trade: Dict[str, Any]):
        if partition not in self._partitions:
            logger.warning(f'Unknown partition: {partition}')
            return
        self._partitions[partition]['trades'].append(trade)
        self._partitions[partition]['returns'].append(trade.get('pnl_pct', 0))

    def check_readiness(self) -> Dict[str, Any]:
        results = {}
        for name, partition in self._partitions.items():
            trades = partition['trades']
            n_trades = len(trades)
            start = datetime.fromisoformat(partition['start_date'])
            days = (datetime.now() - start).days

            ready = n_trades >= MIN_TEST_TRADES or days >= MIN_TEST_DAYS
            results[name] = {
                'ready': ready,
                'trades': n_trades,
                'days': days,
                'min_trades': MIN_TEST_TRADES,
                'min_days': MIN_TEST_DAYS
            }

        all_ready = all(r['ready'] for r in results.values())
        return {'partitions': results, 'all_ready': all_ready}

    def evaluate_partitions(self) -> Dict[str, Any]:
        readiness = self.check_readiness()
        if not readiness['all_ready']:
            return {'status': 'not_ready', 'details': readiness}

        partition_stats = {}
        for name, partition in self._partitions.items():
            returns = partition['returns']
            if not returns:
                continue
            mean_ret = np.mean(returns)
            std_ret = np.std(returns)
            sharpe = (mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0
            cumulative = np.cumsum(returns)
            peak = np.maximum.accumulate(cumulative)
            max_dd = np.max(peak - cumulative) if len(cumulative) > 0 else 0

            partition_stats[name] = {
                'trades': len(returns),
                'total_return': round(sum(returns), 2),
                'sharpe': round(sharpe, 3),
                'max_drawdown': round(max_dd, 4),
                'win_rate': round(sum(1 for r in returns if r > 0) / len(returns) * 100, 1)
            }

        correlation_check = self._check_correlations()
        variance_check = self._check_variance_ratios()

        winner = max(partition_stats.items(), key=lambda x: x[1]['sharpe']) if partition_stats else None

        result = {
            'partition_stats': partition_stats,
            'correlations_ok': correlation_check['ok'],
            'variance_ratios_ok': variance_check['ok'],
            'correlations': correlation_check['matrix'],
            'variance_ratios': variance_check['ratios'],
            'recommended_winner': winner[0] if winner else None,
            'timestamp': datetime.now().isoformat()
        }

        self._log_result(result)
        return result

    def _check_correlations(self) -> Dict[str, Any]:
        partitions_with_returns = {
            k: v for k, v in self._partitions.items()
            if len(v['returns']) >= 30
        }

        if len(partitions_with_returns) < 2:
            return {'ok': True, 'matrix': {}}

        names = list(partitions_with_returns.keys())
        returns_arrays = [partitions_with_returns[n]['returns'] for n in names]
        min_len = min(len(r) for r in returns_arrays)
        returns_arrays = [r[:min_len] for r in returns_arrays]

        corr_matrix = np.corrcoef(returns_arrays)
        matrix = {}
        ok = True
        for i, n1 in enumerate(names):
            for j, n2 in enumerate(names):
                if i < j:
                    corr = corr_matrix[i][j]
                    matrix[f'{n1}_vs_{n2}'] = round(float(corr), 3)
                    if abs(corr) > MAX_CORRELATION:
                        ok = False

        return {'ok': ok, 'matrix': matrix}

    def _check_variance_ratios(self) -> Dict[str, Any]:
        partitions_with_returns = {
            k: v for k, v in self._partitions.items()
            if len(v['returns']) >= 30
        }

        names = list(partitions_with_returns.keys())
        ratios = {}
        ok = True
        for i, n1 in enumerate(names):
            for j, n2 in enumerate(names):
                if i < j:
                    v1 = np.var(partitions_with_returns[n1]['returns'])
                    v2 = np.var(partitions_with_returns[n2]['returns'])
                    if v1 > 0 and v2 > 0:
                        ratio = max(v1, v2) / min(v1, v2)
                        key = f'{n1}_vs_{n2}'
                        ratios[key] = round(float(ratio), 3)
                        if ratio > MAX_VARIANCE_RATIO:
                            ok = False

        return {'ok': ok, 'ratios': ratios}

    def _log_result(self, result: Dict[str, Any]):
        try:
            os.makedirs('logs', exist_ok=True)
            with open(AB_LOG, 'a') as f:
                f.write(json.dumps(result) + '\n')
        except Exception as e:
            logger.error(f'Failed to log A/B test result: {e}')

    def get_partition_status(self) -> Dict[str, Any]:
        return {
            name: {
                'model': p['model'],
                'allocation': p['allocation'],
                'capital': round(p['capital'], 2),
                'trades': len(p['trades']),
                'total_return': round(sum(p['returns']), 2) if p['returns'] else 0
            }
            for name, p in self._partitions.items()
        }

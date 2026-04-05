# ml/canary.py
import json
import os
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from core.logger import logger

CANARY_LOG = 'logs/canary_events.jsonl'
CANARY_ALLOCATION_PCT = 0.15
CANARY_MONITOR_DAYS = 5
CANARY_SHARPE_FLOOR = 0.7
CANARY_MAX_DD_MULTIPLIER = 1.25
CANARY_SLIPPAGE_DRIFT = 0.10


class CanaryDeployer:
    def __init__(self, model_id: str = None):
        self.model_id = model_id or 'unknown'
        self._active = False
        self._start_time: Optional[datetime] = None
        self._trades: List[Dict[str, Any]] = []
        self._returns: List[float] = []
        self._baseline_slippage: float = 0
        self._sentinel_triggers: int = 0

    def activate(self, baseline_slippage: float = 0):
        self._active = True
        self._start_time = datetime.now()
        self._trades = []
        self._returns = []
        self._baseline_slippage = baseline_slippage
        self._sentinel_triggers = 0
        logger.info(f'Canary activated for model {self.model_id}')
        self._log_event('activated')

    def record_trade(self, trade: Dict[str, Any]):
        if not self._active:
            return
        self._trades.append(trade)
        self._returns.append(trade.get('pnl_pct', 0))
        if trade.get('sentinel_triggered', False):
            self._sentinel_triggers += 1

    def check_status(self) -> Dict[str, Any]:
        if not self._active:
            return {'status': 'inactive'}

        elapsed = datetime.now() - self._start_time
        days = elapsed.days
        n_trades = len(self._trades)

        ready_for_decision = days >= CANARY_MONITOR_DAYS or n_trades >= 100

        sharpe = self._compute_sharpe()
        max_dd = self._compute_max_dd()
        slippage_drift = self._compute_slippage_drift()

        safety_checks = {
            'sharpe_above_floor': sharpe >= CANARY_SHARPE_FLOOR,
            'dd_within_bounds': max_dd <= CANARY_MAX_DD_MULTIPLIER * 0.08,
            'slippage_acceptable': slippage_drift <= CANARY_SLIPPAGE_DRIFT,
            'no_sentinel_triggers': self._sentinel_triggers == 0
        }

        all_clear = all(safety_checks.values())
        rollback = not all_clear and n_trades >= 5

        status = 'monitoring'
        if ready_for_decision and all_clear:
            status = 'promote'
        elif rollback:
            status = 'rollback'

        result = {
            'model': self.model_id,
            'status': status,
            'days_elapsed': days,
            'trades': n_trades,
            'ready_for_decision': ready_for_decision,
            'sharpe': round(sharpe, 3),
            'max_drawdown': round(max_dd, 4),
            'slippage_drift': round(slippage_drift, 4),
            'sentinel_triggers': self._sentinel_triggers,
            'safety_checks': safety_checks,
            'timestamp': datetime.now().isoformat()
        }

        if status in ('promote', 'rollback'):
            self._log_event(status, result)

        return result

    def promote(self):
        self._active = False
        logger.info(f'Canary PROMOTED: model {self.model_id} -> full deployment')
        self._log_event('promoted')

    def rollback(self):
        self._active = False
        self._trades = []
        self._returns = []
        logger.warning(f'Canary ROLLED BACK: model {self.model_id}')
        self._log_event('rolled_back')

    def _compute_sharpe(self) -> float:
        if len(self._returns) < 5:
            return 0
        import numpy as np
        mean = np.mean(self._returns)
        std = np.std(self._returns)
        if std == 0:
            return 0
        return mean / std * np.sqrt(252)

    def _compute_max_dd(self) -> float:
        if not self._returns:
            return 0
        import numpy as np
        cumulative = np.cumsum(self._returns)
        peak = np.maximum.accumulate(cumulative)
        return float(np.max(peak - cumulative)) if len(cumulative) > 0 else 0

    def _compute_slippage_drift(self) -> float:
        if not self._trades or self._baseline_slippage == 0:
            return 0
        avg_slippage = sum(abs(t.get('slippage', 0)) for t in self._trades) / len(self._trades)
        return abs(avg_slippage - self._baseline_slippage) / self._baseline_slippage if self._baseline_slippage > 0 else 0

    def _log_event(self, event: str, data: Dict[str, Any] = None):
        try:
            os.makedirs('logs', exist_ok=True)
            entry = {
                'event': event,
                'model': self.model_id,
                'data': data,
                'timestamp': datetime.now().isoformat()
            }
            with open(CANARY_LOG, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.error(f'Failed to log canary event: {e}')

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def allocation_pct(self) -> float:
        return CANARY_ALLOCATION_PCT if self._active else 0

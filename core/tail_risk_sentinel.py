# core/tail_risk_sentinel.py
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.logger import logger

SENTINEL_LOG = 'logs/sentinel_events.jsonl'

VAR_LIMIT = 0.05
VOL_SPIKE_MULTIPLIER = 2.5
SPREAD_MULTIPLIER = 3.0
DEPTH_THRESHOLD = 0.30
CORRELATED_DD_THRESHOLD = 0.05
CORRELATED_DD_COUNT = 3
LIQUIDITY_THRESHOLD = 0.20
FEED_LATENCY_MS = 5000


class TailRiskSentinel:
    def __init__(self):
        self._halted = False
        self._triggers: List[Dict[str, Any]] = []
        self._vol_history: List[float] = []
        self._spread_history: List[float] = []
        self._depth_history: List[float] = []
        self._volume_history: List[float] = []

    def check(self, market_data: Dict[str, Any], agent_states: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        triggers = []

        vol_result = self._check_vol_spike(market_data)
        if vol_result['triggered']:
            triggers.append(vol_result)

        spread_result = self._check_spread_explosion(market_data)
        if spread_result['triggered']:
            triggers.append(spread_result)

        depth_result = self._check_depth_collapse(market_data)
        if depth_result['triggered']:
            triggers.append(depth_result)

        liquidity_result = self._check_liquidity_dryup(market_data)
        if liquidity_result['triggered']:
            triggers.append(liquidity_result)

        feed_result = self._check_feed_anomaly(market_data)
        if feed_result['triggered']:
            triggers.append(feed_result)

        if agent_states:
            dd_result = self._check_correlated_drawdown(agent_states)
            if dd_result['triggered']:
                triggers.append(dd_result)

        if triggers:
            self._triggers.extend(triggers)
            self._halted = True
            self._log_triggers(triggers)
            logger.critical(f'SENTINEL TRIGGERED: {[t["reason"] for t in triggers]}')

        return {
            'status': 'TRIGGERED' if triggers else 'CLEAR',
            'halted': self._halted,
            'triggers': triggers,
            'total_triggers': len(self._triggers),
            'timestamp': datetime.now().isoformat()
        }

    def clear_halt(self):
        if not self._triggers:
            self._halted = False
            logger.info('Sentinel halt cleared')

    def force_halt(self, reason: str):
        self._halted = True
        trigger = {
            'reason': reason,
            'threshold': 'manual',
            'actual': 'N/A',
            'timestamp': datetime.now().isoformat()
        }
        self._triggers.append(trigger)
        self._log_triggers([trigger])
        logger.critical(f'Sentinel FORCE HALT: {reason}')

    def _check_vol_spike(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        indicators = market_data.get('indicators', market_data)
        current_vol = self._get_current_vol(indicators)
        self._vol_history.append(current_vol)
        if len(self._vol_history) > 60:
            self._vol_history = self._vol_history[-60:]

        if len(self._vol_history) < 20:
            return {'triggered': False}

        import numpy as np
        median_vol = np.median(self._vol_history[:-1])
        if median_vol > 0 and current_vol > median_vol * VOL_SPIKE_MULTIPLIER:
            return {
                'triggered': True,
                'reason': 'vol_spike',
                'threshold': f'{VOL_SPIKE_MULTIPLIER}x median',
                'actual': f'{current_vol / median_vol:.2f}x median'
            }
        return {'triggered': False}

    def _check_spread_explosion(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        indicators = market_data.get('indicators', market_data)
        bb_upper = indicators.get('bb_upper', 0)
        bb_lower = indicators.get('bb_lower', 0)
        price = indicators.get('current_price', 0)
        if price <= 0 or bb_upper <= 0 or bb_lower <= 0:
            return {'triggered': False}

        spread = (bb_upper - bb_lower) / price
        self._spread_history.append(spread)
        if len(self._spread_history) > 60:
            self._spread_history = self._spread_history[-60:]

        if len(self._spread_history) < 20:
            return {'triggered': False}

        import numpy as np
        median_spread = np.median(self._spread_history[:-1])
        if median_spread > 0 and spread > median_spread * SPREAD_MULTIPLIER:
            return {
                'triggered': True,
                'reason': 'spread_explosion',
                'threshold': f'{SPREAD_MULTIPLIER}x median',
                'actual': f'{spread / median_spread:.2f}x median'
            }
        return {'triggered': False}

    def _check_depth_collapse(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        indicators = market_data.get('indicators', market_data)
        volume_ratio = indicators.get('volume_ratio', 1.0)
        self._depth_history.append(volume_ratio)
        if len(self._depth_history) > 60:
            self._depth_history = self._depth_history[-60:]

        if len(self._depth_history) < 20:
            return {'triggered': False}

        import numpy as np
        median_depth = np.median(self._depth_history[:-1])
        if median_depth > 0 and volume_ratio < median_depth * DEPTH_THRESHOLD:
            return {
                'triggered': True,
                'reason': 'depth_collapse',
                'threshold': f'{DEPTH_THRESHOLD:.0%} of median',
                'actual': f'{volume_ratio / median_depth:.0%} of median'
            }
        return {'triggered': False}

    def _check_liquidity_dryup(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        indicators = market_data.get('indicators', market_data)
        volume_ratio = indicators.get('volume_ratio', 1.0)
        self._volume_history.append(volume_ratio)
        if len(self._volume_history) > 40:
            self._volume_history = self._volume_history[-40:]

        if len(self._volume_history) < 20:
            return {'triggered': False}

        import numpy as np
        median_vol = np.median(self._volume_history[:-1])
        if median_vol > 0 and volume_ratio < median_vol * LIQUIDITY_THRESHOLD:
            return {
                'triggered': True,
                'reason': 'liquidity_dryup',
                'threshold': f'{LIQUIDITY_THRESHOLD:.0%} of median',
                'actual': f'{volume_ratio / median_vol:.0%} of median'
            }
        return {'triggered': False}

    def _check_feed_anomaly(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        indicators = market_data.get('indicators', market_data)
        price = indicators.get('current_price', 0)
        if price <= 0:
            return {'triggered': True, 'reason': 'feed_anomaly', 'threshold': 'price > 0', 'actual': f'price={price}'}

        bb_upper = indicators.get('bb_upper', 0)
        bb_lower = indicators.get('bb_lower', 0)
        if bb_upper > 0 and bb_lower > 0 and price > bb_upper * 1.1:
            return {'triggered': True, 'reason': 'price_discontinuity', 'threshold': 'within BB', 'actual': f'price={price} > bb_upper*1.1={bb_upper*1.1}'}

        return {'triggered': False}

    def _check_correlated_drawdown(self, agent_states: List[Dict[str, Any]]) -> Dict[str, Any]:
        agents_in_dd = 0
        for state in agent_states:
            daily_pnl = state.get('daily_pnl', 0)
            capital = state.get('capital', 10000)
            if capital > 0 and daily_pnl / capital < -CORRELATED_DD_THRESHOLD:
                agents_in_dd += 1

        if agents_in_dd >= CORRELATED_DD_COUNT:
            return {
                'triggered': True,
                'reason': 'correlated_drawdown',
                'threshold': f'{CORRELATED_DD_COUNT}+ agents in DD',
                'actual': f'{agents_in_dd} agents in DD'
            }
        return {'triggered': False}

    def _get_current_vol(self, indicators: Dict[str, Any]) -> float:
        atr = indicators.get('atr_14', indicators.get('atr', 0))
        price = indicators.get('current_price', 1)
        if atr > 0 and price > 0:
            return atr / price
        return 0.02

    def _log_triggers(self, triggers: List[Dict[str, Any]]):
        try:
            os.makedirs('logs', exist_ok=True)
            for t in triggers:
                entry = {**t, 'logged_at': datetime.now().isoformat()}
                with open(SENTINEL_LOG, 'a') as f:
                    f.write(json.dumps(entry) + '\n')
        except Exception as e:
            logger.error(f'Failed to log sentinel triggers: {e}')

    @property
    def is_halted(self) -> bool:
        return self._halted

    @property
    def trigger_count(self) -> int:
        return len(self._triggers)

# core/risk_governor.py
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.logger import logger

GROSS_EXPOSURE_LIMIT = 0.90
NET_EXPOSURE_LIMIT = 0.60
SINGLE_ASSET_CONCENTRATION = 0.15
CORRELATION_LIMIT = 0.65
MAX_DRAWDOWN = 0.08
MAX_POSITIONS = 10


class RiskGovernor:
    def __init__(self, total_capital: float = 60000):
        self.total_capital = total_capital
        self._position_values: Dict[str, float] = {}
        self._daily_pnl: Dict[str, float] = {}
        self._peak_capital: float = total_capital

    def check_trade(self, symbol: str, side: str, position_value: float,
                    agent_name: str, agent_state: Dict[str, Any] = None) -> Dict[str, Any]:
        checks = []

        gross_result = self._check_gross_exposure(position_value)
        checks.append(gross_result)

        net_result = self._check_net_exposure(side, position_value)
        checks.append(net_result)

        concentration_result = self._check_concentration(symbol, position_value)
        checks.append(concentration_result)

        drawdown_result = self._check_drawdown(agent_state)
        checks.append(drawdown_result)

        capacity_result = self._check_capacity()
        checks.append(capacity_result)

        failures = [c for c in checks if not c['passed']]

        if failures:
            reason_codes = [f['reason_code'] for f in failures]
            logger.warning(f'Risk Governor REJECTED {agent_name}/{symbol}: {reason_codes}')
            return {
                'passed': False,
                'reason_codes': reason_codes,
                'failures': failures,
                'approved_size': 0,
                'timestamp': datetime.now().isoformat()
            }

        approved_size = self._compute_approved_size(position_value)
        return {
            'passed': True,
            'reason_codes': [],
            'failures': [],
            'approved_size': approved_size,
            'timestamp': datetime.now().isoformat()
        }

    def update_position(self, symbol: str, value: float):
        self._position_values[symbol] = value

    def remove_position(self, symbol: str):
        self._position_values.pop(symbol, None)

    def update_daily_pnl(self, agent_name: str, pnl: float):
        self._daily_pnl[agent_name] = pnl

    def update_peak_capital(self, capital: float):
        self._peak_capital = max(self._peak_capital, capital)

    def _check_gross_exposure(self, new_position_value: float) -> Dict[str, Any]:
        current_exposure = sum(self._position_values.values())
        new_exposure = current_exposure + new_position_value
        ratio = new_exposure / self.total_capital if self.total_capital > 0 else 1
        passed = ratio <= GROSS_EXPOSURE_LIMIT
        return {
            'check': 'gross_exposure',
            'passed': passed,
            'reason_code': 'EXPOSURE_LIMIT_BREACH' if not passed else None,
            'current': round(current_exposure, 2),
            'new_exposure': round(new_exposure, 2),
            'ratio': round(ratio, 4),
            'limit': GROSS_EXPOSURE_LIMIT
        }

    def _check_net_exposure(self, side: str, position_value: float) -> Dict[str, Any]:
        long_exposure = sum(v for s, v in self._position_values.items() if 'BUY' in s)
        short_exposure = sum(v for s, v in self._position_values.items() if 'SELL' in s)

        if side == 'BUY':
            long_exposure += position_value
        else:
            short_exposure += position_value

        net = abs(long_exposure - short_exposure)
        ratio = net / self.total_capital if self.total_capital > 0 else 1
        passed = ratio <= NET_EXPOSURE_LIMIT
        return {
            'check': 'net_exposure',
            'passed': passed,
            'reason_code': 'EXPOSURE_LIMIT_BREACH' if not passed else None,
            'net_exposure': round(net, 2),
            'ratio': round(ratio, 4),
            'limit': NET_EXPOSURE_LIMIT
        }

    def _check_concentration(self, symbol: str, position_value: float) -> Dict[str, Any]:
        existing = self._position_values.get(symbol, 0)
        total = existing + position_value
        ratio = total / self.total_capital if self.total_capital > 0 else 1
        passed = ratio <= SINGLE_ASSET_CONCENTRATION
        return {
            'check': 'concentration',
            'passed': passed,
            'reason_code': 'CONCENTRATION_BREACH' if not passed else None,
            'symbol': symbol,
            'exposure': round(total, 2),
            'ratio': round(ratio, 4),
            'limit': SINGLE_ASSET_CONCENTRATION
        }

    def _check_drawdown(self, agent_state: Dict[str, Any] = None) -> Dict[str, Any]:
        if agent_state is None:
            return {'check': 'drawdown', 'passed': True, 'reason_code': None}

        capital = agent_state.get('capital', self.total_capital)
        peak = agent_state.get('peak_capital', self._peak_capital)
        if peak <= 0:
            return {'check': 'drawdown', 'passed': True, 'reason_code': None}

        drawdown = (peak - capital) / peak
        passed = drawdown <= MAX_DRAWDOWN
        return {
            'check': 'drawdown',
            'passed': passed,
            'reason_code': 'DRAWDOWN_LIMIT_BREACH' if not passed else None,
            'drawdown': round(drawdown, 4),
            'limit': MAX_DRAWDOWN
        }

    def _check_capacity(self) -> Dict[str, Any]:
        count = len(self._position_values)
        passed = count < MAX_POSITIONS
        return {
            'check': 'capacity',
            'passed': passed,
            'reason_code': 'CAPACITY_LIMIT_BREACH' if not passed else None,
            'current_positions': count,
            'limit': MAX_POSITIONS
        }

    def _compute_approved_size(self, requested_value: float) -> float:
        current_exposure = sum(self._position_values.values())
        remaining = (self.total_capital * GROSS_EXPOSURE_LIMIT) - current_exposure
        return min(requested_value, max(0, remaining))

    def get_portfolio_state(self) -> Dict[str, Any]:
        total_exposure = sum(self._position_values.values())
        return {
            'total_capital': self.total_capital,
            'gross_exposure': round(total_exposure, 2),
            'exposure_ratio': round(total_exposure / self.total_capital, 4) if self.total_capital > 0 else 0,
            'position_count': len(self._position_values),
            'positions': dict(self._position_values),
            'peak_capital': self._peak_capital,
            'timestamp': datetime.now().isoformat()
        }

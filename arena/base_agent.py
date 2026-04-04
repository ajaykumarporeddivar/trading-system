# arena/base_agent.py
import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Dict, Any, Optional, List

from arena.config import (
    INITIAL_BALANCE, RISK_PER_TRADE, MAX_EXPOSURE, MAX_POSITIONS,
    DAILY_LOSS_CAP, MAX_DRAWDOWN, ORDER_DIR, TRAINING_EXPORT
)
from core.logger import logger


class BaseAgent(ABC):
    def __init__(self, name: str, strategy_name: str, order_db_path: str):
        self.name = name
        self.strategy_name = strategy_name
        self.order_db_path = order_db_path
        self.virtual_capital = INITIAL_BALANCE
        self.peak_capital = INITIAL_BALANCE
        self.daily_start_capital = INITIAL_BALANCE
        self.open_positions: Dict[str, Dict] = {}
        self.closed_positions: Dict[str, Dict] = {}
        self._load_state()

    @abstractmethod
    def generate_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass

    def submit_paper_order(self, signal: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        stop_distance = current_price * signal['stop_loss_pct']
        if stop_distance == 0:
            logger.warning(f'{self.name}: Invalid stop distance for {signal["symbol"]}')
            return {}

        risk_amount = self.virtual_capital * RISK_PER_TRADE
        quantity = risk_amount / stop_distance
        position_value = quantity * current_price

        max_position_value = self.virtual_capital * MAX_EXPOSURE
        if position_value > max_position_value:
            quantity = max_position_value / current_price
            position_value = max_position_value
            logger.info(f'{self.name}: Capped position size for {signal["symbol"]} to  ({MAX_EXPOSURE:.0%} exposure)')

        if signal['symbol'] in [p['symbol'] for p in self.open_positions.values()]:
            logger.info(f'{self.name}: Already have open position in {signal["symbol"]}')
            return {}

        if len(self.open_positions) >= MAX_POSITIONS:
            logger.info(f'{self.name}: Max positions reached ({MAX_POSITIONS})')
            return {}

        order_id = uuid.uuid4().hex[:8]
        side = signal['side']
        stop_loss = current_price * (1 - signal['stop_loss_pct']) if side == 'BUY' else current_price * (1 + signal['stop_loss_pct'])
        take_profit = current_price * (1 + signal['take_profit_pct']) if side == 'BUY' else current_price * (1 - signal['take_profit_pct'])

        order = {
            'order_id': order_id,
            'agent': self.name,
            'strategy': self.strategy_name,
            'symbol': signal['symbol'],
            'side': side,
            'entry_price': current_price,
            'quantity': round(quantity, 6),
            'position_value': round(position_value, 2),
            'stop_loss': round(stop_loss, 8),
            'take_profit': round(take_profit, 8),
            'stop_loss_pct': signal['stop_loss_pct'],
            'take_profit_pct': signal['take_profit_pct'],
            'confidence': signal['confidence'],
            'reason': signal['reason'],
            'status': 'open',
            'opened_at': datetime.now().isoformat(),
            'closed_at': None,
            'exit_price': None,
            'pnl': None,
            'pnl_pct': None,
            'outcome': None,
            'close_reason': None,
            'features': signal.get('features', {})
        }

        self.open_positions[order_id] = order
        self._save_state()

        direction = 'BUY' if side == 'BUY' else 'SELL'
        logger.info(
            f'[{self.name}] PAPER {direction} {signal["symbol"]} @ {current_price} | '
            f'qty: {order["quantity"]} | conf: {signal["confidence"]}% | {signal["reason"]}'
        )
        return order

    def close_position(self, order_id: str, exit_price: float, reason: str) -> Dict[str, Any]:
        if order_id not in self.open_positions:
            return {}

        order = self.open_positions[order_id]
        side = order['side']
        qty = order['quantity']

        if side == 'BUY':
            pnl = (exit_price - order['entry_price']) * qty
        else:
            pnl = (order['entry_price'] - exit_price) * qty

        pnl_pct = (pnl / order['position_value']) * 100 if order['position_value'] > 0 else 0

        if pnl > 0.01:
            outcome = 'WIN'
        elif pnl < -0.01:
            outcome = 'LOSS'
        else:
            outcome = 'BREAKEVEN'

        order['status'] = 'closed'
        order['closed_at'] = datetime.now().isoformat()
        order['exit_price'] = exit_price
        order['pnl'] = round(pnl, 2)
        order['pnl_pct'] = round(pnl_pct, 2)
        order['outcome'] = outcome
        order['close_reason'] = reason

        self.virtual_capital += pnl
        self.peak_capital = max(self.peak_capital, self.virtual_capital)

        del self.open_positions[order_id]
        self.closed_positions[order_id] = order
        self._save_state()

        self._append_training_row(order)

        logger.info(
            f'[{self.name}] {outcome} {order["symbol"]} @ {exit_price} | '
            f'PnL:  ({pnl_pct:.2f}%) | {reason}'
        )
        return order

    def check_exits(self, current_prices: Dict[str, float]):
        to_close = []
        for order_id, position in self.open_positions.items():
            symbol = position['symbol']
            if symbol not in current_prices:
                continue
            price = current_prices[symbol]

            if position['side'] == 'BUY':
                if price <= position['stop_loss']:
                    to_close.append((order_id, price, 'stop_loss'))
                elif price >= position['take_profit']:
                    to_close.append((order_id, price, 'take_profit'))
            else:
                if price >= position['stop_loss']:
                    to_close.append((order_id, price, 'stop_loss'))
                elif price <= position['take_profit']:
                    to_close.append((order_id, price, 'take_profit'))

        for order_id, exit_price, reason in to_close:
            self.close_position(order_id, exit_price, reason)

    def check_risk_limits(self) -> bool:
        daily_pnl = self.virtual_capital - self.daily_start_capital
        drawdown = (self.peak_capital - self.virtual_capital) / self.peak_capital if self.peak_capital > 0 else 0

        if daily_pnl <= -(INITIAL_BALANCE * DAILY_LOSS_CAP):
            logger.warning(f'{self.name}: HALTED - daily loss cap reached ()')
            return False

        if drawdown >= MAX_DRAWDOWN:
            logger.warning(f'{self.name}: HALTED - max drawdown reached ({drawdown:.2%})')
            return False

        return True

    def get_performance(self) -> Dict[str, Any]:
        closed = list(self.closed_positions.values())
        total_trades = len(closed)
        wins = sum(1 for t in closed if t['outcome'] == 'WIN')
        losses = sum(1 for t in closed if t['outcome'] == 'LOSS')
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum(t['pnl'] for t in closed if t['pnl'] is not None)
        avg_pnl = (total_pnl / total_trades) if total_trades > 0 else 0
        pnls = [t['pnl'] for t in closed if t['pnl'] is not None]
        best_trade = max(pnls) if pnls else 0
        worst_trade = min(pnls) if pnls else 0

        return {
            'agent': self.name,
            'strategy': self.strategy_name,
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': round(win_rate, 1),
            'total_pnl': round(total_pnl, 2),
            'avg_pnl': round(avg_pnl, 2),
            'best_trade': round(best_trade, 2),
            'worst_trade': round(worst_trade, 2),
            'virtual_capital': round(self.virtual_capital, 2),
            'open_positions': len(self.open_positions),
            'peak_capital': round(self.peak_capital, 2)
        }

    def reset_daily_capital(self):
        self.daily_start_capital = self.virtual_capital

    def _load_state(self):
        try:
            if os.path.exists(self.order_db_path):
                with open(self.order_db_path, 'r') as f:
                    data = json.load(f)
                self.virtual_capital = data.get('virtual_capital', INITIAL_BALANCE)
                self.peak_capital = data.get('peak_capital', INITIAL_BALANCE)
                self.daily_start_capital = data.get('daily_start_capital', INITIAL_BALANCE)
                self.open_positions = data.get('open_positions', {})
                self.closed_positions = data.get('closed_positions', {})
                logger.info(f'{self.name}: State loaded from {self.order_db_path}')
        except Exception as e:
            logger.error(f'{self.name}: Failed to load state: {e}')
            self.open_positions = {}
            self.closed_positions = {}

    def _save_state(self):
        try:
            os.makedirs(os.path.dirname(self.order_db_path) if os.path.dirname(self.order_db_path) else '.', exist_ok=True)
            data = {
                'agent': self.name,
                'strategy': self.strategy_name,
                'virtual_capital': self.virtual_capital,
                'peak_capital': self.peak_capital,
                'daily_start_capital': self.daily_start_capital,
                'open_positions': self.open_positions,
                'closed_positions': self.closed_positions,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.order_db_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f'{self.name}: Failed to save state: {e}')

    def _append_training_row(self, order: Dict[str, Any]):
        try:
            os.makedirs(os.path.dirname(TRAINING_EXPORT) if os.path.dirname(TRAINING_EXPORT) else '.', exist_ok=True)
            row = {
                'agent': order['agent'],
                'strategy': order['strategy'],
                'symbol': order['symbol'],
                'side': order['side'],
                'confidence': order['confidence'],
                'features': order.get('features', {}),
                'outcome': order['outcome'],
                'pnl_pct': order['pnl_pct'],
                'label': 1 if order['outcome'] == 'WIN' else 0,
                'timestamp': order['closed_at']
            }
            with open(TRAINING_EXPORT, 'a') as f:
                f.write(json.dumps(row) + '\n')
        except Exception as e:
            logger.error(f'{self.name}: Failed to append training row: {e}')

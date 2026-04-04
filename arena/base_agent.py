# arena/base_agent.py
import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, date
from typing import Dict, Any, Optional, List

from arena.config import (
    INITIAL_BALANCE, RISK_PER_TRADE, MAX_EXPOSURE, MAX_POSITIONS,
    DAILY_LOSS_CAP, MAX_DRAWDOWN, ORDER_DIR, TRAINING_EXPORT,
    ML_MIN_PROB_WIN, ML_REJECT_THRESHOLD, ML_PREDICTIONS_LOG
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

    def submit_paper_order(self, signal: Dict[str, Any], current_price: float,
                           regime_info: Optional[Dict[str, Any]] = None, risk_governor_result: Optional[Dict[str, Any]] = None,
                           timeframe: str = '4h', tf_risk_mult: float = 1.0) -> Dict[str, Any]:
        ml_result = self._check_ml_prediction(signal.get('features', {}), signal['symbol'])
        if ml_result['rejected']:
            logger.info(
                f'[{self.name}] REJECTED by ML gate: {signal["symbol"]} | '
                f'prob_win={ml_result["prob_win"]:.2f} | reason={ml_result["reason"]}'
            )
            return {}

        stop_distance = current_price * signal['stop_loss_pct']
        if stop_distance == 0:
            logger.warning(f'{self.name}: Invalid stop distance for {signal["symbol"]}')
            return {}

        regime = regime_info or {'regime': 'unknown', 'confidence': 0.5, 'metrics': {}}
        regime_strength = regime.get('confidence', 0.5)
        vol_scalar = self._compute_vol_scalar(regime.get('metrics', {}))

        risk_multiplier = ml_result.get('risk_multiplier', 1.0)
        agent_risk_adj = self._get_risk_adjustment()
        risk_amount = self.virtual_capital * RISK_PER_TRADE * risk_multiplier * agent_risk_adj * regime_strength * vol_scalar * tf_risk_mult
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

        if risk_governor_result and not risk_governor_result.get('passed', True):
            logger.info(f'[{self.name}] REJECTED by Risk Governor: {signal["symbol"]} | {risk_governor_result.get("reason_codes", [])}')
            return {}

        order_id = uuid.uuid4().hex[:8]
        side = signal['side']
        stop_loss = current_price * (1 - signal['stop_loss_pct']) if side == 'BUY' else current_price * (1 + signal['stop_loss_pct'])
        take_profit = current_price * (1 + signal['take_profit_pct']) if side == 'BUY' else current_price * (1 - signal['take_profit_pct'])

        features = signal.get('features', {})
        features['ml_prob_win'] = ml_result.get('prob_win', 0.5)
        features['ml_prediction'] = ml_result.get('prediction', -1)
        features['regime'] = regime.get('regime', 'unknown')
        features['regime_strength'] = regime_strength
        features['vol_scalar'] = vol_scalar
        features['timeframe'] = timeframe

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
            'timeframe': timeframe,
            'tf_risk_mult': tf_risk_mult,
            'opened_at': datetime.now().isoformat(),
            'closed_at': None,
            'exit_price': None,
            'pnl': None,
            'pnl_pct': None,
            'outcome': None,
            'close_reason': None,
            'ml_prob_win': ml_result.get('prob_win', 0.5),
            'ml_prediction': ml_result.get('prediction', -1),
            'regime_at_entry': regime.get('regime', 'unknown'),
            'regime_confidence': regime.get('confidence', 0.5),
            'risk_governor_outcome': 'PASS' if (risk_governor_result and risk_governor_result.get('passed')) else 'SKIP',
            'position_size_factors': {
                'ml_confidence': risk_multiplier,
                'agent_risk': agent_risk_adj,
                'regime_strength': regime_strength,
                'vol_scalar': vol_scalar
            },
            'features': features
        }

        self.open_positions[order_id] = order
        self._save_state()

        direction = 'BUY' if side == 'BUY' else 'SELL'
        logger.info(
            f'[{self.name}] PAPER {direction} {signal["symbol"]} @ {current_price} | '
            f'tf:{timeframe} qty: {order["quantity"]} | conf: {signal["confidence"]}% | ml_prob: {ml_result["prob_win"]:.2f} | '
            f'regime: {regime.get("regime", "?")}({regime_strength:.2f}) | vol_scalar: {vol_scalar:.2f} | tf_risk: {tf_risk_mult:.2f} | {signal["reason"]}'
        )
        return order

    def close_position(self, order_id: str, exit_price: float, reason: str,
                       regime_at_exit: Optional[str] = None) -> Dict[str, Any]:
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
        order['regime_at_exit'] = regime_at_exit or order.get('regime_at_entry', 'unknown')
        order['stop_out'] = reason in ('stop_loss',)

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

    def check_exits(self, current_prices: Dict[str, float], regime_at_exit: Optional[str] = None, timeframe: str = None):
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
            self.close_position(order_id, exit_price, reason, regime_at_exit=regime_at_exit)

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

    def _get_risk_adjustment(self) -> float:
        try:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'ml', 'strategy_adjustments.json')
            if not os.path.exists(config_path):
                return 1.0
            with open(config_path, 'r') as f:
                adjustments = json.load(f)
            agent_adj = adjustments.get('agent_adjustments', {}).get(self.name, {})
            rec = agent_adj.get('recommendation', 'MAINTAIN')
            if rec == 'INCREASE':
                return min(1.5, 1.0 + agent_adj.get('win_rate', 0.5) * 0.5)
            elif rec == 'DECREASE':
                return max(0.3, agent_adj.get('win_rate', 0.5))
            return 1.0
        except Exception:
            return 1.0

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
            size_factors = order.get('position_size_factors', {})
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
                'timestamp': order['closed_at'],
                'ml_prob_win': order.get('ml_prob_win', 0.5),
                'ml_prediction': order.get('ml_prediction', -1),
                'regime_at_entry': order.get('regime_at_entry', 'unknown'),
                'regime_at_exit': order.get('regime_at_exit', 'unknown'),
                'timeframe': order.get('timeframe', 'unknown'),
                'tf_risk_mult': order.get('tf_risk_mult', 1.0),
                'ml_gate_score': order.get('ml_prob_win', 0.5),
                'risk_governor_outcome': order.get('risk_governor_outcome', 'SKIP'),
                'position_size': order.get('position_value', 0),
                'entry_price': order.get('entry_price', 0),
                'exit_price': order.get('exit_price', 0),
                'gross_pnl': order.get('pnl', 0),
                'net_pnl': order.get('pnl', 0),
                'slippage': 0,
                'attribution_label': 'signal_alpha' if order.get('pnl', 0) > 0 else 'model_error',
                'stop_out': order.get('stop_out', False),
                'ml_confidence_factor': size_factors.get('ml_confidence', 1.0),
                'agent_risk_factor': size_factors.get('agent_risk', 1.0),
                'regime_strength_factor': size_factors.get('regime_strength', 0.5),
                'vol_scalar_factor': size_factors.get('vol_scalar', 1.0)
            }
            with open(TRAINING_EXPORT, 'a') as f:
                f.write(json.dumps(row) + '\n')
        except Exception as e:
            logger.error(f'{self.name}: Failed to append training row: {e}')

    def _compute_vol_scalar(self, regime_metrics: Dict[str, Any]) -> float:
        realized_vol = regime_metrics.get('realized_vol', 0.02)
        target_vol = 0.02
        if realized_vol > 0:
            scalar = target_vol / realized_vol
            return min(2.0, max(0.3, scalar))
        return 1.0

    def _check_ml_prediction(self, features: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        try:
            from ml.trainer import predict_signal, load_model
            model, metrics = load_model()
            if model is None or metrics is None:
                return {'rejected': False, 'prob_win': 0.5, 'prediction': -1, 'reason': 'no_model', 'risk_multiplier': 1.0}

            model_accuracy = metrics.get('accuracy', 0.5)
            result = predict_signal(features, model=model, metrics=metrics)
            if result is None:
                return {'rejected': False, 'prob_win': 0.5, 'prediction': -1, 'reason': 'predict_failed', 'risk_multiplier': 1.0}

            prob_win = result['prob_win']
            prediction = result['prediction']

            self._log_ml_prediction(symbol, prob_win, prediction)

            if model_accuracy < 0.50:
                risk_multiplier = 0.3 if prob_win < 0.35 else (0.6 if prob_win < 0.45 else 0.8)
                logger.debug(f'[{self.name}] ML model weak (acc={model_accuracy:.2f}), scoring only: prob={prob_win:.2f}, risk={risk_multiplier:.1f}x')
                return {'rejected': False, 'prob_win': prob_win, 'prediction': prediction, 'reason': 'model_weak_score_only', 'risk_multiplier': risk_multiplier}

            if prob_win < ML_REJECT_THRESHOLD:
                return {'rejected': True, 'prob_win': prob_win, 'prediction': prediction, 'reason': 'prob_too_low', 'risk_multiplier': 0}

            if prediction == 0:
                return {'rejected': True, 'prob_win': prob_win, 'prediction': prediction, 'reason': 'ml_predicts_loss', 'risk_multiplier': 0}

            risk_multiplier = 0.5 if prob_win < ML_MIN_PROB_WIN else (1.5 if prob_win > 0.70 else 1.0)
            return {'rejected': False, 'prob_win': prob_win, 'prediction': prediction, 'reason': 'approved', 'risk_multiplier': risk_multiplier}
        except Exception as e:
            logger.warning(f'{self.name}: ML gate error: {e}, allowing trade')
            return {'rejected': False, 'prob_win': 0.5, 'prediction': -1, 'reason': 'ml_error', 'risk_multiplier': 1.0}

    def _log_ml_prediction(self, symbol: str, prob_win: float, prediction: int):
        try:
            os.makedirs(os.path.dirname(ML_PREDICTIONS_LOG) if os.path.dirname(ML_PREDICTIONS_LOG) else '.', exist_ok=True)
            entry = {
                'timestamp': datetime.now().isoformat(),
                'agent': self.name,
                'symbol': symbol,
                'prob_win': prob_win,
                'prediction': prediction
            }
            with open(ML_PREDICTIONS_LOG, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception:
            pass

# arena/arena_runner.py
import asyncio
import json
import os
import time
import sys
from datetime import datetime, date
from typing import List, Dict, Any, Optional

from agents.data_agent import DataAgent
from arena.config import SYMBOLS, TIMEFRAME, MIN_CONFIDENCE, POLL_INTERVAL, ORDER_DIR, TIMEFRAMES
from arena.base_agent import BaseAgent
from arena.leaderboard import print_leaderboard, get_leaderboard_data
from arena.training_export import export_performance_csv
from core.regime_classifier import RegimeClassifier
from core.tail_risk_sentinel import TailRiskSentinel
from core.risk_governor import RiskGovernor
from core.diagnostics_engine import DiagnosticsEngine
from core.execution_logger import ExecutionLogger
from core.logger import logger


class TimeframeCycle:
    def __init__(self, tf_config: Dict):
        self.tf = tf_config['tf']
        self.interval = tf_config['interval']
        self.risk_mult = tf_config['risk_mult']
        self.max_pos = tf_config['max_pos']
        self.candles = tf_config['candles']
        self.label = tf_config['label']
        self.last_run = 0
        self.cycle_count = 0
        self.signals_generated = 0
        self.orders_placed = 0
        self.trades_closed = 0

    def should_run(self) -> bool:
        return time.time() - self.last_run >= self.interval

    def mark_run(self):
        self.last_run = time.time()
        self.cycle_count += 1

    def stats(self) -> Dict[str, Any]:
        return {
            'tf': self.tf,
            'label': self.label,
            'interval': self.interval,
            'cycles': self.cycle_count,
            'signals': self.signals_generated,
            'orders': self.orders_placed,
            'closed': self.trades_closed,
            'last_run': datetime.fromtimestamp(self.last_run).strftime('%H:%M:%S') if self.last_run > 0 else 'never'
        }


class ArenaRunner:
    RESTART_STATE_FILE = 'logs/arena_restart_state.json'

    def __init__(self, agents: List[BaseAgent], active_timeframes: List[str] = None):
        self.agents = agents
        self.data_agent = DataAgent()
        self.cycle_count = 0
        self.last_reset_date = date.today()

        total_capital = sum(getattr(a, 'virtual_capital', 10000) for a in agents)
        self.regime_classifier = RegimeClassifier()
        self.sentinel = TailRiskSentinel()
        self.risk_governor = RiskGovernor(total_capital=total_capital)
        self.diagnostics = DiagnosticsEngine()
        self.execution_logger = ExecutionLogger()

        if active_timeframes is None:
            active_timeframes = ['1m', '5m', '15m', '30m', '1h', '2h', '4h']

        self.tf_cycles: Dict[str, TimeframeCycle] = {}
        for tf_cfg in TIMEFRAMES:
            if tf_cfg['tf'] in active_timeframes:
                self.tf_cycles[tf_cfg['tf']] = TimeframeCycle(tf_cfg)

        self._load_restart_state()

        self.current_tf = '4h'
        logger.info(f'ArenaRunner initialized: {len(agents)} agents, {len(self.tf_cycles)} timeframes: {list(self.tf_cycles.keys())}')

    def _save_restart_state(self):
        try:
            os.makedirs('logs', exist_ok=True)
            state = {
                'cycle_count': self.cycle_count,
                'last_reset_date': str(self.last_reset_date),
                'timeframes': {
                    tf: {'last_run': c.last_run, 'cycle_count': c.cycle_count,
                         'signals': c.signals_generated, 'orders': c.orders_placed, 'closed': c.trades_closed}
                    for tf, c in self.tf_cycles.items()
                }
            }
            with open(self.RESTART_STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f'Failed to save restart state: {e}')

    def _load_restart_state(self):
        try:
            if os.path.exists(self.RESTART_STATE_FILE):
                with open(self.RESTART_STATE_FILE, 'r') as f:
                    state = json.load(f)
                self.cycle_count = state.get('cycle_count', 0)
                rd = state.get('last_reset_date')
                if rd:
                    self.last_reset_date = date.fromisoformat(rd)
                for tf, tf_state in state.get('timeframes', {}).items():
                    if tf in self.tf_cycles:
                        self.tf_cycles[tf].last_run = tf_state.get('last_run', 0)
                        self.tf_cycles[tf].cycle_count = tf_state.get('cycle_count', 0)
                        self.tf_cycles[tf].signals_generated = tf_state.get('signals', 0)
                        self.tf_cycles[tf].orders_placed = tf_state.get('orders', 0)
                        self.tf_cycles[tf].trades_closed = tf_state.get('closed', 0)
                logger.info(f'Restart state loaded: cycle={self.cycle_count}, timeframes restored')
        except Exception as e:
            logger.warning(f'Failed to load restart state (starting fresh): {e}')

    def run(self):
        logger.info('Multi-timeframe arena loop starting...')
        try:
            asyncio.run(self._run_loop())
        except KeyboardInterrupt:
            logger.info('Arena loop interrupted')
        except Exception as e:
            logger.error(f'Arena loop error: {e}', exc_info=True)

    async def _run_loop(self):
        while True:
            try:
                await self._run_all_timeframes()
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f'Loop error: {e}', exc_info=True)
                await asyncio.sleep(10)

    async def _run_all_timeframes(self) -> bool:
        ran_any = False
        for tf, cycle in self.tf_cycles.items():
            if cycle.should_run():
                self.current_tf = tf
                await self._run_tf_cycle(tf, cycle)
                ran_any = True
        if not ran_any:
            next_tf = min(self.tf_cycles.values(), key=lambda c: c.interval - (time.time() - c.last_run))
            wait = next_tf.interval - (time.time() - next_tf.last_run)
            logger.debug(f'No timeframe due, next: {next_tf.tf} in {wait:.0f}s')
        return ran_any

    async def _run_tf_cycle(self, timeframe: str, tf_cycle: TimeframeCycle):
        self.cycle_count += 1
        self._check_daily_reset()
        tf_cycle.mark_run()

        logger.info(f'=== CYCLE #{self.cycle_count} | {timeframe} ({tf_cycle.label}) START ===')
        cycle_start = datetime.now()

        try:
            market_data_raw = await self.data_agent.get_all_indicators(SYMBOLS, timeframe)
            if not market_data_raw:
                logger.error(f'No market data for {timeframe} - skipping')
                return

            market_overview = await self.data_agent.get_market_overview()
            current_prices = {sym: data.get('current_price', 0) for sym, data in market_data_raw.items()}

            regime_info = self.regime_classifier.classify(market_data_raw.get(SYMBOLS[0], {}))
            self.regime_classifier.update_vol_history(regime_info['metrics'].get('realized_vol', 0.02))

            sentinel_result = self.sentinel.check(
                market_data_raw.get(SYMBOLS[0], {}),
                self._get_agent_states()
            )
            if sentinel_result['halted']:
                logger.critical(f'Tail-Risk Sentinel HALTED at {timeframe} — no new entries')
                for agent in self.agents:
                    agent.check_exits(current_prices, regime_at_exit=regime_info['regime'], timeframe=timeframe)
                return

            market_data = {}
            for symbol, indicators in market_data_raw.items():
                overview = market_overview.get(symbol, {})
                prev_price = overview.get('low_24h', indicators.get('current_price', 0))
                change_pct = ((indicators['current_price'] - prev_price) / prev_price * 100) if prev_price else 0

                market_data[symbol] = {
                    'symbol': symbol,
                    'price': indicators['current_price'],
                    'change_pct': change_pct,
                    'indicators': indicators,
                    'regime': regime_info,
                    'timeframe': timeframe
                }

            for agent in self.agents:
                try:
                    if not agent.check_risk_limits():
                        continue

                    agent.check_exits(current_prices, regime_at_exit=regime_info['regime'], timeframe=timeframe)

                    for symbol, data in market_data.items():
                        signal = agent.generate_signal(data)
                        if signal and signal.get('confidence', 0) >= MIN_CONFIDENCE:
                            tf_cycle.signals_generated += 1
                            risk_result = self.risk_governor.check_trade(
                                symbol=symbol,
                                side=signal.get('side', 'BUY'),
                                position_value=signal.get('position_value', 0),
                                agent_name=agent.name,
                                agent_state={'capital': agent.virtual_capital, 'peak_capital': agent.peak_capital}
                            )
                            order = agent.submit_paper_order(
                                signal, data['price'],
                                regime_info=regime_info,
                                risk_governor_result=risk_result,
                                timeframe=timeframe,
                                tf_risk_mult=tf_cycle.risk_mult
                            )
                            if order:
                                tf_cycle.orders_placed += 1
                                self.execution_logger.log_signal_time(order['order_id'])
                                self.execution_logger.log_fill(
                                    order['order_id'], symbol, signal.get('side', 'BUY'),
                                    data['price'], order['quantity']
                                )
                                self.risk_governor.update_position(symbol, order['position_value'])
                                self.diagnostics.update_feature_baseline(signal.get('features', {}))

                except Exception as e:
                    logger.error(f'{agent.name} error at {timeframe}: {e}', exc_info=True)
                    continue

            drift_result = self.diagnostics.check_drift({'ml_prob_win': 0.5})

            duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(
                f'=== CYCLE #{self.cycle_count} | {timeframe} ({tf_cycle.label}) END ({duration:.1f}s) | '
                f'Regime: {regime_info["regime"]}({regime_info["confidence"]:.2f}) | '
                f'Sentinel: {sentinel_result["status"]} | '
                f'Signals: {tf_cycle.signals_generated} Orders: {tf_cycle.orders_placed} ==='
            )
            self._save_restart_state()

        except Exception as e:
            logger.error(f'Cycle {self.cycle_count} error at {timeframe}: {e}', exc_info=True)
            self._save_restart_state()

    def _get_agent_states(self) -> List[Dict[str, Any]]:
        states = []
        for agent in self.agents:
            daily_pnl = agent.virtual_capital - agent.daily_start_capital
            states.append({
                'agent': agent.name,
                'capital': agent.virtual_capital,
                'daily_pnl': daily_pnl,
                'open_positions': len(agent.open_positions)
            })
        return states

    def _check_daily_reset(self):
        today = date.today()
        if today != self.last_reset_date:
            for agent in self.agents:
                agent.reset_daily_capital()
            self.last_reset_date = today
            logger.info('Daily capital reset for all agents')

    def get_final_results(self):
        return get_leaderboard_data(self.agents)

    def get_system_status(self) -> Dict[str, Any]:
        return {
            'regime': self.regime_classifier.classify({}),
            'sentinel': {'halted': self.sentinel.is_halted, 'triggers': self.sentinel.trigger_count},
            'risk_governor': self.risk_governor.get_portfolio_state(),
            'diagnostics': self.diagnostics.get_diagnostics_summary(),
            'execution': self.execution_logger.get_execution_stats(),
            'timeframes': {tf: c.stats() for tf, c in self.tf_cycles.items()}
        }

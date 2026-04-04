# arena/arena_runner.py
import asyncio
import time
import sys
from datetime import datetime, date
from typing import List, Dict, Any

from agents.data_agent import DataAgent
from arena.config import SYMBOLS, TIMEFRAME, MIN_CONFIDENCE, POLL_INTERVAL, ORDER_DIR
from arena.base_agent import BaseAgent
from arena.leaderboard import print_leaderboard, get_leaderboard_data
from arena.training_export import export_performance_csv
from core.logger import logger


class ArenaRunner:
    def __init__(self, agents: List[BaseAgent]):
        self.agents = agents
        self.data_agent = DataAgent()
        self.cycle_count = 0
        self.last_reset_date = date.today()
        logger.info(f'ArenaRunner initialized with {len(agents)} agents')

    def run(self):
        logger.info('Arena loop starting...')
        try:
            asyncio.run(self._run_loop())
        except KeyboardInterrupt:
            logger.info('Arena loop interrupted')
        except Exception as e:
            logger.error(f'Arena loop error: {e}', exc_info=True)

    async def _run_loop(self):
        while True:
            try:
                await self._run_cycle()
                await asyncio.sleep(POLL_INTERVAL)
            except Exception as e:
                logger.error(f'Cycle error: {e}', exc_info=True)
                await asyncio.sleep(POLL_INTERVAL)

    async def _run_cycle(self):
        self.cycle_count += 1
        self._check_daily_reset()

        logger.info(f'=== ARENA CYCLE #{self.cycle_count} START ===')
        cycle_start = datetime.now()

        try:
            market_data_raw = await self.data_agent.get_all_indicators(SYMBOLS)
            if not market_data_raw:
                logger.error('No market data available - skipping cycle')
                return

            market_overview = await self.data_agent.get_market_overview()
            current_prices = {sym: data.get('current_price', 0) for sym, data in market_data_raw.items()}

            market_data = {}
            for symbol, indicators in market_data_raw.items():
                overview = market_overview.get(symbol, {})
                prev_price = overview.get('low_24h', indicators.get('current_price', 0))
                change_pct = ((indicators['current_price'] - prev_price) / prev_price * 100) if prev_price else 0

                market_data[symbol] = {
                    'symbol': symbol,
                    'price': indicators['current_price'],
                    'change_pct': change_pct,
                    'indicators': indicators
                }

            for agent in self.agents:
                try:
                    if not agent.check_risk_limits():
                        logger.info(f'{agent.name}: HALTED - skipping cycle')
                        continue

                    agent.check_exits(current_prices)

                    for symbol, data in market_data.items():
                        signal = agent.generate_signal(data)
                        if signal and signal.get('confidence', 0) >= MIN_CONFIDENCE:
                            agent.submit_paper_order(signal, data['price'])

                except Exception as e:
                    logger.error(f'{agent.name} error in cycle: {e}', exc_info=True)
                    continue

            print_leaderboard(self.agents, self.cycle_count)
            export_performance_csv(self.agents)

            duration = (datetime.now() - cycle_start).total_seconds()
            logger.info(f'=== ARENA CYCLE #{self.cycle_count} END ({duration:.1f}s) ===')

        except Exception as e:
            logger.error(f'Cycle {self.cycle_count} error: {e}', exc_info=True)

    def _check_daily_reset(self):
        today = date.today()
        if today != self.last_reset_date:
            for agent in self.agents:
                agent.reset_daily_capital()
            self.last_reset_date = today
            logger.info('Daily capital reset for all agents')

    def get_final_results(self):
        return get_leaderboard_data(self.agents)

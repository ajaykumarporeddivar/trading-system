import asyncio
from typing import Dict, List, Any
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from core.config import Config
from core.logger import logger
from agents.data_agent import DataAgent
from agents.signal_agent import SignalAgent
from agents.risk_agent import RiskAgent
from agents.execution_agent import ExecutionAgent
from agents.journal_agent import JournalAgent
from agents.briefing_agent import BriefingAgent

class Orchestrator:
    def __init__(self):
        self.data_agent = DataAgent()
        self.signal_agent = SignalAgent()
        self.risk_agent = RiskAgent()
        self.execution_agent = ExecutionAgent()
        self.journal_agent = JournalAgent()
        self.briefing_agent = BriefingAgent()
        self.scheduler = AsyncIOScheduler()
        self.system_running = False
        self._halted = False
        logger.info('Orchestrator initialized')

    async def start(self):
        logger.info('Starting trading system...')
        errors = Config.validate()
        if errors:
            logger.error(f'Configuration errors: {errors}')
            return False

        await self.journal_agent.journal.init_db()
        self.system_running = True
        self._halted = False

        self.scheduler.add_job(
            self.trading_cycle,
            IntervalTrigger(hours=Config.CYCLE_HOURS),
            id='trading_cycle',
            name=f'Run trading cycle every {Config.CYCLE_HOURS} hours',
            replace_existing=True
        )

        self.scheduler.add_job(
            self.morning_briefing,
            CronTrigger(hour=Config.BRIEFING_HOUR, minute=0),
            id='morning_briefing',
            name='Send morning briefing',
            replace_existing=True
        )

        self.scheduler.start()
        logger.info(f'System started - Trading cycle every {Config.CYCLE_HOURS}H, Briefing at {Config.BRIEFING_HOUR}:00')
        return True

    async def stop(self):
        logger.info('Stopping trading system...')
        self.system_running = False
        self._halted = True
        self.scheduler.shutdown(wait=False)
        logger.info('System stopped')

    async def halt(self):
        logger.critical('EMERGENCY STOP TRIGGERED')
        await self.stop()

    async def trading_cycle(self):
        if not self.system_running or self._halted:
            logger.warning('Trading cycle skipped - system not running')
            return

        logger.info('=== TRADING CYCLE START ===')
        cycle_start = datetime.now()

        try:
            market_data = await self.data_agent.get_all_indicators()
            if not market_data:
                logger.error('No market data available - skipping cycle')
                return

            signals = await self.signal_agent.analyze(market_data)
            candidates = await self.signal_agent.get_trade_candidates(signals)

            if not candidates:
                logger.info('No trade candidates this cycle')
                await self.log_cycle_complete(cycle_start, 0, 0)
                return

            balance_data = await self.data_agent.get_balance()
            portfolio_state = {
                'balance': balance_data.get('free', Config.INITIAL_BALANCE),
                'peak_balance': balance_data.get('total', Config.INITIAL_BALANCE),
                'current_exposure': 0,
                'daily_pnl': 0
            }

            risk_status = await self.risk_agent.check_all_positions(portfolio_state)
            if not risk_status['can_trade']:
                logger.warning('Risk checks failed - no trades allowed this cycle')
                await self.log_cycle_complete(cycle_start, len(candidates), 0)
                return

            trades_executed = 0
            for candidate in candidates:
                if self._halted:
                    logger.info('Emergency stop - halting trade execution')
                    break

                symbol = candidate['symbol']
                indicator_data = market_data.get(symbol, {})
                current_price = indicator_data.get('current_price', 0)

                if current_price <= 0:
                    continue

                atr = indicator_data.get('atr_14', current_price * 0.02)
                side = 'buy' if candidate['verdict'] == 'LONG' else 'sell'
                stop_loss = await self.risk_agent.calculate_stop_loss(current_price, side, atr)
                take_profit = await self.risk_agent.calculate_take_profit(current_price, stop_loss, side)

                trade_data = {
                    'symbol': symbol,
                    'side': side,
                    'entry_price': current_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'verdict': candidate['verdict'],
                    'confidence': candidate['confidence']
                }

                risk_result = await self.risk_agent.evaluate_trade(trade_data, portfolio_state)

                if risk_result['approved']:
                    position_size = risk_result['position_size']
                    trade_data['quantity'] = position_size['quantity']
                    trade_data['r_ratio'] = position_size.get('r_ratio')

                    execution_result = await self.execution_agent.execute_trade(trade_data)
                    if execution_result:
                        trades_executed += 1
                        await self.briefing_agent.send_trade_alert(trade_data)
                        logger.info(f'Trade #{trades_executed} executed: {symbol}')
                    else:
                        logger.error(f'Failed to execute trade for {symbol}')
                else:
                    logger.info(f'Trade blocked by risk: {symbol}')

            await self.log_cycle_complete(cycle_start, len(candidates), trades_executed)

        except Exception as e:
            logger.error(f'Trading cycle error: {e}', exc_info=True)

        logger.info('=== TRADING CYCLE END ===')

    async def morning_briefing(self):
        if not self.system_running:
            return

        logger.info('Generating morning briefing...')
        try:
            market_overview = await self.data_agent.get_market_overview()
            market_data = await self.data_agent.get_all_indicators()
            signals = await self.signal_agent.analyze(market_data)
            await self.briefing_agent.send_briefing(market_overview, signals)
        except Exception as e:
            logger.error(f'Morning briefing error: {e}', exc_info=True)

    async def log_cycle_complete(self, start_time: datetime, candidates: int, executed: int):
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f'Cycle complete: {candidates} candidates, {executed} trades, {duration:.1f}s')

    async def run_once(self):
        logger.info('Running single trading cycle...')
        await self.trading_cycle()

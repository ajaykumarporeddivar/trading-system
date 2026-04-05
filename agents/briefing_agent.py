from typing import Dict, Any, List
from core.config import Config
from core.logger import logger
from agents.journal_agent import JournalAgent
from alerts.telegram import TelegramAlert
from alerts.email_alert import EmailAlert

class BriefingAgent:
    def __init__(self):
        self.journal = JournalAgent()
        self.telegram = TelegramAlert() if Config.TELEGRAM_BOT_TOKEN else None
        self.email = EmailAlert() if Config.EMAIL_USER else None
        logger.info('Briefing Agent initialized')

    async def generate_morning_briefing(self, market_data: Dict[str, Any], signals: List[Dict[str, Any]]) -> str:
        briefing = 'Morning Crypto Briefing\n'
        briefing += '=' * 40 + '\n\n'

        briefing += 'Market Overview:\n'
        for symbol, data in market_data.items():
            change = data.get('change_24h', 0)
            direction = '+' if change >= 0 else ''
            briefing += f'{symbol}: {direction}{change:.2f}%\n'

        briefing += '\nTrading Signals:\n'
        for signal in signals:
            emoji = 'LONG' if signal['verdict'] == 'LONG' else 'SHORT' if signal['verdict'] == 'SHORT' else 'WAIT'
            briefing += f'{signal["symbol"]}: {emoji} ({signal["confidence"]}% confidence)\n'

        perf = await self.journal.get_performance_report()
        briefing += f'\nPerformance:\n'
        briefing += f'Total P&L: {perf["total_pnl"]}\n'
        briefing += f'Win Rate: {perf["win_rate"]}%\n'

        logger.info('Morning briefing generated')
        return briefing

    async def send_briefing(self, market_data: Dict[str, Any], signals: List[Dict[str, Any]]):
        briefing = await self.generate_morning_briefing(market_data, signals)

        if self.telegram:
            await self.telegram.send_message(briefing)

        if self.email:
            await self.email.send_email('Morning Crypto Briefing', briefing)

        logger.info('Briefing sent via configured channels')

    async def send_trade_alert(self, trade_data: Dict[str, Any]):
        alert = f'Trade Alert\n{"=" * 40}\n'
        alert += f'Symbol: {trade_data.get("symbol")}\n'
        alert += f'Side: {trade_data.get("side")}\n'
        alert += f'Entry: {trade_data.get("entry_price")}\n'
        alert += f'Quantity: {trade_data.get("quantity")}\n'
        alert += f'Stop Loss: {trade_data.get("stop_loss")}\n'
        alert += f'Take Profit: {trade_data.get("take_profit")}\n'
        alert += f'Confidence: {trade_data.get("confidence", 0)}%'

        if self.telegram:
            await self.telegram.send_message(alert)

        if self.email:
            await self.email.send_email(f'Trade Alert: {trade_data.get("symbol")}', alert)

        logger.info(f'Trade alert sent for {trade_data.get("symbol")}')

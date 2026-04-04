from typing import Dict, Any, List
from storage.database import TradingJournal
from core.logger import logger
import datetime

class JournalAgent:
    def __init__(self):
        self.journal = TradingJournal()
        logger.info('Journal Agent initialized')

    async def record_trade(self, trade_data: Dict[str, Any]):
        await self.journal.log_trade(trade_data)
        logger.info(f'Trade recorded: {trade_data["symbol"]} {trade_data["side"]}')

    async def get_performance_report(self) -> Dict[str, Any]:
        stats = await self.journal.get_performance_stats()
        return {
            'total_trades': stats.get('total_trades', 0),
            'wins': stats.get('wins', 0),
            'losses': stats.get('losses', 0),
            'win_rate': round(stats.get('win_rate', 0), 2),
            'total_pnl': round(stats.get('total_pnl', 0), 2),
            'avg_pnl': round(stats.get('avg_pnl', 0), 2),
            'best_trade': round(stats.get('best_trade', 0), 2),
            'worst_trade': round(stats.get('worst_trade', 0), 2)
        }

    async def generate_weekly_report(self) -> str:
        stats = await self.get_performance_report()

        report = f'''Weekly Trading Performance Report
================================
Period: Last 7 days
Total Trades: {stats['total_trades']}
Wins: {stats['wins']}
Losses: {stats['losses']}
Win Rate: {stats['win_rate']}%
Total P&L: 
Average P&L: 
Best Trade: 
Worst Trade: 
'''
        logger.info('Weekly report generated')
        return report

    async def identify_patterns(self) -> Dict[str, Any]:
        stats = await self.journal.get_performance_stats()

        patterns = {
            'losing_streak': 0,
            'winning_streak': 0,
            'best_pair': 'N/A',
            'worst_pair': 'N/A',
            'recommendations': []
        }

        if stats.get('win_rate', 0) < 40:
            patterns['recommendations'].append('Win rate below 40% - consider tightening entry criteria')

        if stats.get('total_trades', 0) > 0:
            avg_r = stats.get('total_pnl', 0) / stats['total_trades']
            if avg_r < 0:
                patterns['recommendations'].append('Average trade is losing - review strategy')

        logger.info(f'Pattern analysis complete: {len(patterns["recommendations"])} recommendations')
        return patterns

    async def update_daily_stats(self, balance: float, starting_balance: float, trades_today: int, wins: int, losses: int):
        today = datetime.date.today().isoformat()
        daily_pnl = balance - starting_balance

        await self.journal.update_daily_pnl(today, {
            'starting_balance': starting_balance,
            'ending_balance': balance,
            'daily_pnl': daily_pnl,
            'trades_count': trades_today,
            'wins': wins,
            'losses': losses
        })

        logger.info(f'Daily stats updated: P&L ')

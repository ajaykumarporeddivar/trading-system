from typing import Dict, Any, List
from core.config import Config
from core.logger import logger
from engine.risk_calculator import RiskCalculator
from storage.database import TradingJournal

class RiskAgent:
    def __init__(self):
        self.calculator = RiskCalculator()
        self.journal = TradingJournal()
        logger.info('Risk Agent initialized')

    async def evaluate_trade(self, trade_data: Dict[str, Any], portfolio_state: Dict[str, Any]) -> Dict[str, Any]:
        result = self.calculator.validate_trade(trade_data, portfolio_state)

        if result['approved']:
            logger.info(
                f'Risk APPROVED: {trade_data.get("symbol")} - '
                f'Size: {result["position_size"]["quantity"]}, '
                f'Risk: '
            )
        else:
            logger.warning(
                f'Risk BLOCKED: {trade_data.get("symbol")} - '
                f'Reasons: {", ".join(result["blocks"])}'
            )

        return result

    async def check_all_positions(self, portfolio_state: Dict[str, Any]) -> Dict[str, Any]:
        open_positions = await self.journal.get_open_positions()

        total_exposure = sum(
            pos['entry_price'] * pos['quantity'] for pos in open_positions
        )

        daily_pnl = await self.journal.get_daily_pnl()
        current_daily_pnl = daily_pnl.get('daily_pnl', 0) if daily_pnl else 0

        exposure_check = self.calculator.check_portfolio_exposure(
            total_exposure, 0, portfolio_state.get('balance', 0)
        )

        daily_check = self.calculator.check_daily_loss(
            current_daily_pnl, portfolio_state.get('balance', 0)
        )

        drawdown_check = self.calculator.check_drawdown(
            portfolio_state.get('balance', 0),
            portfolio_state.get('peak_balance', portfolio_state.get('balance', 0))
        )

        return {
            'open_positions': len(open_positions),
            'total_exposure': round(total_exposure, 2),
            'exposure_check': exposure_check,
            'daily_check': daily_check,
            'drawdown_check': drawdown_check,
            'can_trade': exposure_check['allowed'] and daily_check['allowed'] and drawdown_check['allowed']
        }

    async def calculate_stop_loss(self, entry_price: float, side: str, atr: float, multiplier: float = 1.5) -> float:
        if side == 'LONG':
            return round(entry_price - (atr * multiplier), 8)
        else:
            return round(entry_price + (atr * multiplier), 8)

    async def calculate_take_profit(self, entry_price: float, stop_loss: float, side: str, min_r: float = 2.0) -> float:
        risk_distance = abs(entry_price - stop_loss)
        if side == 'LONG':
            return round(entry_price + (risk_distance * min_r), 8)
        else:
            return round(entry_price - (risk_distance * min_r), 8)

from typing import Dict, Any, Optional
from core.config import Config
from core.logger import logger

class RiskCalculator:
    @staticmethod
    def calculate_position_size(balance: float, entry_price: float, stop_loss: float,
                                risk_per_trade: float = Config.RISK_PER_TRADE) -> Dict[str, Any]:
        risk_amount = balance * risk_per_trade
        price_distance = abs(entry_price - stop_loss)
        if price_distance == 0:
            return {'quantity': 0, 'position_value': 0, 'risk_amount': risk_amount, 'error': 'Invalid stop loss'}

        quantity = risk_amount / price_distance
        position_value = quantity * entry_price
        r_ratio = price_distance / entry_price

        return {
            'quantity': round(quantity, 6),
            'position_value': round(position_value, 2),
            'risk_amount': round(risk_amount, 2),
            'r_ratio': round(r_ratio, 4)
        }

    @staticmethod
    def check_portfolio_exposure(current_exposure: float, new_position_value: float,
                                  total_balance: float) -> Dict[str, Any]:
        new_exposure = (current_exposure + new_position_value) / total_balance
        allowed = new_exposure <= Config.MAX_PORTFOLIO_EXPOSURE

        return {
            'current_exposure': round(current_exposure, 2),
            'new_exposure': round(new_exposure, 4),
            'max_exposure': Config.MAX_PORTFOLIO_EXPOSURE,
            'allowed': allowed
        }

    @staticmethod
    def check_daily_loss(current_daily_pnl: float, starting_balance: float) -> Dict[str, Any]:
        daily_loss_pct = abs(min(current_daily_pnl, 0)) / starting_balance
        allowed = daily_loss_pct < Config.DAILY_LOSS_CAP

        return {
            'daily_pnl': round(current_daily_pnl, 2),
            'daily_loss_pct': round(daily_loss_pct, 4),
            'max_loss_pct': Config.DAILY_LOSS_CAP,
            'allowed': allowed
        }

    @staticmethod
    def check_drawdown(current_balance: float, peak_balance: float) -> Dict[str, Any]:
        drawdown = (peak_balance - current_balance) / peak_balance if peak_balance > 0 else 0
        allowed = drawdown < Config.MAX_DRAWDOWN

        return {
            'current_balance': round(current_balance, 2),
            'peak_balance': round(peak_balance, 2),
            'drawdown_pct': round(drawdown * 100, 2),
            'max_drawdown_pct': Config.MAX_DRAWDOWN * 100,
            'allowed': allowed
        }

    @staticmethod
    def validate_trade(trade_data: Dict[str, Any], portfolio_state: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            'approved': True,
            'blocks': [],
            'position_size': None
        }

        balance = portfolio_state.get('balance', Config.INITIAL_BALANCE)
        if balance <= 0:
            result['approved'] = False
            result['blocks'].append('Invalid balance')
            return result
        entry_price = trade_data.get('entry_price', 0)
        stop_loss = trade_data.get('stop_loss', 0)

        if entry_price <= 0 or stop_loss <= 0:
            result['approved'] = False
            result['blocks'].append('Invalid price data')
            return result

        position_data = RiskCalculator.calculate_position_size(balance, entry_price, stop_loss)
        result['position_size'] = position_data

        if position_data.get('error'):
            result['approved'] = False
            result['blocks'].append(position_data['error'])
            return result

        exposure_check = RiskCalculator.check_portfolio_exposure(
            portfolio_state.get('current_exposure', 0),
            position_data['position_value'],
            balance
        )
        if not exposure_check['allowed']:
            result['approved'] = False
            result['blocks'].append(f'Portfolio exposure too high: {exposure_check["new_exposure"]:.2%}')

        daily_check = RiskCalculator.check_daily_loss(
            portfolio_state.get('daily_pnl', 0),
            balance
        )
        if not daily_check['allowed']:
            result['approved'] = False
            result['blocks'].append(f'Daily loss cap reached: {daily_check["daily_loss_pct"]:.2%}')

        drawdown_check = RiskCalculator.check_drawdown(
            balance,
            portfolio_state.get('peak_balance', balance)
        )
        if not drawdown_check['allowed']:
            result['approved'] = False
            result['blocks'].append(f'Max drawdown reached: {drawdown_check["drawdown_pct"]:.2f}%')

        if result['approved']:
            logger.info(f'Trade approved: {trade_data.get("symbol")} - Position size: {position_data["quantity"]}')
        else:
            logger.warning(f'Trade BLOCKED: {trade_data.get("symbol")} - Reasons: {result["blocks"]}')

        return result

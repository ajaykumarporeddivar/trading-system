# arena/agents/ajay.py
from typing import Dict, Any, Optional
from arena.base_agent import BaseAgent
from arena.config import MIN_CONFIDENCE
from core.logger import logger


class AjayAgent(BaseAgent):
    """Momentum strategy: Ride strong directional moves. Goes WITH the trend.

    BUY conditions:
      - macd > macd_signal                          -> +30
      - 50 < rsi < 72                               -> +25
      - vol_ratio > 1.5                             -> +20
      - change_pct > 0.5                            -> +15
    SELL conditions:
      - macd < macd_signal                          -> +30
      - 28 < rsi < 50                               -> +25
      - vol_ratio > 1.5                             -> +20
      - change_pct < -0.5                           -> +15
    Hard filters (return None):
      - rsi > 82 (exhaustion)
      - rsi < 18 (oversold bounce risk)
    Stop: 2.5% | Target: 5%
    """

    def __init__(self, order_db_path: str):
        super().__init__(name='AJAY', strategy_name='Momentum', order_db_path=order_db_path)

    def generate_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        indicators = market_data.get('indicators', {})
        price = market_data.get('price')
        change_pct = market_data.get('change_pct', 0)
        symbol = market_data.get('symbol', '')

        macd = indicators.get('macd')
        macd_signal = indicators.get('macd_signal')
        rsi = indicators.get('rsi_14')
        vol_ratio = indicators.get('volume_ratio')

        if any(v is None for v in [macd, macd_signal, rsi, vol_ratio, price]):
            return None

        if rsi > 82 or rsi < 18:
            return None

        score = 0
        buy_conditions = []
        sell_conditions = []

        if macd > macd_signal:
            score += 30
            buy_conditions.append('macd_bullish')
        elif macd < macd_signal:
            score += 30
            sell_conditions.append('macd_bearish')

        if 50 < rsi < 72:
            score += 25
            buy_conditions.append('rsi_bullish_zone')
        elif 28 < rsi < 50:
            score += 25
            sell_conditions.append('rsi_bearish_zone')

        if vol_ratio > 1.5:
            score += 20
            if change_pct > 0:
                buy_conditions.append('volume_confirming_up')
            else:
                sell_conditions.append('volume_confirming_down')

        if change_pct > 0.5:
            score += 15
            buy_conditions.append('positive_momentum')
        elif change_pct < -0.5:
            score += 15
            sell_conditions.append('negative_momentum')

        if score >= MIN_CONFIDENCE and len(buy_conditions) >= 2:
            return {
                'symbol': symbol,
                'side': 'BUY',
                'confidence': min(score, 95),
                'reason': ' | '.join(buy_conditions),
                'stop_loss_pct': 0.025,
                'take_profit_pct': 0.05,
                'features': indicators.copy()
            }

        if score >= MIN_CONFIDENCE and len(sell_conditions) >= 2:
            return {
                'symbol': symbol,
                'side': 'SELL',
                'confidence': min(score, 95),
                'reason': ' | '.join(sell_conditions),
                'stop_loss_pct': 0.025,
                'take_profit_pct': 0.05,
                'features': indicators.copy()
            }

        return None

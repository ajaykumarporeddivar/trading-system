# arena/agents/sanjay.py
from typing import Dict, Any, Optional
from arena.base_agent import BaseAgent
from arena.config import MIN_CONFIDENCE
from core.logger import logger


class SanjayAgent(BaseAgent):
    """Breakout strategy: Enter when price escapes its range with volume conviction.

    BUY conditions:
      - price > high_20                             -> +40
      - vol_ratio > 2.0                             -> +30
      - atr > price * 0.018  (ATR expanding)        -> +20
      - change_pct > 1.0                            -> +10
    SELL conditions:
      - price < low_20                              -> +40
      - vol_ratio > 2.0                             -> +30
      - atr > price * 0.018                         -> +20
      - change_pct < -1.0                           -> +10
    Dynamic SL/TP:
      - atr_pct = atr / price
      - stop_loss_pct = max(0.015, min(0.06, atr_pct * 1.5))
      - take_profit_pct = max(0.03, min(0.12, atr_pct * 3.0))
    """

    def __init__(self, order_db_path: str):
        super().__init__(name='SANJAY', strategy_name='Breakout', order_db_path=order_db_path)

    def generate_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        indicators = market_data.get('indicators', {})
        price = market_data.get('price')
        change_pct = market_data.get('change_pct', 0)
        symbol = market_data.get('symbol', '')

        high_20 = indicators.get('high_20')
        low_20 = indicators.get('low_20')
        vol_ratio = indicators.get('volume_ratio')
        atr = indicators.get('atr_14')

        if any(v is None for v in [high_20, low_20, vol_ratio, atr, price]):
            return None

        score = 0
        buy_conditions = []
        sell_conditions = []

        if price > high_20:
            score += 40
            buy_conditions.append('breakout_above_20h')
        elif price < low_20:
            score += 40
            sell_conditions.append('breakdown_below_20h')

        if vol_ratio > 2.0:
            score += 30
            if change_pct > 0:
                buy_conditions.append('volume_surge_up')
            else:
                sell_conditions.append('volume_surge_down')

        if atr > price * 0.018:
            score += 20
            if change_pct > 0:
                buy_conditions.append('atr_expanding')
            else:
                sell_conditions.append('atr_expanding')

        if change_pct > 1.0:
            score += 10
            buy_conditions.append('strong_up_move')
        elif change_pct < -1.0:
            score += 10
            sell_conditions.append('strong_down_move')

        atr_pct = atr / price
        sl_pct = max(0.015, min(0.06, atr_pct * 1.5))
        tp_pct = max(0.03, min(0.12, atr_pct * 3.0))

        if score >= MIN_CONFIDENCE and len(buy_conditions) >= 2:
            return {
                'symbol': symbol,
                'side': 'BUY',
                'confidence': min(score, 95),
                'reason': ' | '.join(buy_conditions),
                'stop_loss_pct': sl_pct,
                'take_profit_pct': tp_pct,
                'features': indicators.copy()
            }

        if score >= MIN_CONFIDENCE and len(sell_conditions) >= 2:
            return {
                'symbol': symbol,
                'side': 'SELL',
                'confidence': min(score, 95),
                'reason': ' | '.join(sell_conditions),
                'stop_loss_pct': sl_pct,
                'take_profit_pct': tp_pct,
                'features': indicators.copy()
            }

        return None

# arena/agents/vijay.py
from typing import Dict, Any, Optional
from arena.base_agent import BaseAgent
from arena.config import MIN_CONFIDENCE
from core.logger import logger


class VijayAgent(BaseAgent):
    """Mean reversion strategy: Fade extremes. Crypto always mean-reverts on 4h.

    BUY conditions:
      - price <= bb_lower * 1.003  (at or within 0.3% of lower band)  -> +35
      - rsi < 35                                                        -> +30
      - vol_ratio < 1.5  (no capitulation volume)                       -> +20
      - change_pct < -1.5                                               -> +15
    SELL conditions:
      - price >= bb_upper * 0.997  (at or within 0.3% of upper band)  -> +35
      - rsi > 65                                                        -> +30
      - vol_ratio < 1.5                                                 -> +20
      - change_pct > 1.5                                                -> +15
    Hard filters (return None):
      - vol_ratio > 3.0 (extreme volume - possible breakout not reversion)
    Stop: 2% | Target: 4%
    """

    def __init__(self, order_db_path: str):
        super().__init__(name='VIJAY', strategy_name='Mean Reversion', order_db_path=order_db_path)

    def generate_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        indicators = market_data.get('indicators', {})
        price = market_data.get('price')
        change_pct = market_data.get('change_pct', 0)
        symbol = market_data.get('symbol', '')

        bb_lower = indicators.get('bb_lower')
        bb_upper = indicators.get('bb_upper')
        rsi = indicators.get('rsi_14')
        vol_ratio = indicators.get('volume_ratio')

        if any(v is None for v in [bb_lower, bb_upper, rsi, vol_ratio, price]):
            return None

        if vol_ratio > 3.0:
            return None

        score = 0
        buy_conditions = []
        sell_conditions = []

        if price <= bb_lower * 1.003:
            score += 35
            buy_conditions.append('at_bb_lower')
        elif price >= bb_upper * 0.997:
            score += 35
            sell_conditions.append('at_bb_upper')

        if rsi < 35:
            score += 30
            buy_conditions.append('rsi_oversold')
        elif rsi > 65:
            score += 30
            sell_conditions.append('rsi_overbought')

        if vol_ratio < 1.5:
            score += 20
            if change_pct < 0:
                buy_conditions.append('calm_volume_dip')
            else:
                sell_conditions.append('calm_volume_rally')

        if change_pct < -1.5:
            score += 15
            buy_conditions.append('sharp_dip')
        elif change_pct > 1.5:
            score += 15
            sell_conditions.append('sharp_rally')

        if score >= MIN_CONFIDENCE and len(buy_conditions) >= 2:
            return {
                'symbol': symbol,
                'side': 'BUY',
                'confidence': min(score, 95),
                'reason': ' | '.join(buy_conditions),
                'stop_loss_pct': 0.02,
                'take_profit_pct': 0.04,
                'features': indicators.copy()
            }

        if score >= MIN_CONFIDENCE and len(sell_conditions) >= 2:
            return {
                'symbol': symbol,
                'side': 'SELL',
                'confidence': min(score, 95),
                'reason': ' | '.join(sell_conditions),
                'stop_loss_pct': 0.02,
                'take_profit_pct': 0.04,
                'features': indicators.copy()
            }

        return None

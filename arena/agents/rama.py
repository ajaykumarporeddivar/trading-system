# arena/agents/rama.py
from typing import Dict, Any, Optional
from arena.base_agent import BaseAgent
from arena.config import MIN_CONFIDENCE
from core.logger import logger


class RamaAgent(BaseAgent):
    """Macro/trend strategy: Patient macro trend follower. BTC/USDT is leading indicator.
    Trades with the macro trend only. Uses EMA crossover (not SMA).

    BUY conditions:
      - price > ema_50  (price above long-term trend)              -> +30
      - ema_21 > ema_50  (short-term above long-term - golden zone) -> +30
      - rsi > 50 and rsi < 70  (trend confirmed, not overbought)   -> +25
      - vol_ratio > 1.2  (trend has participation)                  -> +15
    SELL conditions:
      - price < ema_50                                              -> +30
      - ema_21 < ema_50  (death cross zone)                         -> +30
      - rsi < 50 and rsi > 30                                       -> +25
      - vol_ratio > 1.2                                             -> +15
    Hard filters (return None):
      - rsi > 78 (already overbought, missed the move)
      - rsi < 22 (already oversold, bounce coming)
    Stop: 3% | Target: 9%
    """

    def __init__(self, order_db_path: str):
        super().__init__(name='RAMA', strategy_name='Macro Trend', order_db_path=order_db_path)

    def generate_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        indicators = market_data.get('indicators', {})
        price = market_data.get('price')
        change_pct = market_data.get('change_pct', 0)
        symbol = market_data.get('symbol', '')

        ema_21 = indicators.get('ema_21')
        ema_50 = indicators.get('ema_50')
        rsi = indicators.get('rsi_14')
        vol_ratio = indicators.get('volume_ratio')

        if any(v is None for v in [ema_21, ema_50, rsi, vol_ratio, price]):
            return None

        if rsi > 78 or rsi < 22:
            return None

        score = 0
        buy_conditions = []
        sell_conditions = []

        if price > ema_50:
            score += 30
            buy_conditions.append('above_ema50')
        elif price < ema_50:
            score += 30
            sell_conditions.append('below_ema50')

        if ema_21 > ema_50:
            score += 30
            buy_conditions.append('ema21_above_ema50')
        elif ema_21 < ema_50:
            score += 30
            sell_conditions.append('ema21_below_ema50')

        if 50 < rsi < 70:
            score += 25
            buy_conditions.append('rsi_bullish_zone')
        elif 30 < rsi < 50:
            score += 25
            sell_conditions.append('rsi_bearish_zone')

        if vol_ratio > 1.2:
            score += 15
            if price > ema_50:
                buy_conditions.append('trend_participation')
            else:
                sell_conditions.append('trend_participation')

        if score >= MIN_CONFIDENCE and len(buy_conditions) >= 2:
            return {
                'symbol': symbol,
                'side': 'BUY',
                'confidence': min(score, 95),
                'reason': ' | '.join(buy_conditions),
                'stop_loss_pct': 0.03,
                'take_profit_pct': 0.09,
                'features': indicators.copy()
            }

        if score >= MIN_CONFIDENCE and len(sell_conditions) >= 2:
            return {
                'symbol': symbol,
                'side': 'SELL',
                'confidence': min(score, 95),
                'reason': ' | '.join(sell_conditions),
                'stop_loss_pct': 0.03,
                'take_profit_pct': 0.09,
                'features': indicators.copy()
            }

        return None

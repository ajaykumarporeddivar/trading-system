# arena/agents/rani.py
from typing import Dict, Any, Optional
from arena.base_agent import BaseAgent
from arena.config import MIN_CONFIDENCE



class RaniAgent(BaseAgent):
    """Volatility expansion strategy: Trade volatility spikes. ATR expansion = big move starting.
    ATR collapse after rally = trap - fade it.

    BUY conditions (vol expansion long):
      - atr > price * 0.020    (ATR > 2% of price - expanding)     -> +35
      - macd > macd_signal                                          -> +25
      - 45 < rsi < 68                                               -> +20
      - vol_ratio > 1.5                                             -> +20
    SELL conditions (vol crush / trap fade):
      - atr < price * 0.008    (ATR < 0.8% - vol collapsed)        -> +35
      - change_pct > 2.0       (rally just happened)                -> +25
      - rsi > 60                                                    -> +20
      - macd < macd_signal                                          -> +15
    Dynamic SL/TP:
      - atr_pct = atr / price
      - stop_loss_pct = max(0.015, min(0.06, atr_pct * 1.5))
      - take_profit_pct = max(0.03, min(0.10, atr_pct * 2.5))
    Hard filters (return None):
      - atr is None
    """

    def __init__(self, order_db_path: str):
        super().__init__(name='RANI', strategy_name='Volatility Expansion', order_db_path=order_db_path)

    def generate_signal(self, market_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        indicators = market_data.get('indicators', {})
        price = market_data.get('price')
        change_pct = market_data.get('change_pct', 0)
        symbol = market_data.get('symbol', '')

        atr = indicators.get('atr_14')
        macd = indicators.get('macd')
        macd_signal = indicators.get('macd_signal')
        rsi = indicators.get('rsi_14')
        vol_ratio = indicators.get('volume_ratio')

        if any(v is None for v in [atr, macd, macd_signal, rsi, vol_ratio, price]):
            return None

        score = 0
        buy_conditions = []
        sell_conditions = []

        if atr > price * 0.020:
            score += 35
            buy_conditions.append('atr_expanding')
        elif atr < price * 0.008:
            score += 35
            sell_conditions.append('atr_collapsed')

        if macd > macd_signal:
            score += 25
            buy_conditions.append('macd_bullish')
        elif macd < macd_signal:
            score += 15
            sell_conditions.append('macd_bearish')

        if 45 < rsi < 68:
            score += 20
            buy_conditions.append('rsi_mid_range')
        elif rsi > 60:
            score += 20
            sell_conditions.append('rsi_elevated')

        if vol_ratio > 1.5:
            score += 20
            buy_conditions.append('volume_spike')

        if change_pct > 2.0:
            score += 25
            sell_conditions.append('recent_rally')

        atr_pct = atr / price
        sl_pct = max(0.015, min(0.06, atr_pct * 1.5))
        tp_pct = max(0.03, min(0.10, atr_pct * 2.5))

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

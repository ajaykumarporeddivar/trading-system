# arena/agents/meenakshi.py
from typing import Dict, Any, Optional
from arena.base_agent import BaseAgent
from arena.config import MIN_CONFIDENCE



class MeenakshiAgent(BaseAgent):
    """Sentiment/crowd psychology strategy: Read crowd fear and greed via price action.
    Buys quiet optimism. Sells quiet fear. Avoids euphoria and panic.

    BUY conditions:
      - 0.3 < change_pct < 2.5   (positive but not euphoric)       -> +35
      - rsi < 60                                                    -> +25
      - 0.7 < vol_ratio < 2.0    (normal to slightly elevated)      -> +20
      - macd > macd_signal                                          -> +20
    SELL conditions:
      - -2.5 < change_pct < -0.3  (negative but not panicking)     -> +35
      - rsi > 40                                                    -> +25
      - 0.7 < vol_ratio < 2.0                                       -> +20
      - macd < macd_signal                                          -> +20
    Hard filters (return None - extreme crowd behaviour):
      - change_pct > 4.0   (euphoria - late, dangerous)
      - change_pct < -5.0  (panic - possible reversal coming)
      - rsi > 80           (crowd already all in)
      - rsi < 20           (crowd capitulated - bounce risk)
    Stop: 2.5% | Target: 6%
    """

    def __init__(self, order_db_path: str):
        super().__init__(name='MEENAKSHI', strategy_name='Sentiment', order_db_path=order_db_path)

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

        if change_pct > 4.0 or change_pct < -5.0:
            return None
        if rsi > 80 or rsi < 20:
            return None

        score = 0
        buy_conditions = []
        sell_conditions = []

        if 0.3 < change_pct < 2.5:
            score += 35
            buy_conditions.append('quiet_optimism')
        elif -2.5 < change_pct < -0.3:
            score += 35
            sell_conditions.append('quiet_fear')

        if rsi < 60:
            score += 25
            buy_conditions.append('rsi_not_overbought')
        elif rsi > 40:
            score += 25
            sell_conditions.append('rsi_not_oversold')

        if 0.7 < vol_ratio < 2.0:
            score += 20
            if change_pct > 0:
                buy_conditions.append('normal_volume')
            else:
                sell_conditions.append('normal_volume')

        if macd > macd_signal:
            score += 20
            buy_conditions.append('macd_bullish')
        elif macd < macd_signal:
            score += 20
            sell_conditions.append('macd_bearish')

        if score >= MIN_CONFIDENCE and len(buy_conditions) >= 2:
            return {
                'symbol': symbol,
                'side': 'BUY',
                'confidence': min(score, 95),
                'reason': ' | '.join(buy_conditions),
                'stop_loss_pct': 0.025,
                'take_profit_pct': 0.06,
                'features': indicators.copy()
            }

        if score >= MIN_CONFIDENCE and len(sell_conditions) >= 2:
            return {
                'symbol': symbol,
                'side': 'SELL',
                'confidence': min(score, 95),
                'reason': ' | '.join(sell_conditions),
                'stop_loss_pct': 0.025,
                'take_profit_pct': 0.06,
                'features': indicators.copy()
            }

        return None

from typing import Dict, List, Any
from core.config import Config
from core.logger import logger

class SignalEngine:
    INDICATORS = ['ema_trend', 'rsi', 'macd', 'bollinger', 'volume', 'stoch_rsi', 'adx', 'fibonacci']

    @staticmethod
    def score_indicator(indicator_data: Dict[str, Any]) -> Dict[str, str]:
        scores = {}
        current_price = indicator_data.get('current_price', 0)

        # EMA Trend
        ema_21 = indicator_data.get('ema_21')
        ema_50 = indicator_data.get('ema_50')
        if ema_21 and ema_50:
            if ema_21 > ema_50 and current_price > ema_21:
                scores['ema_trend'] = 'bullish'
            elif ema_21 < ema_50 and current_price < ema_21:
                scores['ema_trend'] = 'bearish'
            else:
                scores['ema_trend'] = 'neutral'
        else:
            scores['ema_trend'] = 'neutral'

        # RSI
        rsi = indicator_data.get('rsi_14')
        if rsi:
            if rsi > 70:
                scores['rsi'] = 'bearish'
            elif rsi < 30:
                scores['rsi'] = 'bullish'
            elif rsi > 50:
                scores['rsi'] = 'bullish'
            else:
                scores['rsi'] = 'bearish'
        else:
            scores['rsi'] = 'neutral'

        # MACD
        macd = indicator_data.get('macd')
        macd_signal = indicator_data.get('macd_signal')
        macd_hist = indicator_data.get('macd_histogram')
        if macd and macd_signal:
            if macd > macd_signal and macd_hist and macd_hist > 0:
                scores['macd'] = 'bullish'
            elif macd < macd_signal and macd_hist and macd_hist < 0:
                scores['macd'] = 'bearish'
            else:
                scores['macd'] = 'neutral'
        else:
            scores['macd'] = 'neutral'

        # Bollinger Bands
        bb_upper = indicator_data.get('bb_upper')
        bb_lower = indicator_data.get('bb_lower')
        if bb_upper and bb_lower:
            if current_price > bb_upper:
                scores['bollinger'] = 'bearish'
            elif current_price < bb_lower:
                scores['bollinger'] = 'bullish'
            else:
                scores['bollinger'] = 'neutral'
        else:
            scores['bollinger'] = 'neutral'

        # Volume
        vol_ratio = indicator_data.get('volume_ratio')
        if vol_ratio and vol_ratio > 1.5:
            if current_price > indicator_data.get('ema_21', 0):
                scores['volume'] = 'bullish'
            else:
                scores['volume'] = 'bearish'
        else:
            scores['volume'] = 'neutral'

        # Stoch RSI
        k = indicator_data.get('stoch_rsi_k')
        d = indicator_data.get('stoch_rsi_d')
        if k and d:
            if k < 20 and k > d:
                scores['stoch_rsi'] = 'bullish'
            elif k > 80 and k < d:
                scores['stoch_rsi'] = 'bearish'
            else:
                scores['stoch_rsi'] = 'neutral'
        else:
            scores['stoch_rsi'] = 'neutral'

        # ADX
        adx = indicator_data.get('adx_14')
        if adx and adx > 25:
            if current_price > indicator_data.get('ema_21', 0):
                scores['adx'] = 'bullish'
            else:
                scores['adx'] = 'bearish'
        else:
            scores['adx'] = 'neutral'

        # Fibonacci
        fib_levels = indicator_data.get('fibonacci_levels', {})
        if fib_levels and current_price:
            fib_618 = fib_levels.get('0.618', 0)
            fib_382 = fib_levels.get('0.382', 0)
            if current_price <= fib_618:
                scores['fibonacci'] = 'bullish'
            elif current_price >= fib_382:
                scores['fibonacci'] = 'bearish'
            else:
                scores['fibonacci'] = 'neutral'
        else:
            scores['fibonacci'] = 'neutral'

        return scores

    @staticmethod
    def compute_confidence(scores: Dict[str, str]) -> int:
        total = len(scores)
        bullish = sum(1 for s in scores.values() if s == 'bullish')
        bearish = sum(1 for s in scores.values() if s == 'bearish')
        dominant = max(bullish, bearish)
        return int((dominant / total) * 100) if total > 0 else 0

    @staticmethod
    def generate_verdict(confidence: int, scores: Dict[str, str]) -> str:
        bullish = sum(1 for s in scores.values() if s == 'bullish')
        bearish = sum(1 for s in scores.values() if s == 'bearish')

        if confidence < Config.MIN_CONFIDENCE:
            return 'NO_TRADE'
        if bullish > bearish:
            return 'LONG'
        elif bearish > bullish:
            return 'SHORT'
        return 'NO_TRADE'

    @staticmethod
    def analyze_symbol(symbol: str, indicator_data: Dict[str, Any]) -> Dict[str, Any]:
        scores = SignalEngine.score_indicator(indicator_data)
        confidence = SignalEngine.compute_confidence(scores)
        verdict = SignalEngine.generate_verdict(confidence, scores)

        result = {
            'symbol': symbol,
            'verdict': verdict,
            'confidence': confidence,
            'indicator_scores': scores,
            'timestamp': indicator_data.get('timestamp')
        }

        logger.info(f'{symbol}: {verdict} (confidence: {confidence}%)')
        return result

    @staticmethod
    def analyze_all(indicator_results: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for symbol, data in indicator_results.items():
            result = SignalEngine.analyze_symbol(symbol, data)
            results.append(result)
        return results

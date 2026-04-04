import pytest
from engine.signal_engine import SignalEngine
from core.config import Config

class TestSignalEngine:
    def test_score_indicator_bullish(self):
        data = {
            'current_price': 51000,
            'ema_21': 50500,
            'ema_50': 49000,
            'rsi_14': 55,
            'macd': 100,
            'macd_signal': 80,
            'macd_histogram': 20,
            'bb_upper': 52000,
            'bb_lower': 48000,
            'volume_ratio': 2.0,
            'stoch_rsi_k': 25,
            'stoch_rsi_d': 20,
            'adx_14': 30,
            'fibonacci_levels': {'0.618': 50000, '0.382': 52000}
        }
        scores = SignalEngine.score_indicator(data)
        assert scores['ema_trend'] == 'bullish'
        assert scores['macd'] == 'bullish'
        assert scores['volume'] == 'bullish'

    def test_score_indicator_bearish(self):
        data = {
            'current_price': 49000,
            'ema_21': 50500,
            'ema_50': 51000,
            'rsi_14': 75,
            'macd': -100,
            'macd_signal': -80,
            'macd_histogram': -20,
            'bb_upper': 52000,
            'bb_lower': 48000,
            'volume_ratio': 2.0,
            'stoch_rsi_k': 85,
            'stoch_rsi_d': 80,
            'adx_14': 30,
            'fibonacci_levels': {'0.618': 50000, '0.382': 52000}
        }
        scores = SignalEngine.score_indicator(data)
        assert scores['ema_trend'] == 'bearish'
        assert scores['rsi'] == 'bearish'
        assert scores['macd'] == 'bearish'

    def test_compute_confidence(self):
        scores = {'ema_trend': 'bullish', 'rsi': 'bullish', 'macd': 'bullish', 'bollinger': 'neutral', 'volume': 'bullish', 'stoch_rsi': 'bullish', 'adx': 'bullish', 'fibonacci': 'bullish'}
        confidence = SignalEngine.compute_confidence(scores)
        assert confidence == 87

    def test_generate_verdict_long(self):
        scores = {'ema_trend': 'bullish', 'rsi': 'bullish', 'macd': 'bullish', 'bollinger': 'bullish', 'volume': 'bullish', 'stoch_rsi': 'neutral', 'adx': 'bullish', 'fibonacci': 'neutral'}
        confidence = SignalEngine.compute_confidence(scores)
        verdict = SignalEngine.generate_verdict(confidence, scores)
        assert verdict == 'LONG'

    def test_generate_verdict_no_trade_low_confidence(self):
        scores = {'ema_trend': 'bullish', 'rsi': 'bearish', 'macd': 'neutral', 'bollinger': 'neutral', 'volume': 'bullish', 'stoch_rsi': 'bearish', 'adx': 'neutral', 'fibonacci': 'neutral'}
        confidence = SignalEngine.compute_confidence(scores)
        verdict = SignalEngine.generate_verdict(confidence, scores)
        assert verdict == 'NO_TRADE'

    def test_analyze_symbol(self):
        data = {
            'current_price': 51000,
            'ema_21': 50500,
            'ema_50': 49000,
            'rsi_14': 55,
            'macd': 100,
            'macd_signal': 80,
            'macd_histogram': 20,
            'bb_upper': 52000,
            'bb_lower': 48000,
            'volume_ratio': 2.0,
            'stoch_rsi_k': 25,
            'stoch_rsi_d': 20,
            'adx_14': 30,
            'fibonacci_levels': {'0.618': 50000, '0.382': 52000},
            'timestamp': '2024-01-01T00:00:00'
        }
        result = SignalEngine.analyze_symbol('BTC/USDT', data)
        assert result['symbol'] == 'BTC/USDT'
        assert result['verdict'] in ['LONG', 'SHORT', 'NO_TRADE']
        assert 0 <= result['confidence'] <= 100
        assert 'indicator_scores' in result

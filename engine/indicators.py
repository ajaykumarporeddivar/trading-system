import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional

class TechnicalIndicators:
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        return data.ewm(span=period, adjust=False).mean()

    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        return data.rolling(window=period).mean()

    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        delta = data.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/period, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {'macd': macd_line, 'signal': signal_line, 'histogram': histogram}

    @staticmethod
    def bollinger_bands(data: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, pd.Series]:
        sma = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        return {'upper': upper, 'middle': sma, 'lower': lower, 'width': (upper - lower) / sma}

    @staticmethod
    def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
        avg_volume = volume.rolling(window=period).mean()
        return volume / avg_volume

    @staticmethod
    def stoch_rsi(close: pd.Series, period: int = 14, smooth_k: int = 3, smooth_d: int = 3) -> Dict[str, pd.Series]:
        rsi = TechnicalIndicators.rsi(close, period)
        lowest_rsi = rsi.rolling(window=period).min()
        highest_rsi = rsi.rolling(window=period).max()
        k = 100 * (rsi - lowest_rsi) / (highest_rsi - lowest_rsi)
        d = k.rolling(window=smooth_d).mean()
        return {'k': k, 'd': d}

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0

        atr = TechnicalIndicators._atr(high, low, close, period)
        plus_di = 100 * (plus_dm.ewm(alpha=1/period, min_periods=period).mean() / atr)
        minus_di = 100 * (abs(minus_dm).ewm(alpha=1/period, min_periods=period).mean() / atr)

        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx.ewm(alpha=1/period, min_periods=period).mean()

    @staticmethod
    def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(alpha=1/period, min_periods=period).mean()

    @staticmethod
    def fibonacci_levels(high: float, low: float) -> Dict[str, float]:
        diff = high - low
        levels = {
            '0.0': high,
            '0.236': high - diff * 0.236,
            '0.382': high - diff * 0.382,
            '0.5': high - diff * 0.5,
            '0.618': high - diff * 0.618,
            '0.786': high - diff * 0.786,
            '1.0': low
        }
        return levels

    @staticmethod
    def compute_all(df: pd.DataFrame) -> Dict[str, Any]:
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']

        ema_21 = TechnicalIndicators.ema(close, 21)
        ema_50 = TechnicalIndicators.ema(close, 50)
        sma_20 = TechnicalIndicators.sma(close, 20)
        sma_50 = TechnicalIndicators.sma(close, 50)
        rsi_14 = TechnicalIndicators.rsi(close, 14)
        macd_data = TechnicalIndicators.macd(close)
        bb_data = TechnicalIndicators.bollinger_bands(close)
        vol_ratio = TechnicalIndicators.volume_ratio(volume)
        stoch_rsi_data = TechnicalIndicators.stoch_rsi(close)
        adx_14 = TechnicalIndicators.adx(high, low, close)
        fib_levels = TechnicalIndicators.fibonacci_levels(high.iloc[-1], low.iloc[-1])
        atr_14 = TechnicalIndicators._atr(high, low, close, 14)
        high_20 = high.rolling(window=20).max()
        low_20 = low.rolling(window=20).min()

        return {
            'ema_21': ema_21.iloc[-1] if len(ema_21) > 0 else None,
            'ema_50': ema_50.iloc[-1] if len(ema_50) > 0 else None,
            'sma_20': sma_20.iloc[-1] if len(sma_20) > 0 else None,
            'sma_50': sma_50.iloc[-1] if len(sma_50) > 0 else None,
            'rsi_14': rsi_14.iloc[-1] if len(rsi_14) > 0 else None,
            'macd': macd_data['macd'].iloc[-1] if len(macd_data['macd']) > 0 else None,
            'macd_signal': macd_data['signal'].iloc[-1] if len(macd_data['signal']) > 0 else None,
            'macd_histogram': macd_data['histogram'].iloc[-1] if len(macd_data['histogram']) > 0 else None,
            'bb_upper': bb_data['upper'].iloc[-1] if len(bb_data['upper']) > 0 else None,
            'bb_middle': bb_data['middle'].iloc[-1] if len(bb_data['middle']) > 0 else None,
            'bb_lower': bb_data['lower'].iloc[-1] if len(bb_data['lower']) > 0 else None,
            'bb_width': bb_data['width'].iloc[-1] if len(bb_data['width']) > 0 else None,
            'volume_ratio': vol_ratio.iloc[-1] if len(vol_ratio) > 0 else None,
            'stoch_rsi_k': stoch_rsi_data['k'].iloc[-1] if len(stoch_rsi_data['k']) > 0 else None,
            'stoch_rsi_d': stoch_rsi_data['d'].iloc[-1] if len(stoch_rsi_data['d']) > 0 else None,
            'adx_14': adx_14.iloc[-1] if len(adx_14) > 0 else None,
            'fibonacci_levels': fib_levels,
            'atr_14': atr_14.iloc[-1] if len(atr_14) > 0 else None,
            'high_20': high_20.iloc[-1] if len(high_20) > 0 else None,
            'low_20': low_20.iloc[-1] if len(low_20) > 0 else None,
            'current_price': close.iloc[-1]
        }

    @staticmethod
    def compute_support_resistance(df: pd.DataFrame) -> Dict[str, Any]:
        close = df['close']
        high = df['high']
        low = df['low']
        current_price = close.iloc[-1]
        prev_high = high.iloc[-2] if len(high) >= 2 else current_price
        prev_low = low.iloc[-2] if len(low) >= 2 else current_price
        prev_close = close.iloc[-2] if len(close) >= 2 else current_price
        atr_14 = TechnicalIndicators._atr(high, low, close, 14).iloc[-1] if len(close) >= 14 else 0
        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = 2 * pivot - prev_low
        r2 = pivot + (prev_high - prev_low)
        r3 = prev_high + 2 * (pivot - prev_low)
        s1 = 2 * pivot - prev_high
        s2 = pivot - (prev_high - prev_low)
        s3 = prev_low - 2 * (prev_high - pivot)
        swing_high = high.rolling(window=20).max().iloc[-1] if len(high) >= 20 else prev_high
        swing_low = low.rolling(window=20).min().iloc[-1] if len(low) >= 20 else prev_low
        bb_data = TechnicalIndicators.bollinger_bands(close)
        bb_upper = bb_data['upper'].iloc[-1] if len(bb_data['upper']) > 0 else current_price
        bb_lower = bb_data['lower'].iloc[-1] if len(bb_data['lower']) > 0 else current_price
        ema_21 = TechnicalIndicators.ema(close, 21).iloc[-1] if len(close) >= 21 else current_price
        ema_50 = TechnicalIndicators.ema(close, 50).iloc[-1] if len(close) >= 50 else current_price
        levels = [
            {'level': r3, 'type': 'resistance', 'label': 'R3', 'distance': (r3 - current_price) / current_price * 100},
            {'level': r2, 'type': 'resistance', 'label': 'R2', 'distance': (r2 - current_price) / current_price * 100},
            {'level': r1, 'type': 'resistance', 'label': 'R1', 'distance': (r1 - current_price) / current_price * 100},
            {'level': swing_high, 'type': 'resistance', 'label': 'Swing High', 'distance': (swing_high - current_price) / current_price * 100},
            {'level': bb_upper, 'type': 'resistance', 'label': 'BB Upper', 'distance': (bb_upper - current_price) / current_price * 100},
            {'level': ema_21, 'type': 'dynamic', 'label': 'EMA 21', 'distance': (ema_21 - current_price) / current_price * 100},
            {'level': ema_50, 'type': 'dynamic', 'label': 'EMA 50', 'distance': (ema_50 - current_price) / current_price * 100},
            {'level': current_price, 'type': 'current', 'label': 'Price', 'distance': 0},
            {'level': bb_lower, 'type': 'support', 'label': 'BB Lower', 'distance': (bb_lower - current_price) / current_price * 100},
            {'level': swing_low, 'type': 'support', 'label': 'Swing Low', 'distance': (swing_low - current_price) / current_price * 100},
            {'level': s1, 'type': 'support', 'label': 'S1', 'distance': (s1 - current_price) / current_price * 100},
            {'level': s2, 'type': 'support', 'label': 'S2', 'distance': (s2 - current_price) / current_price * 100},
            {'level': s3, 'type': 'support', 'label': 'S3', 'distance': (s3 - current_price) / current_price * 100},
        ]
        projected_r1 = pivot * 1.005 + atr_14 * 0.5
        projected_r2 = pivot * 1.01 + atr_14
        projected_s1 = pivot * 0.995 - atr_14 * 0.5
        projected_s2 = pivot * 0.99 - atr_14
        projected = [
            {'level': projected_r2, 'type': 'projected_resistance', 'label': 'Proj R2', 'distance': (projected_r2 - current_price) / current_price * 100},
            {'level': projected_r1, 'type': 'projected_resistance', 'label': 'Proj R1', 'distance': (projected_r1 - current_price) / current_price * 100},
            {'level': projected_s1, 'type': 'projected_support', 'label': 'Proj S1', 'distance': (projected_s1 - current_price) / current_price * 100},
            {'level': projected_s2, 'type': 'projected_support', 'label': 'Proj S2', 'distance': (projected_s2 - current_price) / current_price * 100},
        ]
        return {
            'current_price': round(current_price, 4),
            'pivot': round(pivot, 4),
            'levels': [{'level': round(l['level'], 4), 'type': l['type'], 'label': l['label'], 'distance': round(l['distance'], 2)} for l in levels],
            'projected': [{'level': round(p['level'], 4), 'type': p['type'], 'label': p['label'], 'distance': round(p['distance'], 2)} for p in projected],
            'atr_14': round(atr_14, 4),
            'swing_high': round(swing_high, 4),
            'swing_low': round(swing_low, 4),
        }

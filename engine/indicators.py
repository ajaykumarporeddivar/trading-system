import pandas as pd
import numpy as np
from typing import Dict, Any

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

import pytest
import pandas as pd
import numpy as np
from engine.indicators import TechnicalIndicators

@pytest.fixture
def sample_data():
    np.random.seed(42)
    n = 100
    close = np.cumsum(np.random.randn(n)) + 100
    high = close + np.abs(np.random.randn(n))
    low = close - np.abs(np.random.randn(n))
    volume = np.random.randint(1000, 10000, n)
    return pd.DataFrame({
        'timestamp': pd.date_range('2024-01-01', periods=n, freq='4h'),
        'open': close,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    })

class TestTechnicalIndicators:
    def test_ema(self, sample_data):
        result = TechnicalIndicators.ema(sample_data['close'], 21)
        assert len(result) == len(sample_data)
        assert not result.isna().all()

    def test_rsi(self, sample_data):
        result = TechnicalIndicators.rsi(sample_data['close'], 14)
        assert len(result) == len(sample_data)
        assert result.iloc[-1] >= 0 and result.iloc[-1] <= 100

    def test_macd(self, sample_data):
        result = TechnicalIndicators.macd(sample_data['close'])
        assert 'macd' in result
        assert 'signal' in result
        assert 'histogram' in result
        assert len(result['macd']) == len(sample_data)

    def test_bollinger_bands(self, sample_data):
        result = TechnicalIndicators.bollinger_bands(sample_data['close'])
        assert 'upper' in result
        assert 'middle' in result
        assert 'lower' in result
        valid = result['upper'].dropna()
        assert (valid >= result['lower'].dropna()).all()

    def test_volume_ratio(self, sample_data):
        result = TechnicalIndicators.volume_ratio(sample_data['volume'])
        assert len(result) == len(sample_data)
        assert result.iloc[-1] > 0

    def test_stoch_rsi(self, sample_data):
        result = TechnicalIndicators.stoch_rsi(sample_data['close'])
        assert 'k' in result
        assert 'd' in result

    def test_adx(self, sample_data):
        result = TechnicalIndicators.adx(sample_data['high'], sample_data['low'], sample_data['close'])
        assert len(result) == len(sample_data)
        assert result.iloc[-1] >= 0

    def test_fibonacci_levels(self):
        result = TechnicalIndicators.fibonacci_levels(110.0, 90.0)
        assert '0.0' in result
        assert '0.618' in result
        assert result['0.0'] == 110.0
        assert result['1.0'] == 90.0
        assert result['0.5'] == 100.0

    def test_compute_all(self, sample_data):
        result = TechnicalIndicators.compute_all(sample_data)
        assert 'ema_21' in result
        assert 'ema_50' in result
        assert 'rsi_14' in result
        assert 'macd' in result
        assert 'bb_upper' in result
        assert 'volume_ratio' in result
        assert 'stoch_rsi_k' in result
        assert 'adx_14' in result
        assert 'current_price' in result
        assert result['current_price'] == sample_data['close'].iloc[-1]

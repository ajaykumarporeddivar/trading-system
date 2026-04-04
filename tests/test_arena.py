import pytest
import os
import json
import tempfile
from unittest.mock import MagicMock, patch

from arena.config import (
    INITIAL_BALANCE, RISK_PER_TRADE, MAX_EXPOSURE, MAX_POSITIONS,
    DAILY_LOSS_CAP, MAX_DRAWDOWN, MIN_CONFIDENCE
)
from arena.base_agent import BaseAgent
from arena.agents.ajay import AjayAgent
from arena.agents.vijay import VijayAgent
from arena.agents.sanjay import SanjayAgent
from arena.agents.rama import RamaAgent
from arena.agents.meenakshi import MeenakshiAgent
from arena.agents.rani import RaniAgent


@pytest.fixture
def temp_order_file():
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def sample_market_data():
    return {
        'symbol': 'BTC/USDT',
        'price': 50000.0,
        'change_pct': 1.2,
        'indicators': {
            'ema_21': 49500.0,
            'ema_50': 48000.0,
            'sma_20': 49800.0,
            'sma_50': 48500.0,
            'rsi_14': 55.0,
            'macd': 100.0,
            'macd_signal': 80.0,
            'macd_histogram': 20.0,
            'bb_upper': 52000.0,
            'bb_middle': 50000.0,
            'bb_lower': 48000.0,
            'bb_width': 0.08,
            'volume_ratio': 1.8,
            'stoch_rsi_k': 60.0,
            'stoch_rsi_d': 55.0,
            'adx_14': 30.0,
            'atr_14': 800.0,
            'atr': 800.0,
            'high_20': 51000.0,
            'low_20': 47000.0,
            'current_price': 50000.0
        }
    }


class TestBaseAgent:
    @pytest.fixture
    def agent(self, temp_order_file):
        agent = AjayAgent(temp_order_file)
        agent.open_positions = {}
        agent.closed_positions = {}
        agent.virtual_capital = INITIAL_BALANCE
        agent.peak_capital = INITIAL_BALANCE
        agent.daily_start_capital = INITIAL_BALANCE
        return agent

    def test_init(self, agent):
        assert agent.virtual_capital == 10000
        assert agent.name == 'AJAY'
        assert agent.strategy_name == 'Momentum'

    def test_check_risk_limits_ok(self, agent):
        assert agent.check_risk_limits() is True

    def test_check_risk_limits_daily_loss(self, agent):
        agent.virtual_capital = 9600
        assert agent.check_risk_limits() is False

    def test_check_risk_limits_drawdown(self, agent):
        agent.virtual_capital = 8900
        assert agent.check_risk_limits() is False

    def test_get_performance_empty(self, agent):
        perf = agent.get_performance()
        assert perf['total_trades'] == 0
        assert perf['win_rate'] == 0
        assert perf['virtual_capital'] == 10000

    def test_close_position_win(self, agent):
        agent.open_positions = {
            'abc123': {
                'order_id': 'abc123',
                'agent': 'TEST',
                'strategy': 'Test',
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'entry_price': 50000.0,
                'quantity': 0.1,
                'position_value': 5000.0,
                'stop_loss': 49000.0,
                'take_profit': 52000.0,
                'stop_loss_pct': 0.02,
                'take_profit_pct': 0.04,
                'confidence': 70,
                'reason': 'test',
                'status': 'open',
                'opened_at': '2024-01-01T00:00:00',
                'closed_at': None,
                'exit_price': None,
                'pnl': None,
                'pnl_pct': None,
                'outcome': None,
                'close_reason': None,
                'features': {}
            }
        }
        agent.close_position('abc123', 51000.0, 'take_profit')
        assert agent.closed_positions['abc123']['outcome'] == 'WIN'
        assert agent.closed_positions['abc123']['pnl'] > 0
        assert agent.virtual_capital > 10000

    def test_close_position_loss(self, agent):
        agent.open_positions = {
            'def456': {
                'order_id': 'def456',
                'agent': 'TEST',
                'strategy': 'Test',
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'entry_price': 50000.0,
                'quantity': 0.1,
                'position_value': 5000.0,
                'stop_loss': 49000.0,
                'take_profit': 52000.0,
                'stop_loss_pct': 0.02,
                'take_profit_pct': 0.04,
                'confidence': 70,
                'reason': 'test',
                'status': 'open',
                'opened_at': '2024-01-01T00:00:00',
                'closed_at': None,
                'exit_price': None,
                'pnl': None,
                'pnl_pct': None,
                'outcome': None,
                'close_reason': None,
                'features': {}
            }
        }
        agent.close_position('def456', 49000.0, 'stop_loss')
        assert agent.closed_positions['def456']['outcome'] == 'LOSS'
        assert agent.closed_positions['def456']['pnl'] < 0

    def test_check_exits(self, agent):
        agent.open_positions = {
            'ghi789': {
                'order_id': 'ghi789',
                'agent': 'TEST',
                'strategy': 'Test',
                'symbol': 'BTC/USDT',
                'side': 'BUY',
                'entry_price': 50000.0,
                'quantity': 0.1,
                'position_value': 5000.0,
                'stop_loss': 49000.0,
                'take_profit': 52000.0,
                'stop_loss_pct': 0.02,
                'take_profit_pct': 0.04,
                'confidence': 70,
                'reason': 'test',
                'status': 'open',
                'opened_at': '2024-01-01T00:00:00',
                'closed_at': None,
                'exit_price': None,
                'pnl': None,
                'pnl_pct': None,
                'outcome': None,
                'close_reason': None,
                'features': {}
            }
        }
        agent.check_exits({'BTC/USDT': 49000.0})
        assert len(agent.open_positions) == 0
        assert len(agent.closed_positions) == 1

    def test_save_load_state(self, temp_order_file):
        agent = AjayAgent(temp_order_file)
        agent.virtual_capital = 10500
        agent.peak_capital = 11000
        agent.daily_start_capital = 10000
        agent.open_positions = {}
        agent.closed_positions = {}
        agent._save_state()

        agent2 = AjayAgent(temp_order_file)
        assert agent2.virtual_capital == 10500
        assert agent2.peak_capital == 11000

    def test_reset_daily_capital(self, agent):
        agent.virtual_capital = 10500
        agent.reset_daily_capital()
        assert agent.daily_start_capital == 10500


class TestAjayAgent:
    def test_buy_signal(self, temp_order_file, sample_market_data):
        agent = AjayAgent(temp_order_file)
        signal = agent.generate_signal(sample_market_data)
        assert signal is not None
        assert signal['side'] == 'BUY'
        assert signal['confidence'] >= MIN_CONFIDENCE

    def test_no_signal_extreme_rsi(self, temp_order_file):
        data = {
            'symbol': 'BTC/USDT',
            'price': 50000.0,
            'change_pct': 1.0,
            'indicators': {
                'macd': 100.0,
                'macd_signal': 80.0,
                'rsi_14': 85.0,
                'volume_ratio': 1.8
            }
        }
        agent = AjayAgent(temp_order_file)
        signal = agent.generate_signal(data)
        assert signal is None


class TestRamaAgent:
    def test_buy_signal_ema_crossover(self, temp_order_file, sample_market_data):
        agent = RamaAgent(temp_order_file)
        signal = agent.generate_signal(sample_market_data)
        assert signal is not None
        assert signal['side'] == 'BUY'

    def test_sell_signal_below_ema(self, temp_order_file):
        data = {
            'symbol': 'BTC/USDT',
            'price': 47000.0,
            'change_pct': -1.0,
            'indicators': {
                'ema_21': 49000.0,
                'ema_50': 50000.0,
                'rsi_14': 40.0,
                'volume_ratio': 1.5
            }
        }
        agent = RamaAgent(temp_order_file)
        signal = agent.generate_signal(data)
        assert signal is not None
        assert signal['side'] == 'SELL'


class TestVijayAgent:
    def test_buy_signal_at_bb_lower(self, temp_order_file):
        data = {
            'symbol': 'BTC/USDT',
            'price': 48050.0,
            'change_pct': -2.0,
            'indicators': {
                'bb_lower': 48000.0,
                'bb_upper': 52000.0,
                'rsi_14': 30.0,
                'volume_ratio': 1.2
            }
        }
        agent = VijayAgent(temp_order_file)
        signal = agent.generate_signal(data)
        assert signal is not None
        assert signal['side'] == 'BUY'


class TestSanjayAgent:
    def test_buy_signal_breakout(self, temp_order_file):
        data = {
            'symbol': 'BTC/USDT',
            'price': 51500.0,
            'change_pct': 1.5,
            'indicators': {
                'high_20': 51000.0,
                'low_20': 47000.0,
                'volume_ratio': 2.5,
                'atr_14': 1000.0
            }
        }
        agent = SanjayAgent(temp_order_file)
        signal = agent.generate_signal(data)
        assert signal is not None
        assert signal['side'] == 'BUY'


class TestMeenakshiAgent:
    def test_buy_signal_quiet_optimism(self, temp_order_file):
        data = {
            'symbol': 'BTC/USDT',
            'price': 50000.0,
            'change_pct': 1.0,
            'indicators': {
                'macd': 100.0,
                'macd_signal': 80.0,
                'rsi_14': 55.0,
                'volume_ratio': 1.2
            }
        }
        agent = MeenakshiAgent(temp_order_file)
        signal = agent.generate_signal(data)
        assert signal is not None
        assert signal['side'] == 'BUY'


class TestRaniAgent:
    def test_buy_signal_vol_expansion(self, temp_order_file):
        data = {
            'symbol': 'BTC/USDT',
            'price': 50000.0,
            'change_pct': 1.0,
            'indicators': {
                'atr_14': 1200.0,
                'macd': 100.0,
                'macd_signal': 80.0,
                'rsi_14': 55.0,
                'volume_ratio': 2.0
            }
        }
        agent = RaniAgent(temp_order_file)
        signal = agent.generate_signal(data)
        assert signal is not None
        assert signal['side'] == 'BUY'

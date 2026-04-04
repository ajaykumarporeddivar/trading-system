import pytest
from engine.risk_calculator import RiskCalculator

class TestRiskCalculator:
    def test_calculate_position_size(self):
        result = RiskCalculator.calculate_position_size(10000, 50000, 49000)
        assert result['quantity'] > 0
        assert result['risk_amount'] == 100
        assert result['position_value'] > 0

    def test_calculate_position_size_invalid_stop(self):
        result = RiskCalculator.calculate_position_size(10000, 50000, 50000)
        assert result['quantity'] == 0
        assert 'error' in result

    def test_check_portfolio_exposure_allowed(self):
        result = RiskCalculator.check_portfolio_exposure(2000, 500, 10000)
        assert result['allowed'] is True
        assert result['new_exposure'] == 0.25

    def test_check_portfolio_exposure_blocked(self):
        result = RiskCalculator.check_portfolio_exposure(3500, 0, 10000)
        assert result['allowed'] is False

    def test_check_daily_loss_allowed(self):
        result = RiskCalculator.check_daily_loss(-200, 10000)
        assert result['allowed'] is True
        assert result['daily_loss_pct'] == 0.02

    def test_check_daily_loss_blocked(self):
        result = RiskCalculator.check_daily_loss(-400, 10000)
        assert result['allowed'] is False

    def test_check_drawdown_allowed(self):
        result = RiskCalculator.check_drawdown(9500, 10000)
        assert result['allowed'] is True
        assert result['drawdown_pct'] == 5.0

    def test_check_drawdown_blocked(self):
        result = RiskCalculator.check_drawdown(8500, 10000)
        assert result['allowed'] is False

    def test_validate_trade_approved(self):
        trade = {'symbol': 'BTC/USDT', 'entry_price': 100, 'stop_loss': 95}
        portfolio = {'balance': 10000, 'current_exposure': 0, 'daily_pnl': 0, 'peak_balance': 10000}
        result = RiskCalculator.validate_trade(trade, portfolio)
        assert result['approved'] is True
        assert result['position_size'] is not None

    def test_validate_trade_blocked_exposure(self):
        trade = {'symbol': 'BTC/USDT', 'entry_price': 50000, 'stop_loss': 49000}
        portfolio = {'balance': 10000, 'current_exposure': 3500, 'daily_pnl': 0, 'peak_balance': 10000}
        result = RiskCalculator.validate_trade(trade, portfolio)
        assert result['approved'] is False
        assert any('exposure' in b.lower() for b in result['blocks'])

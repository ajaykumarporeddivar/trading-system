import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

def _safe_float(key: str, default: str) -> float:
    try:
        return float(os.getenv(key, default))
    except (ValueError, TypeError):
        return float(default)

def _safe_int(key: str, default: str) -> int:
    try:
        return int(os.getenv(key, default))
    except (ValueError, TypeError):
        return int(default)

class Config:
    EXCHANGE = os.getenv('EXCHANGE', 'binance')
    EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')
    EXCHANGE_API_SECRET = os.getenv('EXCHANGE_API_SECRET', '')
    USE_TESTNET = os.getenv('USE_TESTNET', 'true').lower() == 'true'

    TRADING_SYMBOLS = [s.strip() for s in os.getenv('TRADING_SYMBOLS', 'BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT').split(',')]
    TIMEFRAME = os.getenv('TIMEFRAME', '4h')
    MAX_PORTFOLIO_EXPOSURE = _safe_float('MAX_PORTFOLIO_EXPOSURE', '0.30')
    DAILY_LOSS_CAP = _safe_float('DAILY_LOSS_CAP', '0.03')
    MAX_DRAWDOWN = _safe_float('MAX_DRAWDOWN', '0.08')
    RISK_PER_TRADE = _safe_float('RISK_PER_TRADE', '0.01')
    MIN_CONFIDENCE = _safe_int('MIN_CONFIDENCE', '65')
    INITIAL_BALANCE = _safe_float('INITIAL_BALANCE', '10000')

    CYCLE_HOURS = _safe_int('CYCLE_HOURS', '4')
    BRIEFING_HOUR = _safe_int('BRIEFING_HOUR', '8')

    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = _safe_int('SMTP_PORT', '587')
    EMAIL_USER = os.getenv('EMAIL_USER', '')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
    ALERT_EMAIL = os.getenv('ALERT_EMAIL', '')

    DATABASE_PATH = os.getenv('DATABASE_PATH', 'trading_journal.db')
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'trading_system.log')

    @classmethod
    def validate(cls) -> List[str]:
        errors = []
        if not cls.EXCHANGE_API_KEY or cls.EXCHANGE_API_KEY == 'your_api_key_here':
            errors.append('EXCHANGE_API_KEY not set')
        if not cls.EXCHANGE_API_SECRET or cls.EXCHANGE_API_SECRET == 'your_api_secret_here':
            errors.append('EXCHANGE_API_SECRET not set')
        return errors

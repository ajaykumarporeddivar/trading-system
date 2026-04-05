import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

class Config:
    EXCHANGE = os.getenv('EXCHANGE', 'binance')
    EXCHANGE_API_KEY = os.getenv('EXCHANGE_API_KEY', '')
    EXCHANGE_API_SECRET = os.getenv('EXCHANGE_API_SECRET', '')
    USE_TESTNET = os.getenv('USE_TESTNET', 'true').lower() == 'true'

    TRADING_SYMBOLS = [s.strip() for s in os.getenv('TRADING_SYMBOLS', 'BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT').split(',')]
    TIMEFRAME = os.getenv('TIMEFRAME', '4h')
    MAX_PORTFOLIO_EXPOSURE = float(os.getenv('MAX_PORTFOLIO_EXPOSURE', '0.30'))
    DAILY_LOSS_CAP = float(os.getenv('DAILY_LOSS_CAP', '0.03'))
    MAX_DRAWDOWN = float(os.getenv('MAX_DRAWDOWN', '0.08'))
    RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.01'))
    MIN_CONFIDENCE = int(os.getenv('MIN_CONFIDENCE', '65'))
    INITIAL_BALANCE = float(os.getenv('INITIAL_BALANCE', '10000'))

    CYCLE_HOURS = int(os.getenv('CYCLE_HOURS', '4'))
    BRIEFING_HOUR = int(os.getenv('BRIEFING_HOUR', '8'))

    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
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

# arena/config.py
from typing import Dict

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
TIMEFRAME = '4h'
MIN_CONFIDENCE = 65
RISK_PER_TRADE = 0.01
MAX_EXPOSURE = 0.30
DAILY_LOSS_CAP = 0.03
MAX_DRAWDOWN = 0.10
INITIAL_BALANCE = 10_000
MAX_POSITIONS = 5
POLL_INTERVAL = 60
ORDER_DIR = 'orders/'
TRAINING_EXPORT = 'orders/training_data.jsonl'
PERF_SUMMARY_CSV = 'orders/agent_performance_summary.csv'

AGENT_COLORS: Dict[str, str] = {
    'AJAY': '\033[91m',
    'VIJAY': '\033[92m',
    'SANJAY': '\033[93m',
    'RAMA': '\033[94m',
    'MEENAKSHI': '\033[95m',
    'RANI': '\033[96m',
}
RESET_COLOR = '\033[0m'
BOLD = '\033[1m'

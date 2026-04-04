# arena/config.py
from typing import Dict, List

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
TIMEFRAME = '4h'

TIMEFRAMES: List[Dict] = [
    {'tf': '1m',  'interval': 60,    'risk_mult': 0.15, 'max_pos': 2,  'candles': 200,  'label': 'Scalp'},
    {'tf': '5m',  'interval': 300,   'risk_mult': 0.30, 'max_pos': 3,  'candles': 200,  'label': 'Scalping'},
    {'tf': '15m', 'interval': 900,   'risk_mult': 0.50, 'max_pos': 3,  'candles': 200,  'label': 'Short-term'},
    {'tf': '30m', 'interval': 1800,  'risk_mult': 0.70, 'max_pos': 4,  'candles': 200,  'label': 'Intraday'},
    {'tf': '1h',  'interval': 3600,  'risk_mult': 0.85, 'max_pos': 4,  'candles': 200,  'label': 'Swing'},
    {'tf': '2h',  'interval': 7200,  'risk_mult': 1.00, 'max_pos': 5,  'candles': 200,  'label': 'Swing'},
    {'tf': '4h',  'interval': 14400, 'risk_mult': 1.20, 'max_pos': 5,  'candles': 100,  'label': 'Position'},
]

MIN_CONFIDENCE = 65
ML_MIN_PROB_WIN = 0.45
ML_REJECT_THRESHOLD = 0.30
ML_STRONG_REJECT = 0.35
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
ML_PREDICTIONS_LOG = 'logs/ml_predictions.jsonl'
WALK_FORWARD_WINDOW = 500
FEATURE_PRUNE_BOTTOM = 0.20

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


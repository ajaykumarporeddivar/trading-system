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
MAX_DRAWDOWN = 0.08
INITIAL_BALANCE = 10_000
MAX_POSITIONS = 5
POLL_INTERVAL = 60
ORDER_DIR = 'orders/'
TRAINING_EXPORT = 'orders/training_data.jsonl'
PERF_SUMMARY_CSV = 'orders/agent_performance_summary.csv'
ML_PREDICTIONS_LOG = 'logs/ml_predictions.jsonl'
WALK_FORWARD_WINDOW = 500
FEATURE_PRUNE_BOTTOM = 0.20

TF_SL_MULT: Dict[str, float] = {
    '1m': 0.20, '5m': 0.30, '15m': 0.40,
    '30m': 0.55, '1h': 0.70, '2h': 0.85, '4h': 1.00
}

TF_MAX_HOLD: Dict[str, int] = {
    '1m': 600,     # 10 minutes
    '5m': 1800,    # 30 minutes
    '15m': 3600,   # 1 hour
    '30m': 7200,   # 2 hours
    '1h': 14400,   # 4 hours
    '2h': 28800,   # 8 hours
    '4h': 57600    # 16 hours
}

TF_MAX_POSITIONS: Dict[str, int] = {
    '1m': 10,
    '5m': 8,
    '15m': 6,
    '30m': 5,
    '1h': 4,
    '2h': 3,
    '4h': 2
}

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


# arena/training_export.py
import json
import os
import csv
from typing import List, Dict, Any, Optional
from arena.config import TRAINING_EXPORT, PERF_SUMMARY_CSV
from arena.base_agent import BaseAgent
from core.logger import logger


CSV_FIELDS = [
    'agent', 'strategy', 'total_trades', 'wins', 'losses', 'win_rate',
    'total_pnl', 'avg_pnl', 'best_trade', 'worst_trade', 'virtual_capital'
]


def append_training_row(order: Dict[str, Any]):
    try:
        os.makedirs(os.path.dirname(TRAINING_EXPORT) if os.path.dirname(TRAINING_EXPORT) else '.', exist_ok=True)
        row = {
            'agent': order['agent'],
            'strategy': order['strategy'],
            'symbol': order['symbol'],
            'side': order['side'],
            'confidence': order['confidence'],
            'features': order.get('features', {}),
            'outcome': order['outcome'],
            'pnl_pct': order['pnl_pct'],
            'label': 1 if order['outcome'] == 'WIN' else 0,
            'timestamp': order['closed_at']
        }
        with open(TRAINING_EXPORT, 'a') as f:
            f.write(json.dumps(row) + '\n')
    except Exception as e:
        logger.error(f'Failed to append training row: {e}')


def export_performance_csv(agents: List[BaseAgent]):
    try:
        os.makedirs(os.path.dirname(PERF_SUMMARY_CSV) if os.path.dirname(PERF_SUMMARY_CSV) else '.', exist_ok=True)
        perf_data = [agent.get_performance() for agent in agents]

        with open(PERF_SUMMARY_CSV, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
            writer.writeheader()
            for perf in perf_data:
                writer.writerow(perf)

        logger.info(f'Performance CSV exported to {PERF_SUMMARY_CSV}')
    except Exception as e:
        logger.error(f'Failed to export performance CSV: {e}')


def load_training_data() -> List[Dict[str, Any]]:
    try:
        if not os.path.exists(TRAINING_EXPORT):
            return []
        rows = []
        with open(TRAINING_EXPORT, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows
    except Exception as e:
        logger.error(f'Failed to load training data: {e}')
        return []


def get_winner() -> Optional[Dict[str, Any]]:
    try:
        if not os.path.exists(PERF_SUMMARY_CSV):
            return None

        with open(PERF_SUMMARY_CSV, 'r') as f:
            reader = csv.DictReader(f)
            agents = list(reader)

        qualified = [a for a in agents if int(a.get('total_trades', 0)) >= 10]
        if not qualified:
            return None

        winner = max(qualified, key=lambda x: float(x.get('win_rate', 0)))
        return winner
    except Exception as e:
        logger.error(f'Failed to determine winner: {e}')
        return None

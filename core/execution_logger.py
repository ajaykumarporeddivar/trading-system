# core/execution_logger.py
import json
import os
import time
from typing import Dict, Any, Optional
from datetime import datetime
from core.logger import logger

EXECUTION_LOG = 'logs/execution_log.jsonl'
SIGNAL_TIMES: Dict[str, float] = {}


class ExecutionLogger:
    def __init__(self):
        self._slippage_history: Dict[str, list] = {}
        self._latency_history: list = []

    def log_signal_time(self, order_id: str):
        SIGNAL_TIMES[order_id] = time.time()

    def log_fill(self, order_id: str, symbol: str, side: str, entry_price: float,
               quantity: float, spread: float = 0, market_impact: float = 0,
               adv_ratio: float = 0) -> Dict[str, Any]:
        signal_time = SIGNAL_TIMES.pop(order_id, None)
        latency_ms = (time.time() - signal_time) * 1000 if signal_time else 0

        est_slippage = self._estimate_slippage(quantity, spread, adv_ratio)

        record = {
            'order_id': order_id,
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'quantity': quantity,
            'spread': round(spread, 8),
            'est_slippage': round(est_slippage, 8),
            'market_impact': round(market_impact, 8),
            'adv_ratio': round(adv_ratio, 4),
            'latency_ms': round(latency_ms, 2),
            'timestamp': datetime.now().isoformat()
        }

        self._latency_history.append(latency_ms)
        if len(self._latency_history) > 500:
            self._latency_history = self._latency_history[-500:]

        if symbol not in self._slippage_history:
            self._slippage_history[symbol] = []
        self._slippage_history[symbol].append(est_slippage)
        if len(self._slippage_history[symbol]) > 500:
            self._slippage_history[symbol] = self._slippage_history[symbol][-500:]

        self._log_record(record)
        logger.debug(f'Fill: {side} {symbol} @ {entry_price} | slippage={est_slippage:.2f} | latency={latency_ms:.0f}ms')
        return record

    def log_close(self, order_id: str, symbol: str, exit_price: float,
                  entry_price: float, pnl: float, spread: float = 0,
                  market_impact: float = 0) -> Dict[str, Any]:
        avg_slippage = self._get_avg_slippage(symbol)
        realized_slippage = abs(exit_price - entry_price) * 0.001 + spread * 0.5

        record = {
            'order_id': order_id,
            'symbol': symbol,
            'exit_price': exit_price,
            'entry_price': entry_price,
            'gross_pnl': pnl,
            'net_pnl': round(pnl - realized_slippage - market_impact, 2),
            'realized_slippage': round(realized_slippage, 8),
            'avg_slippage': round(avg_slippage, 8),
            'slippage_vs_estimate': round(realized_slippage - avg_slippage, 8) if avg_slippage else 0,
            'market_impact': round(market_impact, 8),
            'timestamp': datetime.now().isoformat()
        }

        self._log_record(record)
        return record

    def check_latency_guardrail(self, threshold_ms: float = 5000) -> bool:
        if not self._latency_history:
            return True
        recent = self._latency_history[-50:]
        avg_latency = sum(recent) / len(recent)
        if avg_latency > threshold_ms:
            logger.warning(f'Latency guardrail breached: avg={avg_latency:.0f}ms > {threshold_ms}ms')
            return False
        return True

    def get_execution_stats(self) -> Dict[str, Any]:
        if not self._latency_history:
            return {'status': 'no_data'}

        import numpy as np
        latencies = np.array(self._latency_history[-100:])
        return {
            'avg_latency_ms': round(float(np.mean(latencies)), 2),
            'p50_latency_ms': round(float(np.median(latencies)), 2),
            'p95_latency_ms': round(float(np.percentile(latencies, 95)), 2),
            'p99_latency_ms': round(float(np.percentile(latencies, 99)), 2),
            'total_fills': len(self._latency_history),
            'slippage_by_symbol': {
                sym: round(float(np.mean(slips)), 8)
                for sym, slips in self._slippage_history.items()
                if slips
            },
            'timestamp': datetime.now().isoformat()
        }

    def _estimate_slippage(self, quantity: float, spread: float, adv_ratio: float) -> float:
        if adv_ratio > 0.01:
            return quantity * 0.0001 * adv_ratio
        return spread * 0.5

    def _get_avg_slippage(self, symbol: str) -> float:
        if symbol not in self._slippage_history or not self._slippage_history[symbol]:
            return 0
        import numpy as np
        return float(np.mean(self._slippage_history[symbol]))

    def _log_record(self, record: Dict[str, Any]):
        try:
            os.makedirs('logs', exist_ok=True)
            with open(EXECUTION_LOG, 'a') as f:
                f.write(json.dumps(record) + '\n')
        except Exception as e:
            logger.error(f'Failed to log execution: {e}')

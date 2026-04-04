# ml/retrain_scheduler.py
import time
import json
import os
import numpy as np
import threading
from datetime import datetime, timedelta
from typing import Callable, Optional

from ml.strategy_updater import StrategyUpdater
from ml.trainer import load_training_data, load_model, predict_signal
from ml.model_registry import ModelRegistry
from core.logger import logger

ML_PREDICTIONS_LOG = 'logs/ml_predictions.jsonl'
STABILITY_LOG = 'logs/stability_contract.jsonl'

STABILITY_MIN_SAMPLES = 500
STABILITY_MAX_REGIME_PCT = 0.40
STABILITY_RECENCY_PCT = 0.60
STABILITY_VARIANCE_FLOOR = 0.80
STABILITY_DRIFT_INTERVAL = 3600
STABILITY_MISSING_THRESHOLD = 0.01


class RetrainScheduler:
    def __init__(self, check_interval: int = 3600, min_samples: int = 50):
        self.check_interval = check_interval
        self.min_samples = min_samples
        self.updater = StrategyUpdater()
        self.registry = ModelRegistry()
        self.running = False
        self.thread = None
        self._last_retrain_count = 0
        self._last_force_retrain = 0
        self._force_retrain_cooldown = 300

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        logger.info(f'Retrain scheduler started (check every {self.check_interval}s)')

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=10)
        logger.info('Retrain scheduler stopped')

    def _loop(self):
        while self.running:
            try:
                live_accuracy = self._check_live_ml_accuracy()
                if live_accuracy is not None:
                    logger.info(f'Live ML accuracy: {live_accuracy:.1%}')
                    if live_accuracy < 0.45 and (time.time() - self._last_force_retrain) > self._force_retrain_cooldown:
                        logger.warning('Live accuracy degraded, forcing retrain')
                        self._last_force_retrain = time.time()
                        self.force_retrain()
                        continue

                contract_ok, reasons = self._check_stability_contract()
                if not contract_ok:
                    logger.debug(f'Stability Contract NOT met: {reasons}')
                    time.sleep(self.check_interval)
                    continue

                if self.updater.should_retrain(self.min_samples):
                    logger.info('Stability Contract met — Auto-retraining ML model...')
                    success = self.updater.retrain_and_update(self.min_samples)
                    if success:
                        logger.info('ML model retrained successfully')
                        metrics = self.updater.adjustments
                        if metrics.get('model_accuracy'):
                            self.registry.register_champion(
                                'ml/models/trading_model.pkl',
                                {'accuracy': metrics['model_accuracy'], 'model_type': 'auto', 'total_retrains': metrics.get('total_retrains', 0)}
                            )
                    else:
                        logger.warning('ML retraining failed')
                else:
                    logger.debug('Not enough new data for retraining')
            except Exception as e:
                logger.error(f'Retrain scheduler error: {e}', exc_info=True)

            time.sleep(self.check_interval)

    def _check_stability_contract(self) -> tuple:
        rows = load_training_data()
        reasons = []

        new_since_last = len(rows) - self._last_retrain_count
        if new_since_last < STABILITY_MIN_SAMPLES:
            reasons.append(f'insufficient_samples: {new_since_last} < {STABILITY_MIN_SAMPLES}')

        regime_counts = {}
        for row in rows[-200:]:
            regime = row.get('regime_at_entry', 'unknown')
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        total_recent = sum(regime_counts.values())
        if total_recent > 0:
            for regime, count in regime_counts.items():
                pct = count / total_recent
                if pct > STABILITY_MAX_REGIME_PCT:
                    reasons.append(f'regime_imbalance: {regime}={pct:.0%} > {STABILITY_MAX_REGIME_PCT:.0%}')

        now = datetime.now()
        ninety_days_ago = now - timedelta(days=90)
        recent_rows = sum(1 for r in rows if datetime.fromisoformat(r.get('timestamp', '2000-01-01')) > ninety_days_ago)
        if len(rows) > 0:
            recency_pct = recent_rows / len(rows)
            if recency_pct < STABILITY_RECENCY_PCT:
                reasons.append(f'recency: {recency_pct:.0%} < {STABILITY_RECENCY_PCT:.0%}')

        if len(rows) >= 100:
            recent_pnls = [r.get('pnl_pct', 0) for r in rows[-100:]]
            older_pnls = [r.get('pnl_pct', 0) for r in rows[-500:-100]] if len(rows) >= 500 else recent_pnls
            recent_var = np.var(recent_pnls) if recent_pnls else 0
            older_var = np.var(older_pnls) if older_pnls else 1
            if older_var > 0 and recent_var / older_var < STABILITY_VARIANCE_FLOOR:
                reasons.append(f'variance_floor: {recent_var/older_var:.2f} < {STABILITY_VARIANCE_FLOOR}')

        missing = sum(1 for r in rows[-200:] if not r.get('features') or not r.get('label'))
        if len(rows) > 0:
            missing_pct = missing / min(200, len(rows))
            if missing_pct > STABILITY_MISSING_THRESHOLD:
                reasons.append(f'data_quality: {missing_pct:.1%} missing > {STABILITY_MISSING_THRESHOLD:.1%}')

        if not reasons:
            self._last_retrain_count = len(rows)
            return True, []

        self._log_contract_check(False, reasons)
        return False, reasons

    def _log_contract_check(self, passed: bool, reasons: list):
        try:
            os.makedirs('logs', exist_ok=True)
            entry = {
                'passed': passed,
                'reasons': reasons,
                'timestamp': datetime.now().isoformat()
            }
            with open(STABILITY_LOG, 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception:
            pass

    def _check_live_ml_accuracy(self) -> Optional[float]:
        if not os.path.exists(ML_PREDICTIONS_LOG):
            return None
        predictions = []
        with open(ML_PREDICTIONS_LOG, 'r') as f:
            for line in f:
                if line.strip():
                    predictions.append(json.loads(line))
        if len(predictions) < 20:
            return None

        orders_dir = 'orders/'
        if not os.path.exists(orders_dir):
            return None

        closed_trades = {}
        for fname in os.listdir(orders_dir):
            if not fname.endswith('_orders.json'):
                continue
            with open(os.path.join(orders_dir, fname), 'r') as f:
                data = json.load(f)
            for oid, trade in data.get('closed_positions', {}).items():
                if trade.get('outcome'):
                    closed_trades[(trade.get('agent'), trade.get('symbol'), trade.get('opened_at'))] = trade.get('outcome')

        if not closed_trades:
            return None

        correct = 0
        total = 0
        for pred in predictions[-100:]:
            key = (pred['agent'], pred['symbol'])
            for trade_key, outcome in closed_trades.items():
                if trade_key[0] == key[0] and trade_key[1] == key[1]:
                    total += 1
                    if (pred['prediction'] == 1 and outcome == 'WIN') or (pred['prediction'] == 0 and outcome == 'LOSS'):
                        correct += 1
                    break

        return correct / total if total > 0 else None

    def force_retrain(self):
        logger.info('Forcing ML retrain...')
        result = self.updater.retrain_and_update(self.min_samples)
        if result:
            self._last_retrain_count = len(load_training_data())
        return result

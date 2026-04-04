# ml/retrain_scheduler.py
import time
import threading
from datetime import datetime
from typing import Callable, Optional

from ml.strategy_updater import StrategyUpdater
from core.logger import logger


class RetrainScheduler:
    def __init__(self, check_interval: int = 3600, min_samples: int = 50):
        self.check_interval = check_interval
        self.min_samples = min_samples
        self.updater = StrategyUpdater()
        self.running = False
        self.thread = None

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
                if self.updater.should_retrain(self.min_samples):
                    logger.info('Auto-retraining ML model...')
                    success = self.updater.retrain_and_update(self.min_samples)
                    if success:
                        logger.info('ML model retrained successfully')
                    else:
                        logger.warning('ML retraining failed')
                else:
                    logger.debug('Not enough new data for retraining')
            except Exception as e:
                logger.error(f'Retrain scheduler error: {e}', exc_info=True)

            time.sleep(self.check_interval)

    def force_retrain(self):
        logger.info('Forcing ML retrain...')
        return self.updater.retrain_and_update(self.min_samples)

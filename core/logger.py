import logging
import os
import sys
from core.config import Config

def setup_logger(name: str = 'trading_system') -> logging.Logger:
    logger = logging.getLogger(name)

    valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
    log_level = Config.LOG_LEVEL.upper() if Config.LOG_LEVEL.upper() in valid_levels else 'INFO'
    logger.setLevel(getattr(logging, log_level))

    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        log_dir = os.path.dirname(Config.LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler(Config.LOG_FILE)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

logger = setup_logger()

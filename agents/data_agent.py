import ccxt
import pandas as pd
import numpy as np
from typing import Dict, List, Any
from core.config import Config
from core.logger import logger
from engine.indicators import TechnicalIndicators

class DataAgent:
    def __init__(self):
        self.exchange = getattr(ccxt, Config.EXCHANGE)({
            'apiKey': Config.EXCHANGE_API_KEY,
            'secret': Config.EXCHANGE_API_SECRET,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        if Config.USE_TESTNET:
            if Config.EXCHANGE == 'binance':
                self.exchange.set_sandbox_mode(True)
        self.indicators = TechnicalIndicators()
        logger.info(f'Data Agent initialized - {Config.EXCHANGE} ({'testnet' if Config.USE_TESTNET else 'live'})')

    async def fetch_ohlcv(self, symbol: str, timeframe: str = Config.TIMEFRAME, limit: int = 100) -> pd.DataFrame:
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            logger.info(f'Fetched {len(df)} candles for {symbol}')
            return df
        except Exception as e:
            logger.error(f'Failed to fetch OHLCV for {symbol}: {e}')
            return pd.DataFrame()

    async def compute_indicators(self, symbol: str) -> Dict[str, Any]:
        df = await self.fetch_ohlcv(symbol)
        if df.empty:
            return {}

        indicator_data = self.indicators.compute_all(df)
        indicator_data['symbol'] = symbol
        indicator_data['timestamp'] = pd.Timestamp.now().isoformat()
        return indicator_data

    async def get_all_indicators(self, symbols: List[str] = Config.TRADING_SYMBOLS) -> Dict[str, Dict[str, Any]]:
        results = {}
        for symbol in symbols:
            data = await self.compute_indicators(symbol)
            if data:
                results[symbol] = data
        logger.info(f'Indicators computed for {len(results)} symbols')
        return results

    async def get_market_overview(self) -> Dict[str, Any]:
        tickers = {}
        for symbol in Config.TRADING_SYMBOLS:
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                tickers[symbol] = {
                    'price': ticker['last'],
                    'change_24h': ticker.get('percentage', 0),
                    'volume_24h': ticker.get('baseVolume', 0),
                    'high_24h': ticker.get('high', 0),
                    'low_24h': ticker.get('low', 0)
                }
            except Exception as e:
                logger.error(f'Failed to fetch ticker for {symbol}: {e}')
        return tickers

    async def get_balance(self) -> Dict[str, Any]:
        try:
            balance = self.exchange.fetch_balance()
            usdt = balance.get('USDT', {'free': 0, 'total': 0})
            return {
                'free': usdt['free'],
                'total': usdt['total'],
                'used': usdt['total'] - usdt['free']
            }
        except Exception as e:
            logger.error(f'Failed to fetch balance: {e}')
            return {'free': 0, 'total': 0, 'used': 0}

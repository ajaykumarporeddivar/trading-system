import ccxt
import pandas as pd
from typing import Dict, List, Any, Optional
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

        self.live_exchange = getattr(ccxt, Config.EXCHANGE)({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        self._fallback_active = False
        self.indicators = TechnicalIndicators()
        env_label = 'testnet' if Config.USE_TESTNET else 'live'
        logger.info(f'Data Agent initialized - {Config.EXCHANGE} ({env_label}) with live fallback')

    async def fetch_ohlcv(self, symbol: str, timeframe: str = Config.TIMEFRAME, limit: int = 100) -> pd.DataFrame:
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            if self._fallback_active:
                logger.info(f'Testnet recovered, using primary exchange')
                self._fallback_active = False
            logger.debug(f'Fetched {len(df)} {timeframe} candles for {symbol}')
            return df
        except Exception as e:
            error_str = str(e)
            if '451' in error_str or 'restricted location' in error_str.lower():
                if not self._fallback_active:
                    logger.warning(f'Testnet geo-blocked (451), falling back to live {Config.EXCHANGE} public API')
                    self._fallback_active = True
                try:
                    ohlcv = self.live_exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                    logger.debug(f'Fetched {len(df)} {timeframe} candles for {symbol} (live fallback)')
                    return df
                except Exception as e2:
                    logger.error(f'Live fallback also failed for {symbol} {timeframe}: {e2}')
                    return pd.DataFrame()
            else:
                logger.error(f'Failed to fetch OHLCV for {symbol} {timeframe}: {e}')
                return pd.DataFrame()

    async def compute_indicators_for_tf(self, symbol: str, timeframe: str, limit: int = 100) -> Dict[str, Any]:
        df = await self.fetch_ohlcv(symbol, timeframe, limit)
        if df.empty:
            return {}
        indicator_data = self.indicators.compute_all(df)
        indicator_data['symbol'] = symbol
        indicator_data['timeframe'] = timeframe
        indicator_data['timestamp'] = pd.Timestamp.now().isoformat()
        return indicator_data

    async def compute_indicators(self, symbol: str, timeframe: str = None) -> Dict[str, Any]:
        tf = timeframe or Config.TIMEFRAME
        return await self.compute_indicators_for_tf(symbol, tf)

    async def get_all_indicators(self, symbols: List[str] = Config.TRADING_SYMBOLS, timeframe: str = None) -> Dict[str, Dict[str, Any]]:
        tf = timeframe or Config.TIMEFRAME
        results = {}
        for symbol in symbols:
            data = await self.compute_indicators_for_tf(symbol, tf)
            if data:
                results[symbol] = data
        logger.debug(f'Indicators computed for {len(results)} symbols @ {tf}')
        return results

    async def get_multi_tf_indicators(self, symbols: List[str], timeframes: List[str]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        results = {}
        for symbol in symbols:
            results[symbol] = {}
            for tf in timeframes:
                data = await self.compute_indicators_for_tf(symbol, tf)
                if data:
                    results[symbol][tf] = data
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

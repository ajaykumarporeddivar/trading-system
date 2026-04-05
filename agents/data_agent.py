import ccxt
import yfinance as yf
import pandas as pd
from typing import Dict, List, Any, Optional
from core.config import Config
from core.logger import logger
from engine.indicators import TechnicalIndicators

SYMBOL_TO_YF = {
    'BTC/USDT': 'BTC-USD',
    'ETH/USDT': 'ETH-USD',
    'SOL/USDT': 'SOL-USD',
    'BNB/USDT': 'BNB-USD',
    'XRP/USDT': 'XRP-USD',
}

TF_TO_YF = {
    '1m': '1m',
    '5m': '5m',
    '15m': '15m',
    '30m': '30m',
    '1h': '1h',
    '2h': '2h',
    '4h': '1d',
    '1d': '1d',
}

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

        self.fallback_exchanges = [
            ('bybit', ccxt.bybit({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})),
            ('gate', ccxt.gate({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})),
            ('okx', ccxt.okx({'enableRateLimit': True})),
            ('kucoin', ccxt.kucoin({'enableRateLimit': True, 'options': {'defaultType': 'spot'}})),
        ]
        self._fallback_level = 0
        self._yfinance_warned = False
        self.indicators = TechnicalIndicators()
        env_label = 'testnet' if Config.USE_TESTNET else 'live'
        logger.info(f'Data Agent initialized - {Config.EXCHANGE} ({env_label}) with 4 exchange + yfinance fallback')

    def _is_geo_blocked(self, error_str: str) -> bool:
        return any(x in error_str for x in ['451', '403', 'restricted location', 'cloudfront', 'blocked'])

    def _fetch_yfinance_ohlcv(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        yf_symbol = SYMBOL_TO_YF.get(symbol)
        yf_interval = TF_TO_YF.get(timeframe, '1h')
        if not yf_symbol:
            return pd.DataFrame()
        try:
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period=f'{min(limit * 2, 730)}d', interval=yf_interval)
            if df.empty:
                return pd.DataFrame()
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            if 'date' in df.columns:
                df = df.rename(columns={'date': 'timestamp'})
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].tail(limit)
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            if not self._yfinance_warned:
                logger.warning('Using yfinance for market data (all exchanges blocked)')
                self._yfinance_warned = True
            return df
        except Exception as e:
            logger.error(f'yfinance failed for {symbol} {timeframe}: {e}')
            return pd.DataFrame()

    async def fetch_ohlcv(self, symbol: str, timeframe: str = Config.TIMEFRAME, limit: int = 100) -> pd.DataFrame:
        exchanges = [
            (self.exchange, 'primary'),
            (self.live_exchange, 'binance_live'),
        ] + [(ex, name) for name, ex in self.fallback_exchanges]

        for i, (ex, label) in enumerate(exchanges):
            try:
                ohlcv = ex.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                if i > self._fallback_level:
                    self._fallback_level = i
                    logger.warning(f'Using {label} exchange for market data (level {i})')
                elif i < self._fallback_level:
                    self._fallback_level = i
                    logger.info(f'Recovered to {label} exchange (level {i})')
                logger.debug(f'Fetched {len(df)} {timeframe} candles for {symbol} ({label})')
                return df
            except Exception as e:
                error_str = str(e)
                if self._is_geo_blocked(error_str):
                    logger.warning(f'{label} blocked for {symbol} {timeframe}, trying next...')
                    continue
                logger.error(f'Failed to fetch OHLCV for {symbol} {timeframe} ({label}): {e}')
                if i < len(exchanges) - 1:
                    continue

        logger.warning(f'All exchanges blocked for {symbol} {timeframe}, using yfinance fallback')
        return self._fetch_yfinance_ohlcv(symbol, timeframe, limit)

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

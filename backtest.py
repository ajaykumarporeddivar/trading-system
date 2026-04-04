# backtest.py
import sys
import os
import json
import asyncio
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import ccxt
import pandas as pd
from agents.data_agent import DataAgent
from arena.config import SYMBOLS, ORDER_DIR, MIN_CONFIDENCE
from arena.agents.ajay import AjayAgent
from arena.agents.vijay import VijayAgent
from arena.agents.sanjay import SanjayAgent
from arena.agents.rama import RamaAgent
from arena.agents.meenakshi import MeenakshiAgent
from arena.agents.rani import RaniAgent
from arena.leaderboard import print_leaderboard
from arena.training_export import export_performance_csv, load_training_data, get_winner
from engine.indicators import TechnicalIndicators
from core.logger import logger


def fetch_historical_candles(symbol, limit=500):
    exchange = ccxt.binance({'enableRateLimit': True})
    all_candles = []
    since = None
    while len(all_candles) < limit:
        ohlcv = exchange.fetch_ohlcv(symbol, '4h', since=since, limit=min(500, limit - len(all_candles)))
        if not ohlcv:
            break
        all_candles.extend(ohlcv)
        since = ohlcv[-1][0] + 1
        if len(ohlcv) < 500:
            break
    df = pd.DataFrame(all_candles[:limit], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df


class BacktestSimulator:
    def __init__(self, agents, candles_per_symbol: dict):
        self.agents = agents
        self.candles_per_symbol = candles_per_symbol
        self.cycle_count = 0
        self._build_timeline()

    def _build_timeline(self):
        timestamps = set()
        for symbol, candles in self.candles_per_symbol.items():
            for c in candles:
                timestamps.add(c['timestamp'])
        self.timeline = sorted(list(timestamps))
        logger.info(f'Backtest timeline: {len(self.timeline)} candles from {self.timeline[0]} to {self.timeline[-1]}')

    def _get_indicators_at(self, symbol, candle_index):
        candles = self.candles_per_symbol.get(symbol, [])
        if candle_index < 50:
            return None
        historical = candles[:candle_index + 1]
        import pandas as pd
        df = pd.DataFrame(historical)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return TechnicalIndicators.compute_all(df)

    def run(self):
        logger.info('=== BACKTEST START ===')
        closed_trades = 0
        current_prices = {}

        for idx, ts in enumerate(self.timeline):
            self.cycle_count += 1
            current_prices = {}
            market_data = {}

            for symbol in SYMBOLS:
                indicators = self._get_indicators_at(symbol, idx)
                if indicators is None:
                    continue
                candles = self.candles_per_symbol.get(symbol, [])
                if idx >= len(candles):
                    continue
                current_candle = candles[idx]
                price = current_candle['close']
                current_prices[symbol] = price

                prev_idx = idx - 1
                if prev_idx >= 0 and prev_idx < len(candles):
                    prev_price = candles[prev_idx]['close']
                    change_pct = ((price - prev_price) / prev_price * 100) if prev_price else 0
                else:
                    change_pct = 0

                market_data[symbol] = {
                    'symbol': symbol,
                    'price': price,
                    'change_pct': change_pct,
                    'indicators': indicators
                }

            for agent in self.agents:
                if not agent.check_risk_limits():
                    continue
                agent.check_exits(current_prices)

                for symbol, data in market_data.items():
                    signal = agent.generate_signal(data)
                    if signal and signal.get('confidence', 0) >= MIN_CONFIDENCE:
                        agent.submit_paper_order(signal, data['price'])

            if self.cycle_count % 100 == 0:
                total_closed = sum(len(a.closed_positions) for a in self.agents)
                total_open = sum(len(a.open_positions) for a in self.agents)
                logger.info(f'Cycle {self.cycle_count}/{len(self.timeline)}: {total_open} open, {total_closed} closed')

        for agent in self.agents:
            for order_id in list(agent.open_positions.keys()):
                last_price = current_prices.get(agent.open_positions[order_id]['symbol'])
                if last_price:
                    agent.close_position(order_id, last_price, 'backtest_end')
                    closed_trades += 1

        logger.info(f'=== BACKTEST END ===')
        logger.info(f'Total cycles: {self.cycle_count}')
        logger.info(f'Total closed trades: {closed_trades}')

        print('\n' + '=' * 80)
        print('BACKTEST RESULTS')
        print('=' * 80)
        print_leaderboard(self.agents, 'BACKTEST')
        export_performance_csv(self.agents)

        training_rows = load_training_data()
        logger.info(f'Training data generated: {len(training_rows)} rows')

        winner = get_winner()
        if winner:
            print(f'\nWinner: {winner["agent"]} ({winner["strategy"]})')
            print(f'  Win Rate: {winner["win_rate"]}%')
            print(f'  Total PnL: ')
            print(f'  Trades: {winner["total_trades"]}')
        else:
            print('\nNo winner yet - need 10+ trades per agent to qualify')

        print(f'\nBacktest complete. Training data: {len(training_rows)} rows')
        return training_rows


def main():
    print('''
    +====================================+
    |   CRYPTO AGENT BACKTEST SIMULATOR  |
    |   6 Agents  |  Historical Data     |
    |   BTC ETH SOL BNB XRP  |  4h      |
    +====================================+
    ''')

    os.makedirs(ORDER_DIR, exist_ok=True)

    logger.info('Fetching historical data from Binance (public API, no keys needed)...')

    candles_per_symbol = {}
    for symbol in SYMBOLS:
        logger.info(f'Fetching 500 candles for {symbol}...')
        df = fetch_historical_candles(symbol, limit=500)
        if not df.empty:
            candles = []
            for _, row in df.iterrows():
                candles.append({
                    'timestamp': row['timestamp'].isoformat(),
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': float(row['volume'])
                })
            candles_per_symbol[symbol] = candles
            logger.info(f'  {symbol}: {len(candles)} candles loaded ({df["timestamp"].iloc[0]} to {df["timestamp"].iloc[-1]})')

    if not candles_per_symbol:
        logger.error('No historical data fetched. Exiting.')
        return

    agents = [
        AjayAgent(f'{ORDER_DIR}ajay_orders.json'),
        VijayAgent(f'{ORDER_DIR}vijay_orders.json'),
        SanjayAgent(f'{ORDER_DIR}sanjay_orders.json'),
        RamaAgent(f'{ORDER_DIR}rama_orders.json'),
        MeenakshiAgent(f'{ORDER_DIR}meenakshi_orders.json'),
        RaniAgent(f'{ORDER_DIR}rani_orders.json'),
    ]

    sim = BacktestSimulator(agents, candles_per_symbol)
    sim.run()


if __name__ == '__main__':
    main()

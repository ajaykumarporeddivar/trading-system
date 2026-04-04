import aiosqlite
import datetime
from core.config import Config
from core.logger import logger

class TradingJournal:
    def __init__(self, db_path: str = Config.DATABASE_PATH):
        self.db_path = db_path

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    quantity REAL NOT NULL,
                    stop_loss REAL,
                    take_profit REAL,
                    exit_price REAL,
                    pnl REAL DEFAULT 0,
                    r_ratio REAL,
                    status TEXT DEFAULT 'open',
                    agent_verdict TEXT,
                    confidence INTEGER,
                    order_id TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    confidence INTEGER NOT NULL,
                    indicator_scores TEXT
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS daily_pnl (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL UNIQUE,
                    starting_balance REAL,
                    ending_balance REAL,
                    daily_pnl REAL DEFAULT 0,
                    trades_count INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0
                )
            ''')
            await db.commit()
        logger.info('Database initialized')

    async def log_trade(self, trade_data: dict):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO trades (timestamp, symbol, side, entry_price, quantity,
                                   stop_loss, take_profit, exit_price, pnl, r_ratio,
                                   status, agent_verdict, confidence, order_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                trade_data.get('timestamp', datetime.datetime.now().isoformat()),
                trade_data['symbol'],
                trade_data['side'],
                trade_data['entry_price'],
                trade_data['quantity'],
                trade_data.get('stop_loss'),
                trade_data.get('take_profit'),
                trade_data.get('exit_price'),
                trade_data.get('pnl', 0),
                trade_data.get('r_ratio'),
                trade_data.get('status', 'open'),
                trade_data.get('agent_verdict'),
                trade_data.get('confidence'),
                trade_data.get('order_id')
            ))
            await db.commit()
        logger.info(f'Trade logged: {trade_data["symbol"]} {trade_data["side"]} @{trade_data["entry_price"]}')

    async def log_signal(self, signal_data: dict):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO signals (timestamp, symbol, verdict, confidence, indicator_scores)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                signal_data.get('timestamp', datetime.datetime.now().isoformat()),
                signal_data['symbol'],
                signal_data['verdict'],
                signal_data['confidence'],
                str(signal_data.get('indicator_scores', {}))
            ))
            await db.commit()

    async def get_open_positions(self) -> list:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM trades WHERE status = ?', ('open',)) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    async def get_daily_pnl(self, date: str = None) -> dict:
        target_date = date or datetime.date.today().isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('SELECT * FROM daily_pnl WHERE date = ?', (target_date,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_daily_pnl(self, date: str, pnl_data: dict):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO daily_pnl (date, starting_balance, ending_balance, daily_pnl, trades_count, wins, losses)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                date,
                pnl_data.get('starting_balance'),
                pnl_data.get('ending_balance'),
                pnl_data.get('daily_pnl', 0),
                pnl_data.get('trades_count', 0),
                pnl_data.get('wins', 0),
                pnl_data.get('losses', 0)
            ))
            await db.commit()

    async def get_performance_stats(self) -> dict:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute('''
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as best_trade,
                    MIN(pnl) as worst_trade
                FROM trades WHERE status = 'closed'
            ''') as cursor:
                row = await cursor.fetchone()
                if row:
                    stats = dict(row)
                    stats['win_rate'] = (stats['wins'] / stats['total_trades'] * 100) if stats['total_trades'] > 0 else 0
                    return stats
                return {'total_trades': 0, 'wins': 0, 'losses': 0, 'total_pnl': 0, 'win_rate': 0}

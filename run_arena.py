# run_arena.py
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from arena.config import ORDER_DIR, AGENT_COLORS, RESET_COLOR
from arena.base_agent import BaseAgent
from arena.arena_runner import ArenaRunner
from arena.agents.ajay import AjayAgent
from arena.agents.vijay import VijayAgent
from arena.agents.sanjay import SanjayAgent
from arena.agents.rama import RamaAgent
from arena.agents.meenakshi import MeenakshiAgent
from arena.agents.rani import RaniAgent
from arena.leaderboard import print_leaderboard
from arena.training_export import export_performance_csv, load_training_data, get_winner
from core.logger import logger


def print_banner():
    banner = '''
    +====================================+
    |   CRYPTO AGENT TRADING ARENA       |
    |   6 Agents  |   Real Money       |
    |   BTC ETH SOL BNB XRP  |  4h      |
    +====================================+
    '''
    print(banner)


def main():
    print_banner()

    os.makedirs(ORDER_DIR, exist_ok=True)

    agents = [
        AjayAgent(order_db_path=f'{ORDER_DIR}ajay_orders.json'),
        VijayAgent(order_db_path=f'{ORDER_DIR}vijay_orders.json'),
        SanjayAgent(order_db_path=f'{ORDER_DIR}sanjay_orders.json'),
        RamaAgent(order_db_path=f'{ORDER_DIR}rama_orders.json'),
        MeenakshiAgent(order_db_path=f'{ORDER_DIR}meenakshi_orders.json'),
        RaniAgent(order_db_path=f'{ORDER_DIR}rani_orders.json'),
    ]

    logger.info(f'Starting arena with {len(agents)} agents')

    runner = ArenaRunner(agents)

    try:
        runner.run()
    except KeyboardInterrupt:
        print('\nArena stopped.')
        print_final_results(agents)


def print_final_results(agents):
    print('\n' + '=' * 60)
    print('FINAL RESULTS')
    print('=' * 60)

    print_leaderboard(agents, 'FINAL')

    export_performance_csv(agents)

    training_rows = load_training_data()
    print(f'Training data saved: {len(training_rows)} rows in orders/training_data.jsonl')

    winner = get_winner()
    if winner:
        print(f'\nWinner: {winner["agent"]} ({winner["strategy"]})')
        print(f'  Win Rate: {winner["win_rate"]}%')
        print(f'  Total PnL: ')
        print(f'  Trades: {winner["total_trades"]}')
    else:
        print('\nNo winner yet - need 10+ trades per agent to qualify')

    print(f'\nArena stopped. Training data saved to orders/training_data.jsonl')


if __name__ == '__main__':
    main()

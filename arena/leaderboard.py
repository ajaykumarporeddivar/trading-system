# arena/leaderboard.py
from typing import List, Dict, Any
from datetime import datetime
from arena.base_agent import BaseAgent
from arena.config import AGENT_COLORS, RESET_COLOR, BOLD


def print_leaderboard(agents: List[BaseAgent], cycle_count: int | str):
    perf_data = [agent.get_performance() for agent in agents]
    perf_data.sort(key=lambda x: x['total_pnl'], reverse=True)

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    width = 80

    print()
    print('=' * width)
    print(f'{"AGENT ARENA LEADERBOARD":^{width}}')
    print(f'{"Cycle #" + str(cycle_count) + "  |  " + now:^{width}}')
    print('-' * width)
    print(f'{"Rank":>5} {"Agent":<12} {"Trades":>8} {"Win %":>8} {"Total PnL":>12} {"Capital":>12} {"Status":>10}')
    print('-' * width)

    for i, perf in enumerate(perf_data):
        rank = i + 1
        agent_name = perf['agent']
        color = AGENT_COLORS.get(agent_name, '')
        status = 'OK'

        if rank == 1:
            rank_str = f'{BOLD} #1{RESET_COLOR}'
        else:
            rank_str = f' #{rank}'

        pnl_str = f'{perf["total_pnl"]:+,.0f}'
        capital_str = f'{perf["virtual_capital"]:,.0f}'
        win_rate_str = f'{perf["win_rate"]:.1f}%' if perf['total_trades'] > 0 else 'N/A'

        row = f'{rank_str} {color}{agent_name:<12}{RESET_COLOR} {perf["total_trades"]:>8} {win_rate_str:>8} {pnl_str:>12} {capital_str:>12} {status:>10}'
        print(row)

    print('-' * width)
    open_pos = ' '.join(f'{a.name}({len(a.open_positions)})' for a in agents)
    print(f'Open positions: {open_pos}')
    print('=' * width)
    print()


def get_leaderboard_data(agents: List[BaseAgent]) -> List[Dict[str, Any]]:
    perf_data = [agent.get_performance() for agent in agents]
    perf_data.sort(key=lambda x: x['total_pnl'], reverse=True)
    return perf_data

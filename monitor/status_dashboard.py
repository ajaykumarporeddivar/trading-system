# monitor/status_dashboard.py
import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def get_agent_status():
    agents = {}
    orders_dir = 'orders/'

    if not os.path.exists(orders_dir):
        return agents

    for f in os.listdir(orders_dir):
        if f.endswith('_orders.json'):
            agent_name = f.replace('_orders.json', '').upper()
            filepath = os.path.join(orders_dir, f)
            with open(filepath, 'r') as fh:
                data = json.load(fh)

            open_positions = data.get('open_positions', {})
            closed_positions = data.get('closed_positions', {})

            total_pnl = sum(p.get('pnl', 0) for p in closed_positions.values() if p.get('pnl') is not None)
            wins = sum(1 for p in closed_positions.values() if p.get('outcome') == 'WIN')
            losses = sum(1 for p in closed_positions.values() if p.get('outcome') == 'LOSS')
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0

            agents[agent_name] = {
                'strategy': data.get('strategy', 'Unknown'),
                'capital': data.get('virtual_capital', 0),
                'peak_capital': data.get('peak_capital', 0),
                'open_positions': len(open_positions),
                'closed_trades': len(closed_positions),
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'last_updated': data.get('last_updated', 'N/A')
            }

    return agents


def get_training_stats():
    training_file = 'orders/training_data.jsonl'
    if not os.path.exists(training_file):
        return {'rows': 0, 'win_rate': 0, 'avg_pnl': 0}

    rows = []
    with open(training_file, 'r') as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    if not rows:
        return {'rows': 0, 'win_rate': 0, 'avg_pnl': 0}

    wins = sum(1 for r in rows if r.get('label') == 1)
    win_rate = (wins / len(rows) * 100) if rows else 0
    avg_pnl = sum(r.get('pnl_pct', 0) for r in rows) / len(rows) if rows else 0

    return {
        'rows': len(rows),
        'win_rate': win_rate,
        'avg_pnl': avg_pnl
    }


def print_dashboard():
    clear_screen()
    agents = get_agent_status()
    training = get_training_stats()

    print('\n' + '=' * 90)
    print('  CRYPTO AGENT TRADING ARENA - LIVE DASHBOARD')
    print(f'  Updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 90)

    if agents:
        print(f'\n{"Agent":<15} {"Strategy":<20} {"Capital":>10} {"PnL":>10} {"Win%":>8} {"Open":>6} {"Trades":>8}')
        print('-' * 90)

        sorted_agents = sorted(agents.items(), key=lambda x: x[1]['total_pnl'], reverse=True)
        for name, stats in sorted_agents:
            pnl_str = f'{stats["total_pnl"]:+,.0f}'
            print(f'{name:<15} {stats["strategy"]:<20} ${stats["capital"]:>9,.0f} ${pnl_str:>10} {stats["win_rate"]:>7.1f}% {stats["open_positions"]:>6} {stats["closed_trades"]:>8}')

    print('\n' + '-' * 90)
    print(f'  Training Data: {training["rows"]} rows | Win Rate: {training["win_rate"]:.1f}% | Avg PnL: {training["avg_pnl"]:+.2f}%')
    print('=' * 90)
    print('  Press Ctrl+C to exit | Auto-refreshes every 30 seconds')
    print()


def main():
    print('Starting live dashboard...')
    print('Press Ctrl+C to exit')

    try:
        while True:
            print_dashboard()
            time.sleep(30)
    except KeyboardInterrupt:
        print('\nDashboard stopped.')


if __name__ == '__main__':
    main()

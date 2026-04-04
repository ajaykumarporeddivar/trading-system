# monitor/health_check.py
import sys
import os
import json
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

RUN_STATE_FILE = 'logs/run_state.json'
CRASH_LOG = 'logs/crash_log.jsonl'
HEALTH_REPORT = 'logs/health_report.json'


def check_system_health():
    report = {
        'timestamp': datetime.now().isoformat(),
        'status': 'UNKNOWN',
        'issues': [],
        'metrics': {}
    }

    if not os.path.exists(RUN_STATE_FILE):
        report['status'] = 'NOT_RUNNING'
        report['issues'].append('No run state file found. System may not be running.')
        return report

    with open(RUN_STATE_FILE, 'r') as f:
        state = json.load(f)

    report['metrics'] = {
        'total_uptime_hours': state.get('total_uptime_hours', 0),
        'total_cycles': state.get('total_cycles', 0),
        'total_crashes': state.get('total_crashes', 0),
        'consecutive_crashes': state.get('consecutive_crashes', 0),
        'crashes_last_hour': state.get('crashes_last_hour', 0),
        'last_start': state.get('last_start', 'N/A')
    }

    if state.get('consecutive_crashes', 0) >= 5:
        report['status'] = 'CRITICAL'
        report['issues'].append(f'{state["consecutive_crashes"]} consecutive crashes')
    elif state.get('crashes_last_hour', 0) >= 3:
        report['status'] = 'WARNING'
        report['issues'].append(f'{state["crashes_last_hour"]} crashes in last hour')
    elif state.get('total_uptime_hours', 0) > 0:
        report['status'] = 'HEALTHY'
    else:
        report['status'] = 'STARTING'

    if os.path.exists(CRASH_LOG):
        crash_count = 0
        with open(CRASH_LOG, 'r') as f:
            for line in f:
                crash_count += 1
        report['metrics']['total_crash_entries'] = crash_count

    orders_dir = 'orders/'
    if os.path.exists(orders_dir):
        order_files = [f for f in os.listdir(orders_dir) if f.endswith('.json')]
        report['metrics']['active_agents'] = len(order_files)

        total_open = 0
        total_closed = 0
        for f in order_files:
            with open(os.path.join(orders_dir, f), 'r') as fh:
                data = json.load(fh)
                total_open += len(data.get('open_positions', {}))
                total_closed += len(data.get('closed_positions', {}))

        report['metrics']['total_open_positions'] = total_open
        report['metrics']['total_closed_trades'] = total_closed

    training_file = 'orders/training_data.jsonl'
    if os.path.exists(training_file):
        row_count = 0
        with open(training_file, 'r') as f:
            for line in f:
                if line.strip():
                    row_count += 1
        report['metrics']['training_data_rows'] = row_count

    os.makedirs('logs', exist_ok=True)
    with open(HEALTH_REPORT, 'w') as f:
        json.dump(report, f, indent=2)

    return report


def print_health_report():
    report = check_system_health()

    status_icon = {
        'HEALTHY': '[OK]',
        'WARNING': '[!!]',
        'CRITICAL': '[XX]',
        'NOT_RUNNING': '[--]',
        'STARTING': '[..]',
        'UNKNOWN': '[??]'
    }

    icon = status_icon.get(report['status'], '[??]')
    print(f'\n{icon} System Status: {report["status"]}')
    print(f'Timestamp: {report["timestamp"]}')
    print()

    if report['metrics']:
        print('Metrics:')
        for key, value in report['metrics'].items():
            print(f'  {key}: {value}')

    if report['issues']:
        print(f'\nIssues ({len(report["issues"])}):')
        for issue in report['issues']:
            print(f'  - {issue}')

    print()
    return report


if __name__ == '__main__':
    print_health_report()

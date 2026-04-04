# run_247.py - Continuous 24/7 Arena Runner with ML Learning
import sys
import os
import time
import json
import signal
import traceback
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from arena.config import ORDER_DIR
from arena.agents.ajay import AjayAgent
from arena.agents.vijay import VijayAgent
from arena.agents.sanjay import SanjayAgent
from arena.agents.rama import RamaAgent
from arena.agents.meenakshi import MeenakshiAgent
from arena.agents.rani import RaniAgent
from arena.arena_runner import ArenaRunner
from arena.leaderboard import print_leaderboard
from arena.training_export import export_performance_csv, load_training_data
from ml.retrain_scheduler import RetrainScheduler
from ml.trainer import get_model_status
from core.logger import logger

RUN_STATE_FILE = 'logs/run_state.json'
CRASH_LOG = 'logs/crash_log.jsonl'
MAX_RESTARTS_PER_HOUR = 5
MAX_CONSECUTIVE_CRASHES = 10


def load_run_state():
    if os.path.exists(RUN_STATE_FILE):
        with open(RUN_STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        'total_uptime_hours': 0,
        'total_cycles': 0,
        'total_crashes': 0,
        'last_start': None,
        'crashes_last_hour': 0,
        'consecutive_crashes': 0,
        'last_crash_time': None
    }


def save_run_state(state):
    os.makedirs(os.path.dirname(RUN_STATE_FILE), exist_ok=True)
    with open(RUN_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def log_crash(error_msg, traceback_str):
    os.makedirs(os.path.dirname(CRASH_LOG), exist_ok=True)
    crash_entry = {
        'timestamp': datetime.now().isoformat(),
        'error': str(error_msg),
        'traceback': traceback_str
    }
    with open(CRASH_LOG, 'a') as f:
        f.write(json.dumps(crash_entry) + '\n')


def check_crash_limits(state):
    now = datetime.now()
    if state.get('last_crash_time'):
        last_crash = datetime.fromisoformat(state['last_crash_time'])
        if (now - last_crash).total_seconds() < 3600:
            state['crashes_last_hour'] += 1
        else:
            state['crashes_last_hour'] = 1
    else:
        state['crashes_last_hour'] = 1

    state['last_crash_time'] = now.isoformat()
    state['consecutive_crashes'] = state.get('consecutive_crashes', 0) + 1
    state['total_crashes'] = state.get('total_crashes', 0) + 1

    if state['crashes_last_hour'] >= MAX_RESTARTS_PER_HOUR:
        logger.critical(f'CRASH LIMIT REACHED: {state["crashes_last_hour"]} crashes in last hour. Waiting 10 minutes...')
        return False, 600

    if state['consecutive_crashes'] >= MAX_CONSECUTIVE_CRASHES:
        logger.critical(f'MAX CONSECUTIVE CRASHES: {state["consecutive_crashes"]}. Waiting 30 minutes...')
        return False, 1800

    wait_time = min(2 ** state['consecutive_crashes'], 300)
    logger.warning(f'Crash #{state["consecutive_crashes"]}. Waiting {wait_time}s before restart...')
    return True, wait_time


def create_agents():
    os.makedirs(ORDER_DIR, exist_ok=True)
    return [
        AjayAgent(f'{ORDER_DIR}ajay_orders.json'),
        VijayAgent(f'{ORDER_DIR}vijay_orders.json'),
        SanjayAgent(f'{ORDER_DIR}sanjay_orders.json'),
        RamaAgent(f'{ORDER_DIR}rama_orders.json'),
        MeenakshiAgent(f'{ORDER_DIR}meenakshi_orders.json'),
        RaniAgent(f'{ORDER_DIR}rani_orders.json'),
    ]


def print_banner():
    banner = '''
    +============================================+
    |   CRYPTO AGENT TRADING ARENA - 24/7 MODE   |
    |   6 Agents  |   Real Money               |
    |   BTC ETH SOL BNB XRP  |  4h               |
    |   Auto-Restart  |  ML Learning             |
    +============================================+
    '''
    print(banner)


def print_status(state):
    model_status = get_model_status()
    training_rows = load_training_data()

    print(f'\n{"=" * 60}')
    print(f'  SYSTEM STATUS')
    print(f'{"=" * 60}')
    print(f'  Total Uptime:      {state.get("total_uptime_hours", 0):.1f} hours')
    print(f'  Total Cycles:      {state.get("total_cycles", 0)}')
    print(f'  Total Crashes:     {state.get("total_crashes", 0)}')
    print(f'  Consecutive:       {state.get("consecutive_crashes", 0)}')
    print(f'  Last Start:        {state.get("last_start", "N/A")}')
    print(f'  Training Data:     {len(training_rows)} rows')
    print(f'  ML Model:          {model_status.get("status", "N/A")}')
    if model_status.get('metrics'):
        print(f'  ML Accuracy:       {model_status["metrics"].get("accuracy", 0):.3f}')
    print(f'{"=" * 60}\n')


def run_arena_cycle(runner, state):
    try:
        import asyncio
        ran = asyncio.run(runner._run_all_timeframes())
        state['total_cycles'] = state.get('total_cycles', 0) + 1
        state['consecutive_crashes'] = 0
        if not ran:
            time.sleep(5)
        return True
    except Exception as e:
        tb = traceback.format_exc()
        log_crash(str(e), tb)
        ok, wait_time = check_crash_limits(state)
        if not ok:
            logger.critical(f'System entering cooldown for {wait_time}s')
            time.sleep(wait_time)
            state['consecutive_crashes'] = 0
            state['crashes_last_hour'] = 0
        else:
            time.sleep(wait_time)
        return False


def main():
    print_banner()

    state = load_run_state()
    state['last_start'] = datetime.now().isoformat()
    save_run_state(state)

    agents = create_agents()
    runner = ArenaRunner(agents)

    retrain_scheduler = RetrainScheduler(
        check_interval=int(os.getenv('ML_RETRAIN_INTERVAL', '3600')),
        min_samples=int(os.getenv('ML_MIN_SAMPLES', '500'))
    )
    retrain_scheduler.start()

    logger.info('24/7 Arena engine starting with ML learning...')
    print_status(state)

    cycle_count = 0
    last_daily_report = date.today()
    start_time = time.time()

    try:
        while True:
            cycle_count += 1
            success = run_arena_cycle(runner, state)

            if success:
                current_time = time.time()
                state['total_uptime_hours'] = (current_time - start_time) / 3600
                save_run_state(state)

            today = date.today()
            if today != last_daily_report:
                logger.info('Generating daily report...')
                print_status(state)
                print_leaderboard(agents, 'DAILY')
                export_performance_csv(agents)
                last_daily_report = today

            if cycle_count % 10 == 0:
                training_rows = load_training_data()
                logger.info(f'Progress: {cycle_count} cycles, {len(training_rows)} training rows')

    except KeyboardInterrupt:
        logger.info('Shutdown requested...')
        retrain_scheduler.stop()
        print('\n' + '=' * 60)
        print('  FINAL REPORT')
        print('=' * 60)
        state['total_uptime_hours'] = (time.time() - start_time) / 3600
        save_run_state(state)
        print_status(state)
        print_leaderboard(agents, 'FINAL')
        export_performance_csv(agents)
        training_rows = load_training_data()
        print(f'Training data: {len(training_rows)} rows saved to {ORDER_DIR}training_data.jsonl')
        print('Arena stopped gracefully.')
    except Exception as e:
        tb = traceback.format_exc()
        log_crash(str(e), tb)
        logger.critical(f'FATAL ERROR: {e}')
        logger.critical(tb)
        state['total_crashes'] = state.get('total_crashes', 0) + 1
        save_run_state(state)
        retrain_scheduler.stop()
        sys.exit(1)


if __name__ == '__main__':
    main()

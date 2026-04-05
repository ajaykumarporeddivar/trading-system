# engine/sr_tracker.py - Support/Resistance Bounce Tracker
import json
import os
from typing import Dict, Any, List
from datetime import datetime

SR_TRACKER_FILE = 'orders/sr_tracker.json'
TOUCH_THRESHOLD = 0.002  # 0.2% distance = "touched"
HOLDING_PERIODS = 3  # candles to wait for bounce confirmation

class SRTracker:
    def __init__(self):
        self.data = self._load()

    def _load(self) -> Dict[str, Any]:
        if os.path.exists(SR_TRACKER_FILE):
            try:
                with open(SR_TRACKER_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {'levels': {}, 'tests': []}

    def _save(self):
        os.makedirs(os.path.dirname(SR_TRACKER_FILE) if os.path.dirname(SR_TRACKER_FILE) else '.', exist_ok=True)
        with open(SR_TRACKER_FILE, 'w') as f:
            json.dump(self.data, f, indent=2)

    def _key(self, symbol: str, timeframe: str, label: str) -> str:
        return f'{symbol}_{timeframe}_{label}'

    def record_test(self, symbol: str, timeframe: str, level_label: str,
                    level_price: float, touch_price: float, touch_time: str):
        key = self._key(symbol, timeframe, level_label)
        if key not in self.data['levels']:
            self.data['levels'][key] = {'tests': 0, 'bounces': 0, 'breaks': 0, 'pending': []}
        test = {
            'key': key,
            'symbol': symbol,
            'timeframe': timeframe,
            'level_label': level_label,
            'level_price': level_price,
            'touch_price': touch_price,
            'touch_time': touch_time,
            'status': 'pending',
            'candles_elapsed': 0
        }
        self.data['levels'][key]['tests'] += 1
        self.data['levels'][key]['pending'].append(test)
        self.data['tests'].append(test)
        self._save()

    def resolve_pending(self, symbol: str, timeframe: str, current_prices: Dict[str, float]):
        for test in list(self.data['tests']):
            if test['status'] != 'pending':
                continue
            if test['symbol'] != symbol or test['timeframe'] != timeframe:
                continue
            test['candles_elapsed'] += 1
            if test['candles_elapsed'] < HOLDING_PERIODS:
                continue
            current_price = current_prices.get(symbol, test['touch_price'])
            level_price = test['level_price']
            level_label = test['level_label']
            is_support = level_label.startswith('S') or 'support' in level_label.lower()
            if is_support:
                bounced = current_price > level_price
            else:
                bounced = current_price < level_price
            key = test['key']
            if key in self.data['levels']:
                if bounced:
                    self.data['levels'][key]['bounces'] += 1
                    test['status'] = 'bounce'
                else:
                    self.data['levels'][key]['breaks'] += 1
                    test['status'] = 'break'
                test['resolution_price'] = current_price
                test['resolution_time'] = datetime.now().isoformat()
                self.data['levels'][key]['pending'] = [
                    p for p in self.data['levels'][key]['pending'] if p is not test
                ]
        self.data['tests'] = [t for t in self.data['tests'] if t['status'] == 'pending' or t['candles_elapsed'] < HOLDING_PERIODS + 10]
        self._save()

    def get_stats(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        result = {}
        for key, stats in self.data['levels'].items():
            if key.startswith(f'{symbol}_{timeframe}_'):
                label = key.split('_', 2)[2]
                tests = stats['tests']
                bounces = stats['bounces']
                breaks = stats['breaks']
                resolved = bounces + breaks
                win_rate = round((bounces / resolved * 100) if resolved > 0 else 0, 1)
                result[label] = {
                    'tests': tests,
                    'bounces': bounces,
                    'breaks': breaks,
                    'win_rate': win_rate,
                    'pending': len(stats.get('pending', []))
                }
        return result

    def get_all_stats(self) -> Dict[str, Any]:
        return self.data['levels']

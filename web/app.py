import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import json
import time
import threading
import queue
import hashlib
from datetime import datetime, timedelta
from functools import wraps

import jwt
import numpy as np
from flask import Flask, render_template, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from monitor.health_check import check_system_health

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
            static_folder=os.path.join(os.path.dirname(__file__), 'static'))
CORS(app)

app.config['SECRET_KEY'] = os.getenv('DASHBOARD_SECRET', 'trading-system-v11-secret-key-2026')
JWT_EXPIRY = 24

_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 15

_sse_clients = []
_sse_lock = threading.Lock()

C2_LOG = 'logs/c2_actions.jsonl'


def _cached(key, fn, ttl=None):
    ttl = ttl or CACHE_TTL
    with _cache_lock:
        entry = _cache.get(key)
        if entry and time.time() - entry['ts'] < ttl:
            return entry['data']
    data = fn()
    with _cache_lock:
        _cache[key] = {'data': data, 'ts': time.time()}
    return data


def _hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def _get_admin_hash():
    return _hash_password(os.getenv('DASHBOARD_PASSWORD', 'admin'))


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            token = request.cookies.get('token', '')
        if not token:
            token = request.args.get('token', '')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.user = payload
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            token = request.cookies.get('token', '')
        if not token:
            token = request.args.get('token', '')
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            if payload.get('role') != 'admin':
                return jsonify({'error': 'Admin access required'}), 403
            request.user = payload
            return f(*args, **kwargs)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
    return decorated


def _log_c2_action(action, details, user='system'):
    try:
        os.makedirs('logs', exist_ok=True)
        entry = {
            'action': action,
            'details': details,
            'user': user,
            'timestamp': datetime.now().isoformat()
        }
        with open(C2_LOG, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    except Exception:
        pass


def _broadcast_sse(event, data):
    msg = f'event: {event}\ndata: {json.dumps(data)}\n\n'
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(msg)
            except Exception:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)


# ==================== DATA FUNCTIONS ====================

def get_agent_status():
    agents = {}
    orders_dir = os.path.join(os.path.dirname(__file__), '..', 'orders')
    if not os.path.exists(orders_dir):
        return agents
    for f in os.listdir(orders_dir):
        if f.endswith('_orders.json'):
            agent_name = f.replace('_orders.json', '').upper()
            filepath = os.path.join(orders_dir, f)
            try:
                with open(filepath, 'r') as fh:
                    data = json.load(fh)
                open_positions = data.get('open_positions', {})
                closed_positions = data.get('closed_positions', {})
                total_pnl = sum(p.get('pnl', 0) for p in closed_positions.values() if p.get('pnl') is not None)
                wins = sum(1 for p in closed_positions.values() if p.get('outcome') == 'WIN')
                losses = sum(1 for p in closed_positions.values() if p.get('outcome') == 'LOSS')
                win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
                ml_rejected = sum(1 for p in closed_positions.values() if p.get('ml_prob_win', 0.5) < 0.4)
                agents[agent_name] = {
                    'strategy': data.get('strategy', 'Unknown'),
                    'capital': data.get('virtual_capital', 0),
                    'peak_capital': data.get('peak_capital', 0),
                    'open_positions': len(open_positions),
                    'closed_trades': len(closed_positions),
                    'wins': wins,
                    'losses': losses,
                    'win_rate': round(win_rate, 1),
                    'total_pnl': round(total_pnl, 2),
                    'ml_rejected': ml_rejected,
                    'last_updated': data.get('last_updated', 'N/A')
                }
            except Exception:
                continue
    return agents


def get_training_stats():
    training_file = os.path.join(os.path.dirname(__file__), '..', 'orders', 'training_data.jsonl')
    if not os.path.exists(training_file):
        return {'rows': 0, 'win_rate': 0, 'avg_pnl': 0, 'regime_breakdown': {}, 'enriched_rows': 0}
    rows = []
    with open(training_file, 'r') as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    if not rows:
        return {'rows': 0, 'win_rate': 0, 'avg_pnl': 0, 'regime_breakdown': {}, 'enriched_rows': 0}
    wins = sum(1 for r in rows if r.get('label') == 1)
    win_rate = (wins / len(rows) * 100) if rows else 0
    avg_pnl = sum(r.get('pnl_pct', 0) for r in rows) / len(rows) if rows else 0

    regime_counts = {}
    enriched = 0
    for r in rows:
        regime = r.get('regime_at_entry', 'unknown')
        regime_counts[regime] = regime_counts.get(regime, 0) + 1
        if r.get('position_size_factors') or r.get('regime_at_exit'):
            enriched += 1

    return {
        'rows': len(rows),
        'win_rate': round(win_rate, 1),
        'avg_pnl': round(avg_pnl, 2),
        'regime_breakdown': regime_counts,
        'enriched_rows': enriched
    }


def get_model_status():
    try:
        metrics_path = os.path.join(os.path.dirname(__file__), '..', 'ml', 'models', 'metrics.json')
        model_path = os.path.join(os.path.dirname(__file__), '..', 'ml', 'models', 'trading_model.pkl')
        if not os.path.exists(model_path):
            return {'status': 'NO_MODEL', 'message': 'No trained model found'}
        with open(metrics_path, 'r') as f:
            metrics = json.load(f)
        return {
            'status': 'READY',
            'metrics': metrics,
            'total_training_rows': metrics.get('total_samples', 0),
            'model_file': os.path.getsize(model_path)
        }
    except Exception as e:
        return {'status': 'ERROR', 'message': str(e)}


def get_recent_signals():
    orders_dir = os.path.join(os.path.dirname(__file__), '..', 'orders')
    if not os.path.exists(orders_dir):
        return []
    signals = []
    for f in os.listdir(orders_dir):
        if f.endswith('_orders.json'):
            filepath = os.path.join(orders_dir, f)
            try:
                with open(filepath, 'r') as fh:
                    data = json.load(fh)
                agent_name = f.replace('_orders.json', '').upper()
                for pos_id, pos in {**data.get('open_positions', {}), **data.get('closed_positions', {})}.items():
                    if pos.get('opened_at'):
                        ml_prob = pos.get('ml_prob_win', 0.5)
                        signals.append({
                            'timestamp': pos.get('opened_at', ''),
                            'symbol': pos.get('symbol', ''),
                            'verdict': pos.get('side', 'UNKNOWN'),
                            'confidence': pos.get('confidence', 0),
                            'agent': agent_name,
                            'reason': pos.get('reason', ''),
                            'status': pos.get('status', 'unknown'),
                            'timeframe': pos.get('timeframe', 'unknown'),
                            'regime': pos.get('regime_at_entry', 'unknown'),
                            'ml_prob_win': round(ml_prob, 2),
                            'ml_approved': ml_prob >= 0.30 and pos.get('ml_prediction', -1) != 0
                        })
            except Exception:
                continue
    signals.sort(key=lambda x: x['timestamp'], reverse=True)
    return signals[:50]


def get_recent_trades():
    orders_dir = os.path.join(os.path.dirname(__file__), '..', 'orders')
    if not os.path.exists(orders_dir):
        return []
    trades = []
    for f in os.listdir(orders_dir):
        if f.endswith('_orders.json'):
            filepath = os.path.join(orders_dir, f)
            try:
                with open(filepath, 'r') as fh:
                    data = json.load(fh)
                agent_name = f.replace('_orders.json', '').upper()
                for pos_id, pos in data.get('closed_positions', {}).items():
                    if pos.get('closed_at'):
                        size_factors = pos.get('position_size_factors', {})
                        trades.append({
                            'timestamp': pos.get('closed_at', ''),
                            'symbol': pos.get('symbol', ''),
                            'side': pos.get('side', ''),
                            'entry_price': pos.get('entry_price', 0),
                            'exit_price': pos.get('exit_price', 0),
                            'pnl': pos.get('pnl', 0),
                            'pnl_pct': pos.get('pnl_pct', 0),
                            'status': pos.get('status', 'closed'),
                            'agent': agent_name,
                            'close_reason': pos.get('close_reason', ''),
                            'timeframe': pos.get('timeframe', 'unknown'),
                            'regime_entry': pos.get('regime_at_entry', 'unknown'),
                            'regime_exit': pos.get('regime_at_exit', 'unknown'),
                            'ml_prob_win': round(pos.get('ml_prob_win', 0.5), 2),
                            'stop_out': pos.get('stop_out', False),
                            'size_factors': size_factors
                        })
            except Exception:
                continue
    trades.sort(key=lambda x: x['timestamp'], reverse=True)
    return trades[:50]


def get_mtf_matrix():
    orders_dir = os.path.join(os.path.dirname(__file__), '..', 'orders')
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
    timeframes = ['1m', '5m', '15m', '30m', '1h', '2h', '4h']
    matrix = {}
    if not os.path.exists(orders_dir):
        return {'symbols': symbols, 'timeframes': timeframes, 'cells': {}}
    for sym in symbols:
        matrix[sym] = {}
        for tf in timeframes:
            matrix[sym][tf] = {
                'regime': 'unknown',
                'signals': 0,
                'open_positions': 0,
                'avg_ml_prob': 0,
                'last_signal': None
            }
    for f in os.listdir(orders_dir):
        if f.endswith('_orders.json'):
            try:
                with open(os.path.join(orders_dir, f), 'r') as fh:
                    data = json.load(fh)
                for pos_id, pos in {**data.get('open_positions', {}), **data.get('closed_positions', {})}.items():
                    sym = pos.get('symbol', '')
                    tf = pos.get('timeframe', '4h')
                    if sym in matrix and tf in matrix.get(sym, {}):
                        matrix[sym][tf]['signals'] += 1
                        if pos.get('status') == 'open':
                            matrix[sym][tf]['open_positions'] += 1
                        ml_prob = pos.get('ml_prob_win', 0.5)
                        current_avg = matrix[sym][tf]['avg_ml_prob']
                        n = matrix[sym][tf]['signals']
                        matrix[sym][tf]['avg_ml_prob'] = round((current_avg * (n - 1) + ml_prob) / n, 2) if n > 0 else ml_prob
                        ts = pos.get('opened_at', '')
                        if not matrix[sym][tf]['last_signal'] or ts > matrix[sym][tf]['last_signal']:
                            matrix[sym][tf]['last_signal'] = ts
                            matrix[sym][tf]['regime'] = pos.get('regime_at_entry', 'unknown')
            except Exception:
                continue
    return {'symbols': symbols, 'timeframes': timeframes, 'cells': matrix}


def get_v11_system_status():
    try:
        from ml.model_registry import ModelRegistry
        from ml.ab_testing import ABTesting

        registry = ModelRegistry()
        ab = ABTesting()

        sentinel_log = os.path.join(os.path.dirname(__file__), '..', 'logs', 'sentinel_events.jsonl')
        sentinel_events = []
        if os.path.exists(sentinel_log):
            with open(sentinel_log, 'r') as f:
                for line in f:
                    if line.strip():
                        sentinel_events.append(json.loads(line))

        governance_log = os.path.join(os.path.dirname(__file__), '..', 'logs', 'governance_decisions.jsonl')
        governance_decisions = []
        if os.path.exists(governance_log):
            with open(governance_log, 'r') as f:
                for line in f:
                    if line.strip():
                        governance_decisions.append(json.loads(line))

        stability_log = os.path.join(os.path.dirname(__file__), '..', 'logs', 'stability_contract.jsonl')
        stability_checks = []
        if os.path.exists(stability_log):
            with open(stability_log, 'r') as f:
                for line in f:
                    if line.strip():
                        stability_checks.append(json.loads(line))

        ml_predictions_log = os.path.join(os.path.dirname(__file__), '..', 'logs', 'ml_predictions.jsonl')
        ml_stats = {'total': 0, 'avg_prob': 0.5, 'approved': 0, 'rejected': 0, 'by_tf': {}}
        if os.path.exists(ml_predictions_log):
            preds = []
            with open(ml_predictions_log, 'r') as f:
                for line in f:
                    if line.strip():
                        preds.append(json.loads(line))
            if preds:
                ml_stats['total'] = len(preds)
                ml_stats['avg_prob'] = round(sum(p.get('prob_win', 0.5) for p in preds) / len(preds), 3)
                ml_stats['approved'] = sum(1 for p in preds if p.get('prob_win', 0.5) >= 0.30 and p.get('prediction', -1) != 0)
                ml_stats['rejected'] = ml_stats['total'] - ml_stats['approved']

        training_file = os.path.join(os.path.dirname(__file__), '..', 'orders', 'training_data.jsonl')
        tf_stats = {}
        if os.path.exists(training_file):
            with open(training_file, 'r') as f:
                for line in f:
                    if line.strip():
                        row = json.loads(line)
                        tf = row.get('timeframe', 'unknown')
                        if tf not in tf_stats:
                            tf_stats[tf] = {'trades': 0, 'wins': 0, 'total_pnl': 0}
                        tf_stats[tf]['trades'] += 1
                        if row.get('label') == 1:
                            tf_stats[tf]['wins'] += 1
                        tf_stats[tf]['total_pnl'] += row.get('pnl_pct', 0)
            for tf in tf_stats:
                t = tf_stats[tf]
                t['win_rate'] = round(t['wins'] / t['trades'] * 100, 1) if t['trades'] > 0 else 0
                t['avg_pnl'] = round(t['total_pnl'] / t['trades'], 2) if t['trades'] > 0 else 0

        diagnostics_log = os.path.join(os.path.dirname(__file__), '..', 'logs', 'diagnostics.jsonl')
        drift_alerts = 0
        if os.path.exists(diagnostics_log):
            with open(diagnostics_log, 'r') as f:
                for line in f:
                    if line.strip():
                        d = json.loads(line)
                        if d.get('drift_detected'):
                            drift_alerts += 1

        c2_log = os.path.join(os.path.dirname(__file__), '..', C2_LOG)
        c2_actions = []
        if os.path.exists(c2_log):
            with open(c2_log, 'r') as f:
                for line in f:
                    if line.strip():
                        c2_actions.append(json.loads(line))

        return {
            'sentinel': {
                'halted': False,
                'total_triggers': len(sentinel_events),
                'recent_events': sentinel_events[-3:]
            },
            'registry': registry.get_status(),
            'ab_testing': ab.get_partition_status(),
            'governance': governance_decisions[-3:],
            'stability_contract': stability_checks[-3:],
            'ml_predictions': ml_stats,
            'timeframe_stats': tf_stats,
            'drift_alerts': drift_alerts,
            'c2_actions': c2_actions[-10:]
        }
    except Exception as e:
        return {'error': str(e)}


# ==================== ROUTES ====================

@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    password = data.get('password', '')
    if _hash_password(password) == _get_admin_hash():
        token = jwt.encode({
            'role': 'admin',
            'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRY)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        resp = jsonify({'token': token, 'role': 'admin'})
        resp.set_cookie('token', token, httponly=True, max_age=JWT_EXPIRY * 3600)
        _log_c2_action('login', {'user': 'admin'})
        return resp
    return jsonify({'error': 'Invalid password'}), 401


@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/dashboard')
@require_auth
def api_dashboard():
    agents = _cached('agents', get_agent_status, ttl=5)
    training = _cached('training', get_training_stats, ttl=10)
    health = _cached('health', check_system_health, ttl=10)
    model = _cached('model', get_model_status, ttl=30)
    v11 = _cached('v11', get_v11_system_status, ttl=10)
    total_pnl = sum(a['total_pnl'] for a in agents.values())
    total_trades = sum(a['closed_trades'] for a in agents.values())
    total_wins = sum(a['wins'] for a in agents.values())
    total_ml_rejected = sum(a.get('ml_rejected', 0) for a in agents.values())
    overall_win_rate = round((total_wins / total_trades * 100) if total_trades > 0 else 0, 1)
    return jsonify({
        'agents': agents,
        'summary': {
            'total_pnl': round(total_pnl, 2),
            'total_trades': total_trades,
            'overall_win_rate': overall_win_rate,
            'active_agents': len(agents),
            'health_status': health.get('status', 'UNKNOWN'),
            'ml_rejected': total_ml_rejected,
            'enriched_training_rows': training.get('enriched_rows', 0)
        },
        'training': training,
        'model': model,
        'v11': v11
    })


@app.route('/api/agents')
@require_auth
def api_agents():
    return jsonify(_cached('agents', get_agent_status, ttl=5))


@app.route('/api/health')
@require_auth
def api_health():
    return jsonify(_cached('health', check_system_health, ttl=10))


@app.route('/api/signals')
@require_auth
def api_signals():
    return jsonify(get_recent_signals())


@app.route('/api/trades')
@require_auth
def api_trades():
    return jsonify(get_recent_trades())


@app.route('/api/model')
@require_auth
def api_model():
    return jsonify(_cached('model', get_model_status, ttl=30))


@app.route('/api/v11')
@require_auth
def api_v11():
    return jsonify(_cached('v11', get_v11_system_status, ttl=10))


@app.route('/api/mtf-matrix')
@require_auth
def api_mtf_matrix():
    return jsonify(_cached('mtf', get_mtf_matrix, ttl=5))


@app.route('/api/stream')
@require_auth
def api_stream():
    def event_stream():
        q = queue.Queue(maxsize=50)
        with _sse_lock:
            _sse_clients.append(q)
        try:
            while True:
                try:
                    msg = q.get(timeout=30)
                    yield msg
                except queue.Empty:
                    yield f': heartbeat\n\n'
        except GeneratorExit:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)
    return Response(stream_with_context(event_stream()),
                    mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


# ==================== C2 CONTROLS ====================

@app.route('/api/c2/halt-all', methods=['POST'])
@require_admin
def c2_halt_all():
    try:
        from core.tail_risk_sentinel import TailRiskSentinel
        sentinel = TailRiskSentinel()
        sentinel.force_halt('Manual halt from dashboard')
        _log_c2_action('halt_all', {'triggered_by': request.user.get('role', 'admin')})
        _broadcast_sse('alert', {'type': 'HALT', 'message': 'All new entries halted by admin'})
        return jsonify({'status': 'halted', 'message': 'All new entries halted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/c2/resume-all', methods=['POST'])
@require_admin
def c2_resume_all():
    try:
        from core.tail_risk_sentinel import TailRiskSentinel
        sentinel = TailRiskSentinel()
        sentinel.clear_halt()
        _log_c2_action('resume_all', {'triggered_by': request.user.get('role', 'admin')})
        _broadcast_sse('alert', {'type': 'RESUME', 'message': 'Trading resumed by admin'})
        return jsonify({'status': 'resumed', 'message': 'Trading resumed'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/c2/close-all-positions', methods=['POST'])
@require_admin
def c2_close_all():
    try:
        orders_dir = os.path.join(os.path.dirname(__file__), '..', 'orders')
        closed_count = 0
        for f in os.listdir(orders_dir):
            if f.endswith('_orders.json'):
                filepath = os.path.join(orders_dir, f)
                with open(filepath, 'r') as fh:
                    data = json.load(fh)
                for oid, pos in list(data.get('open_positions', {}).items()):
                    entry = pos.get('entry_price', 0)
                    side = pos.get('side', 'BUY')
                    pos['status'] = 'closed'
                    pos['closed_at'] = datetime.now().isoformat()
                    pos['exit_price'] = entry
                    pos['pnl'] = 0
                    pos['pnl_pct'] = 0
                    pos['outcome'] = 'BREAKEVEN'
                    pos['close_reason'] = 'manual_close_all'
                    pos['regime_at_exit'] = pos.get('regime_at_entry', 'unknown')
                    data['closed_positions'][oid] = pos
                    closed_count += 1
                data['open_positions'] = {}
                with open(filepath, 'w') as fh:
                    json.dump(data, fh, indent=2)
        _log_c2_action('close_all_positions', {'count': closed_count, 'triggered_by': request.user.get('role', 'admin')})
        _broadcast_sse('alert', {'type': 'CLOSE_ALL', 'message': f'{closed_count} positions closed manually'})
        return jsonify({'status': 'closed', 'count': closed_count})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/c2/retrain', methods=['POST'])
@require_admin
def c2_retrain():
    try:
        from ml.trainer import train_model
        metrics = train_model()
        _log_c2_action('manual_retrain', {'metrics': metrics, 'triggered_by': request.user.get('role', 'admin')})
        _broadcast_sse('alert', {'type': 'RETRAIN', 'message': f'Model retrained: acc={metrics.get("accuracy", 0):.3f}' if metrics else 'Retrain failed'})
        return jsonify({'status': 'retrained', 'metrics': metrics})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def run(port=5000, debug=False):
    app.run(host='0.0.0.0', port=port, debug=debug)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    run(port=port, debug=False)

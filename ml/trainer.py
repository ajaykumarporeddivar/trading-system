# ml/trainer.py - ML Training Pipeline
import json
import os
import sys
import pickle
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.logger import logger

TRAINING_EXPORT = 'orders/training_data.jsonl'
MODEL_DIR = 'ml/models/'
METRICS_FILE = 'ml/models/metrics.json'
WALK_FORWARD_WINDOW = 500
FEATURE_PRUNE_BOTTOM = 0.20
V11_MIN_ROWS = 250
V11_REQUIRED_FIELDS = ['regime_at_entry', 'timeframe', 'ml_gate_score']

QUALITY_AGENTS = {'AJAY', 'RAMA'}
MIN_PNL_PCT_FOR_WIN = 0.10


def load_training_data(filepath: str = TRAINING_EXPORT) -> List[Dict[str, Any]]:
    if not os.path.exists(filepath):
        return []
    rows = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _is_v11_row(row: Dict[str, Any]) -> bool:
    return all(row.get(field) is not None for field in V11_REQUIRED_FIELDS)


def _purge_old_data(filepath: str = TRAINING_EXPORT):
    if not os.path.exists(filepath):
        return
    rows = load_training_data(filepath)
    v11_rows = [r for r in rows if _is_v11_row(r)]
    old_rows = [r for r in rows if not _is_v11_row(r)]

    if len(v11_rows) >= V11_MIN_ROWS and old_rows:
        with open(filepath, 'w') as f:
            for row in v11_rows:
                f.write(json.dumps(row) + '\n')
        logger.info(f'Data purge: removed {len(old_rows)} pre-V11 rows, kept {len(v11_rows)} V11 rows')


def flatten_features(rows: List[Dict[str, Any]]):
    X = []
    y = []
    symbols = []
    agents = []

    for row in rows:
        features = row.get('features', {})
        if not features:
            continue

        flat = {}
        for key, value in features.items():
            if isinstance(value, (int, float)) and value is not None:
                flat[key] = value
            elif isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, (int, float)) and v is not None:
                        flat[f'{key}_{k}'] = v

        if len(flat) < 5:
            continue

        X.append(flat)
        y.append(row.get('label', 0))
        symbols.append(row.get('symbol', ''))
        agents.append(row.get('agent', ''))

    return X, y, symbols, agents


def align_features(X: List[Dict[str, Any]]):
    all_keys = set()
    for features in X:
        all_keys.update(features.keys())
    all_keys = sorted(list(all_keys))

    X_array = []
    for features in X:
        row = [features.get(k, 0) for k in all_keys]
        X_array.append(row)

    return np.array(X_array), all_keys


def _filter_quality_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    quality = []
    excluded_agents = 0
    for r in rows:
        agent = r.get('agent', '')
        if agent not in QUALITY_AGENTS:
            excluded_agents += 1
            continue
        quality.append(r)

    if excluded_agents:
        logger.info(f'Quality filter: excluded {excluded_agents} rows from non-quality agents (kept {QUALITY_AGENTS})')

    wins = sum(1 for r in quality if r.get('label') == 1)
    wr = wins / len(quality) * 100 if quality else 0
    logger.info(f'Quality rows: {len(quality)} ({wins}W/{len(quality)-wins}L, {wr:.1f}% WR)')
    return quality


def train_model(model_type: str = 'random_forest', use_walk_forward: bool = True, prune_features: bool = True, v11_only: bool = True):
    all_rows = load_training_data()
    if len(all_rows) < 50:
        logger.warning(f'Not enough training data: {len(all_rows)} rows (need 50+)')
        return None

    _purge_old_data()

    rows = _filter_quality_rows(all_rows)
    if len(rows) < 50:
        logger.warning(f'Not enough quality rows after filtering: {len(rows)} (need 50+)')
        return None

    if use_walk_forward and len(rows) > WALK_FORWARD_WINDOW:
        rows = rows[-WALK_FORWARD_WINDOW:]
        logger.info(f'Walk-forward: using last {len(rows)} rows of {len(all_rows)} total')

    X_dicts, y, symbols, agents = flatten_features(rows)
    if len(X_dicts) < 50:
        logger.warning(f'Not enough valid features: {len(X_dicts)} (need 50+)')
        return None

    X_array, feature_names = align_features(X_dicts)
    y_array = np.array(y)

    win_rate = sum(y_array) / len(y_array)
    logger.info(f'Training on {len(rows)} quality rows, label win rate: {win_rate:.1%}')

    if prune_features and len(feature_names) > 10:
        X_array, feature_names, pruned_count = _prune_weak_features(X_array, feature_names, y_array)
        if pruned_count > 0:
            logger.info(f'Feature pruning: removed {pruned_count} weak features, {len(feature_names)} remaining')

    X_train, X_test, y_train, y_test = train_test_split(
        X_array, y_array, test_size=0.2, random_state=42,
        stratify=y_array if len(set(y_array)) > 1 and min(np.bincount(y_array.astype(int))) >= 2 else None
    )

    models_to_try = [
        ('random_forest', RandomForestClassifier(
            n_estimators=100, max_depth=10, min_samples_split=5, random_state=42
        )),
        ('gradient_boosting', GradientBoostingClassifier(
            n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42
        )),
    ]

    best_model = None
    best_metrics = None
    best_score = -1

    for name, model in models_to_try:
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test, y_pred)
        f1 = f1_score(y_test, y_pred, zero_division=0.0)
        score = acc * 0.4 + f1 * 0.6

        metrics = {
            'accuracy': acc,
            'precision': precision_score(y_test, y_pred, zero_division=0.0),
            'recall': recall_score(y_test, y_pred, zero_division=0.0),
            'f1': f1,
            'train_size': len(X_train),
            'test_size': len(X_test),
            'total_samples': len(X_array),
            'feature_names': feature_names,
            'feature_importance': dict(zip(feature_names, model.feature_importances_.tolist())) if hasattr(model, 'feature_importances_') else {},
            'trained_at': datetime.now().isoformat(),
            'model_type': name
        }

        if score > best_score:
            best_score = score
            best_model = model
            best_metrics = metrics
            logger.info(f'{name}: accuracy={acc:.3f}, f1={f1:.3f} (best so far)')

    if best_model is None or best_metrics is None:
        logger.error('No model could be trained')
        return None

    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_DIR, 'trading_model.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(best_model, f)

    with open(METRICS_FILE, 'w') as f:
        json.dump(best_metrics, f, indent=2)

    logger.info(f'Model trained: {best_metrics["model_type"]} accuracy={best_metrics["accuracy"]:.3f}, f1={best_metrics["f1"]:.3f}')
    logger.info(f'Top features: {sorted(best_metrics["feature_importance"].items(), key=lambda x: x[1], reverse=True)[:5]}')

    return best_metrics


def _prune_weak_features(X: np.ndarray, feature_names: List[str], y: np.ndarray) -> Tuple[np.ndarray, List[str], int]:
    from sklearn.inspection import permutation_importance
    from sklearn.ensemble import RandomForestClassifier

    model = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
    model.fit(X, y)
    result = permutation_importance(model, X, y, n_repeats=10, random_state=42, scoring='accuracy')
    importances = result.importances_mean.tolist()
    max_imp = max(importances) if importances else 1

    keep_mask = [imp >= 0.01 * max_imp for imp in importances]
    X_pruned = X[:, keep_mask]
    names_pruned = [n for n, k in zip(feature_names, keep_mask) if k]
    pruned_count = sum(1 for k in keep_mask if not k)

    return X_pruned, names_pruned, pruned_count


def load_model():
    model_path = os.path.join(MODEL_DIR, 'trading_model.pkl')
    if not os.path.exists(model_path):
        return None, None

    try:
        with open(model_path, 'rb') as f:
            model = pickle.load(f)
    except Exception as e:
        logger.error(f'Failed to load model: {e}')
        return None, None

    metrics_path = METRICS_FILE
    if os.path.exists(metrics_path):
        try:
            with open(metrics_path, 'r') as f:
                metrics = json.load(f)
        except Exception as e:
            logger.error(f'Failed to load model metrics: {e}')
            return model, None
    else:
        metrics = None

    return model, metrics


def predict_signal(features: Dict[str, Any], model=None, metrics=None):
    if model is None:
        model, metrics = load_model()
    if model is None or metrics is None:
        return None

    feature_names = metrics.get('feature_names', [])
    if not feature_names:
        return None

    flat = {}
    for key, value in features.items():
        if isinstance(value, (int, float)) and value is not None:
            flat[key] = value
        elif isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, (int, float)) and v is not None:
                    flat[f'{key}_{k}'] = v

    X = np.array([[flat.get(k, 0) for k in feature_names]])
    prediction = model.predict(X)[0]
    probability = model.predict_proba(X)[0]

    return {
        'prediction': int(prediction),
        'confidence': float(max(probability)),
        'prob_win': float(probability[1]) if len(probability) > 1 else 0.5,
        'prob_loss': float(probability[0]) if len(probability) > 0 else 0.5
    }


def get_model_status():
    model, metrics = load_model()
    if model is None:
        return {'status': 'NO_MODEL', 'message': 'No trained model found'}

    rows = load_training_data()
    return {
        'status': 'READY',
        'metrics': metrics,
        'total_training_rows': len(rows),
        'model_file': os.path.getsize(os.path.join(MODEL_DIR, 'trading_model.pkl'))
    }


if __name__ == '__main__':
    print('Training ML model...')
    metrics = train_model()
    if metrics:
        print(f'Model trained successfully!')
        print(f'Accuracy: {metrics["accuracy"]:.3f}')
        print(f'Precision: {metrics["precision"]:.3f}')
        print(f'F1 Score: {metrics["f1"]:.3f}')
        print(f'Training samples: {metrics["total_samples"]}')
    else:
        print('Not enough training data. Need 50+ rows.')

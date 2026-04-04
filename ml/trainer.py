# ml/trainer.py - ML Training Pipeline
import json
import os
import sys
import pickle
from typing import Dict, List, Any, Optional
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


def train_model(model_type: str = 'random_forest'):
    rows = load_training_data()
    if len(rows) < 50:
        logger.warning(f'Not enough training data: {len(rows)} rows (need 50+)')
        return None

    X_dicts, y, symbols, agents = flatten_features(rows)
    if len(X_dicts) < 50:
        logger.warning(f'Not enough valid features: {len(X_dicts)} (need 50+)')
        return None

    X_array, feature_names = align_features(X_dicts)
    y_array = np.array(y)

    X_train, X_test, y_train, y_test = train_test_split(
        X_array, y_array, test_size=0.2, random_state=42, stratify=y_array
    )

    if model_type == 'gradient_boosting':
        model = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
    else:
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42
        )

    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    metrics = {
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred, zero_division=0),
        'recall': recall_score(y_test, y_pred, zero_division=0),
        'f1': f1_score(y_test, y_pred, zero_division=0),
        'train_size': len(X_train),
        'test_size': len(X_test),
        'total_samples': len(X_array),
        'feature_names': feature_names,
        'feature_importance': dict(zip(feature_names, model.feature_importances_.tolist())) if hasattr(model, 'feature_importances_') else {},
        'trained_at': datetime.now().isoformat(),
        'model_type': model_type
    }

    os.makedirs(MODEL_DIR, exist_ok=True)
    model_path = os.path.join(MODEL_DIR, 'trading_model.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)

    with open(METRICS_FILE, 'w') as f:
        json.dump(metrics, f, indent=2)

    logger.info(f'Model trained: accuracy={metrics["accuracy"]:.3f}, precision={metrics["precision"]:.3f}, f1={metrics["f1"]:.3f}')
    logger.info(f'Top features: {sorted(metrics["feature_importance"].items(), key=lambda x: x[1], reverse=True)[:5]}')

    return metrics


def load_model():
    model_path = os.path.join(MODEL_DIR, 'trading_model.pkl')
    if not os.path.exists(model_path):
        return None, None

    with open(model_path, 'rb') as f:
        model = pickle.load(f)

    metrics_path = METRICS_FILE
    if os.path.exists(metrics_path):
        with open(metrics_path, 'r') as f:
            metrics = json.load(f)
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
        'prob_loss': float(probability[0])
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

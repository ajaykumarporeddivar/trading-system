# ml/strategy_updater.py
import json
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from ml.trainer import train_model, load_model, predict_signal, get_model_status
from core.logger import logger

STRATEGY_CONFIG = 'ml/strategy_adjustments.json'


class StrategyUpdater:
    def __init__(self):
        self.adjustments = self._load_adjustments()

    def _load_adjustments(self):
        if os.path.exists(STRATEGY_CONFIG):
            with open(STRATEGY_CONFIG, 'r') as f:
                return json.load(f)
        return {
            'last_updated': None,
            'agent_adjustments': {},
            'model_accuracy': 0,
            'total_retrains': 0
        }

    def _save_adjustments(self):
        os.makedirs(os.path.dirname(STRATEGY_CONFIG), exist_ok=True)
        with open(STRATEGY_CONFIG, 'w') as f:
            json.dump(self.adjustments, f, indent=2)

    def retrain_and_update(self, min_samples: int = 50):
        from ml.trainer import load_training_data
        rows = load_training_data()

        if len(rows) < min_samples:
            logger.info(f'Not enough data for retraining: {len(rows)} < {min_samples}')
            return False

        metrics = train_model()
        if metrics is None:
            return False

        self.adjustments['last_updated'] = datetime.now().isoformat()
        self.adjustments['model_accuracy'] = metrics['accuracy']
        self.adjustments['total_retrains'] = self.adjustments.get('total_retrains', 0) + 1

        self._analyze_agent_performance(rows)
        self._save_adjustments()

        logger.info(f'Strategy updated: accuracy={metrics["accuracy"]:.3f}, retrain #{self.adjustments["total_retrains"]}')
        return True

    def _analyze_agent_performance(self, rows: List[Dict[str, Any]]):
        agent_stats = {}
        for row in rows:
            agent = row.get('agent', 'unknown')
            if agent not in agent_stats:
                agent_stats[agent] = {'wins': 0, 'losses': 0, 'total_pnl': 0}

            if row.get('label') == 1:
                agent_stats[agent]['wins'] += 1
            else:
                agent_stats[agent]['losses'] += 1

            agent_stats[agent]['total_pnl'] += row.get('pnl_pct', 0)

        for agent, stats in agent_stats.items():
            total = stats['wins'] + stats['losses']
            win_rate = stats['wins'] / total if total > 0 else 0
            avg_pnl = stats['total_pnl'] / total if total > 0 else 0

            adjustment = {
                'win_rate': round(win_rate, 3),
                'avg_pnl': round(avg_pnl, 3),
                'total_trades': total,
                'recommendation': 'INCREASE' if win_rate > 0.55 else 'DECREASE' if win_rate < 0.45 else 'MAINTAIN'
            }

            self.adjustments['agent_adjustments'][agent] = adjustment

    def get_ml_signal(self, features: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        prediction = predict_signal(features)
        if prediction is None:
            return None

        if prediction['prob_win'] > 0.65:
            return {
                'ml_verdict': 'ML_BUY',
                'confidence': prediction['confidence'],
                'prob_win': prediction['prob_win']
            }
        elif prediction['prob_win'] < 0.35:
            return {
                'ml_verdict': 'ML_SELL',
                'confidence': prediction['confidence'],
                'prob_win': prediction['prob_win']
            }

        return {
            'ml_verdict': 'ML_WAIT',
            'confidence': prediction['confidence'],
            'prob_win': prediction['prob_win']
        }

    def should_retrain(self, check_interval: int = 100):
        last_updated = self.adjustments.get('last_updated')
        if last_updated is None:
            return True

        from ml.trainer import load_training_data
        rows = load_training_data()
        return len(rows) >= check_interval


if __name__ == '__main__':
    updater = StrategyUpdater()
    print('Retraining model and updating strategies...')
    success = updater.retrain_and_update()
    if success:
        print(f'Model updated: {updater.adjustments["model_accuracy"]:.3f} accuracy')
        print(f'Agent adjustments:')
        for agent, adj in updater.adjustments['agent_adjustments'].items():
            print(f'  {agent}: {adj["win_rate"]:.1%} win rate -> {adj["recommendation"]}')
    else:
        print('Not enough data for retraining.')

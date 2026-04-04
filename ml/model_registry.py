# ml/model_registry.py
import json
import os
import shutil
import pickle
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.logger import logger

REGISTRY_FILE = 'ml/models/registry.json'
ARCHIVE_DIR = 'ml/models/archive/'


class ModelRegistry:
    def __init__(self):
        self.registry = self._load_registry()

    def _load_registry(self) -> Dict[str, Any]:
        if os.path.exists(REGISTRY_FILE):
            with open(REGISTRY_FILE, 'r') as f:
                return json.load(f)
        return {
            'champion': None,
            'candidates': [],
            'history': [],
            'created_at': datetime.now().isoformat()
        }

    def _save_registry(self):
        os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)
        with open(REGISTRY_FILE, 'w') as f:
            json.dump(self.registry, f, indent=2)

    def register_champion(self, model_path: str, metrics: Dict[str, Any],
                          governance_result: Dict[str, Any] = None) -> str:
        version_id = self._generate_version()

        archive_path = os.path.join(ARCHIVE_DIR, version_id)
        os.makedirs(archive_path, exist_ok=True)

        if os.path.exists(model_path):
            shutil.copy2(model_path, os.path.join(archive_path, 'model.pkl'))
            if os.path.exists(model_path.replace('.pkl', '_metrics.json')):
                shutil.copy2(model_path.replace('.pkl', '_metrics.json'),
                           os.path.join(archive_path, 'metrics.json'))

        old_champion = self.registry.get('champion')
        if old_champion:
            old_champion['demoted_at'] = datetime.now().isoformat()
            self.registry['history'].append(old_champion)

        champion_record = {
            'version_id': version_id,
            'model_path': archive_path,
            'metrics': metrics,
            'governance_result': governance_result,
            'promoted_at': datetime.now().isoformat(),
            'feature_count': len(metrics.get('feature_names', [])),
            'model_type': metrics.get('model_type', 'unknown')
        }

        self.registry['champion'] = champion_record
        self._save_registry()

        logger.info(f'Champion registered: {version_id} ({metrics.get("model_type", "?")}, acc={metrics.get("accuracy", 0):.3f})')
        return version_id

    def register_candidate(self, model_path: str, metrics: Dict[str, Any]) -> str:
        version_id = self._generate_version()
        candidate = {
            'version_id': version_id,
            'model_path': model_path,
            'metrics': metrics,
            'registered_at': datetime.now().isoformat(),
            'status': 'testing'
        }
        self.registry['candidates'].append(candidate)
        self._save_registry()
        logger.info(f'Candidate registered: {version_id}')
        return version_id

    def promote_candidate(self, version_id: str, governance_result: Dict[str, Any]):
        for i, candidate in enumerate(self.registry['candidates']):
            if candidate['version_id'] == version_id:
                candidate['status'] = 'promoted'
                candidate['promoted_at'] = datetime.now().isoformat()
                champion_data = {
                    'version_id': version_id,
                    'model_path': candidate['model_path'],
                    'metrics': candidate['metrics'],
                    'governance_result': governance_result,
                    'promoted_at': datetime.now().isoformat()
                }
                old_champion = self.registry.get('champion')
                if old_champion:
                    old_champion['demoted_at'] = datetime.now().isoformat()
                    self.registry['history'].append(old_champion)
                self.registry['champion'] = champion_data
                self._save_registry()
                logger.info(f'Candidate {version_id} promoted to champion')
                return True
        logger.warning(f'Candidate {version_id} not found')
        return False

    def get_champion(self) -> Optional[Dict[str, Any]]:
        return self.registry.get('champion')

    def get_candidates(self) -> List[Dict[str, Any]]:
        return [c for c in self.registry['candidates'] if c.get('status') == 'testing']

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.registry['history'][-limit:]

    def get_status(self) -> Dict[str, Any]:
        champion = self.registry.get('champion')
        return {
            'champion_version': champion['version_id'] if champion else None,
            'champion_metrics': champion.get('metrics', {}) if champion else {},
            'active_candidates': len(self.get_candidates()),
            'total_history': len(self.registry['history']),
            'timestamp': datetime.now().isoformat()
        }

    def _generate_version(self) -> str:
        n = len(self.registry['history']) + 1
        return f'v{n:03d}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'

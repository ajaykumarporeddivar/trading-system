from typing import Dict, List, Any
from core.logger import logger
from engine.signal_engine import SignalEngine

class SignalAgent:
    def __init__(self):
        self.engine = SignalEngine()
        logger.info('Signal Agent initialized')

    async def analyze(self, indicator_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not indicator_data:
            logger.warning('No indicator data provided')
            return []

        results = self.engine.analyze_all(indicator_data)

        for result in results:
            logger.info(
                f'Signal: {result["symbol"]} -> {result["verdict"]} '
                f'(confidence: {result["confidence"]}%)'
            )

        return results

    async def get_trade_candidates(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        candidates = [s for s in signals if s['verdict'] in ['LONG', 'SHORT']]
        candidates.sort(key=lambda x: x['confidence'], reverse=True)
        logger.info(f'Found {len(candidates)} trade candidates')
        return candidates

    async def generate_summary(self, signals: List[Dict[str, Any]]) -> str:
        summary = 'Signal Analysis Summary:\n'
        for s in signals:
            emoji = '??' if s['verdict'] == 'LONG' else '??' if s['verdict'] == 'SHORT' else '?'
            summary += f'{emoji} {s["symbol"]}: {s["verdict"]} ({s["confidence"]}%)'
            if s['verdict'] != 'NO_TRADE':
                summary += f' - Strong signal'
            summary += '\n'
        return summary.strip()

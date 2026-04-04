# core/regime_classifier.py
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
from core.logger import logger


REGIMES = ['trending', 'mean_reversion', 'high_volatility', 'low_volatility', 'news_noise']

VOL_WINDOW = 60
VOL_HIGH_THRESHOLD = 1.5
VOL_LOW_THRESHOLD = 0.6
ADX_TRENDING = 25
BB_WIDTH_SPIKE = 2.0
VOL_SPIKE_THRESHOLD = 3.0


class RegimeClassifier:
    def __init__(self):
        self._vol_history: List[float] = []
        self._bb_width_history: List[float] = []
        self._volume_history: List[float] = []

    def classify(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        indicators = market_data.get('indicators', market_data)
        current_price = indicators.get('current_price', 0)
        adx = indicators.get('adx_14', 0)
        rsi = indicators.get('rsi_14', 50)
        bb_upper = indicators.get('bb_upper', 0)
        bb_lower = indicators.get('bb_lower', 0)
        bb_middle = indicators.get('bb_middle', 0)
        volume_ratio = indicators.get('volume_ratio', 1.0)
        macd_hist = indicators.get('macd_histogram', 0)
        ema_21 = indicators.get('ema_21', 0)
        ema_50 = indicators.get('ema_50', 0)

        realized_vol = self._compute_realized_vol(current_price, indicators)
        median_vol = self._get_median_vol()
        vol_ratio = realized_vol / median_vol if median_vol > 0 else 1.0

        bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0
        self._bb_width_history.append(bb_width)
        if len(self._bb_width_history) > VOL_WINDOW:
            self._bb_width_history = self._bb_width_history[-VOL_WINDOW:]
        median_bb_width = np.median(self._bb_width_history) if self._bb_width_history else bb_width
        bb_width_ratio = bb_width / median_bb_width if median_bb_width > 0 else 1.0

        self._volume_history.append(volume_ratio)
        if len(self._volume_history) > VOL_WINDOW:
            self._volume_history = self._volume_history[-VOL_WINDOW:]
        median_volume = np.median(self._volume_history) if self._volume_history else 1.0

        scores = self._score_regimes(adx, rsi, vol_ratio, bb_width_ratio, volume_ratio, macd_hist, ema_21, ema_50, current_price)

        regime = max(scores, key=scores.get)
        confidence = scores[regime]
        total = sum(scores.values())
        confidence = confidence / total if total > 0 else 0.2

        switch_prob = self._compute_switch_probability(regime, scores)

        result = {
            'regime': regime,
            'confidence': round(confidence, 3),
            'switch_probability': round(switch_prob, 3),
            'regime_scores': {k: round(v, 3) for k, v in scores.items()},
            'metrics': {
                'realized_vol': round(realized_vol, 6),
                'vol_ratio': round(vol_ratio, 3),
                'bb_width': round(bb_width, 6),
                'bb_width_ratio': round(bb_width_ratio, 3),
                'adx': adx,
                'rsi': rsi,
                'volume_ratio': volume_ratio
            },
            'timestamp': datetime.now().isoformat()
        }

        logger.debug(f'Regime: {regime} (conf={confidence:.2f}, vol_ratio={vol_ratio:.2f}, adx={adx})')
        return result

    def _score_regimes(self, adx, rsi, vol_ratio, bb_width_ratio, volume_ratio, macd_hist, ema_21, ema_50, price) -> Dict[str, float]:
        scores = {r: 0.1 for r in REGIMES}

        ema_diff = abs(ema_21 - ema_50) / ema_50 if ema_50 > 0 else 0
        trend_strength = min(1.0, ema_diff * 20)

        if adx > ADX_TRENDING and trend_strength > 0.3:
            scores['trending'] += 0.5 + trend_strength * 0.3
            if abs(macd_hist) > 0:
                scores['trending'] += 0.1

        if adx < 20 and bb_width_ratio < 0.8:
            scores['mean_reversion'] += 0.4
            if 35 < rsi < 65:
                scores['mean_reversion'] += 0.3
            if vol_ratio < 1.0:
                scores['mean_reversion'] += 0.2

        if vol_ratio > VOL_HIGH_THRESHOLD:
            scores['high_volatility'] += 0.5 + (vol_ratio - VOL_HIGH_THRESHOLD) * 0.3
            if bb_width_ratio > BB_WIDTH_SPIKE:
                scores['high_volatility'] += 0.2

        if vol_ratio < VOL_LOW_THRESHOLD:
            scores['low_volatility'] += 0.5 + (VOL_LOW_THRESHOLD - vol_ratio) * 0.5
            if bb_width_ratio < 0.7:
                scores['low_volatility'] += 0.2

        if volume_ratio > VOL_SPIKE_THRESHOLD and adx < 25:
            scores['news_noise'] += 0.4 + (volume_ratio - VOL_SPIKE_THRESHOLD) * 0.1
            if bb_width_ratio > 1.5:
                scores['news_noise'] += 0.2
            if abs(macd_hist) > 0 and abs(macd_hist) < 50:
                scores['news_noise'] += 0.1

        return scores

    def _compute_realized_vol(self, price: float, indicators: Dict[str, Any]) -> float:
        atr = indicators.get('atr_14', indicators.get('atr', 0))
        if atr > 0 and price > 0:
            return atr / price
        bb_upper = indicators.get('bb_upper', 0)
        bb_lower = indicators.get('bb_lower', 0)
        if bb_upper > 0 and bb_lower > 0:
            return (bb_upper - bb_lower) / (2 * price) if price > 0 else 0
        return 0.02

    def _get_median_vol(self) -> float:
        if len(self._vol_history) < 10:
            return 0.02
        return np.median(self._vol_history[-VOL_WINDOW:])

    def _compute_switch_probability(self, current_regime: str, scores: Dict[str, float]) -> float:
        total = sum(scores.values())
        if total == 0:
            return 0.0
        current_score = scores[current_regime] / total
        runner_up = sorted(scores.values(), reverse=True)[1] / total if len(scores) > 1 else 0
        return max(0, min(1, 1 - (current_score - runner_up)))

    def update_vol_history(self, vol: float):
        self._vol_history.append(vol)
        if len(self._vol_history) > VOL_WINDOW * 2:
            self._vol_history = self._vol_history[-VOL_WINDOW:]

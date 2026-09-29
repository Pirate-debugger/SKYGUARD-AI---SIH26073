"""
Machine Learning Anomaly Detector for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Uses scikit-learn Isolation Forest on multi-dimensional feature space:
- Core parameters (T, P, RH)
- Temporal rates of change
- Spatial neighborhood relative deviations
- Multivariate Mahalanobis metric
Provides anomaly score, normalized confidence, and feature attribution contributions.
"""

from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from sklearn.ensemble import IsolationForest
from app.models.schemas import MLEvidence


FEATURE_NAMES = [
    "temperature",
    "pressure",
    "humidity",
    "temp_rate_of_change",
    "pres_rate_of_change",
    "hum_rate_of_change",
    "temp_spatial_diff",
    "pres_spatial_diff",
    "hum_spatial_diff",
    "mahalanobis_dist"
]


class MLAnomalyDetector:
    def __init__(self, random_state: int = 42):
        self.feature_names = FEATURE_NAMES
        self.model_name = "IsolationForest-v1.4.0"
        self.model = IsolationForest(
            n_estimators=100,
            contamination=0.04,  # Expected ~4% anomaly rate in rigorous AWS streams
            random_state=random_state,
            n_jobs=-1
        )
        self.is_trained = False
        self._feature_means: np.ndarray = np.zeros(len(FEATURE_NAMES))
        self._feature_stds: np.ndarray = np.ones(len(FEATURE_NAMES))
        
        # Pre-train on synthetic normal meteorological baseline so model is immediately operational
        self._pretrain_baseline()

    def _pretrain_baseline(self):
        """Generates realistic normal surface observations with diurnal cycle and natural weather shifts."""
        np.random.seed(42)
        n_samples = 3000
        
        # Realistic surface distributions
        t_base = np.random.normal(loc=28.0, scale=6.0, size=n_samples)
        # Pressure negatively correlated with temperature slightly
        p_base = np.random.normal(loc=1010.0, scale=8.0, size=n_samples) - 0.2 * (t_base - 28.0)
        # Humidity negatively correlated with temperature
        rh_base = np.clip(np.random.normal(loc=65.0, scale=14.0, size=n_samples) - 1.2 * (t_base - 28.0), 10.0, 98.0)
        
        # Normal rates of change (gradual diurnal changes, < 0.2°C/min)
        t_rate = np.abs(np.random.exponential(scale=0.05, size=n_samples))
        p_rate = np.abs(np.random.exponential(scale=0.03, size=n_samples))
        rh_rate = np.abs(np.random.exponential(scale=0.15, size=n_samples))
        
        # Spatial differences among close stations (mostly < 1.5°C, < 1.0 hPa, < 5%)
        t_spat = np.random.normal(loc=0.0, scale=0.8, size=n_samples)
        p_spat = np.random.normal(loc=0.0, scale=0.5, size=n_samples)
        rh_spat = np.random.normal(loc=0.0, scale=2.5, size=n_samples)
        
        # Mahalanobis distances (typically between 0.5 and 2.5)
        m_dist = np.random.gamma(shape=2.0, scale=0.8, size=n_samples)
        
        X = np.column_stack([
            t_base, p_base, rh_base,
            t_rate, p_rate, rh_rate,
            t_spat, p_spat, rh_spat,
            m_dist
        ])
        
        self.fit(X)

    def fit(self, X: np.ndarray):
        """Fits the Isolation Forest and computes feature scales for attribution."""
        self._feature_means = np.mean(X, axis=0)
        self._feature_stds = np.std(X, axis=0)
        self._feature_stds[self._feature_stds < 1e-4] = 1.0
        
        self.model.fit(X)
        self.is_trained = True

    def extract_features(
        self,
        temperature: Optional[float],
        pressure: Optional[float],
        humidity: Optional[float],
        rates_of_change: Dict[str, float],
        spatial_diffs: Dict[str, float],
        mahalanobis_dist: float
    ) -> np.ndarray:
        """Assembles the feature vector from telemetry and upstream engine metrics."""
        t = temperature if temperature is not None else float(self._feature_means[0])
        p = pressure if pressure is not None else float(self._feature_means[1])
        rh = humidity if humidity is not None else float(self._feature_means[2])
        
        t_rate = rates_of_change.get("temperature", 0.0)
        p_rate = rates_of_change.get("pressure", 0.0)
        rh_rate = rates_of_change.get("humidity", 0.0)
        
        t_spat = spatial_diffs.get("temperature", 0.0)
        p_spat = spatial_diffs.get("pressure", 0.0)
        rh_spat = spatial_diffs.get("humidity", 0.0)
        
        return np.array([
            t, p, rh,
            t_rate, p_rate, rh_rate,
            t_spat, p_spat, rh_spat,
            mahalanobis_dist
        ], dtype=float)

    def predict(self, feature_vector: np.ndarray) -> MLEvidence:
        if not self.is_trained:
            return MLEvidence(
                is_anomaly=False,
                anomaly_score=0.0,
                confidence=0.5,
                feature_contributions={},
                model_name=self.model_name
            )

        X = feature_vector.reshape(1, -1)
        
        # decision_function returns negative values for anomalies, positive for inliers
        raw_score = float(self.model.decision_function(X)[0])
        pred_label = int(self.model.predict(X)[0]) # -1 = anomaly, 1 = normal
        
        is_anomaly = (pred_label == -1)
        
        # Calculate feature contributions by measuring standardized distance from normal baseline
        standardized_deviations = np.abs((feature_vector - self._feature_means) / self._feature_stds)
        total_dev = float(np.sum(standardized_deviations))
        
        contributions: Dict[str, float] = {}
        if total_dev > 1e-4:
            for name, dev in zip(self.feature_names, standardized_deviations):
                # Percentage of total standardized deviation
                contributions[name] = round(float(dev / total_dev), 3)
                
        # Calibrated normalized anomaly index [0.0..1.0]
        # raw_score > 0 is inlier/normal; raw_score < 0 is outlier/anomalous
        # Linear calibration around boundary: 0.0 -> 0.50, +0.25 -> 0.0, -0.25 -> 1.0
        normalized_score = float(np.clip(0.5 - 2.0 * raw_score, 0.0, 1.0))

        # Confidence score: maps raw decision function (-0.35 to +0.25) to [0.5, 0.99]
        if is_anomaly:
            # The more negative, the more anomalous and higher the confidence
            conf = min(0.99, max(0.60, 0.60 + abs(raw_score) * 2.0))
        else:
            # The more positive, the more typical
            conf = min(0.95, max(0.50, 0.50 + raw_score * 1.5))

        return MLEvidence(
            is_anomaly=is_anomaly,
            raw_decision_score=round(raw_score, 4),
            normalized_anomaly_score=round(normalized_score, 4),
            anomaly_score=round(normalized_score, 4),
            confidence=round(conf, 3),
            feature_contributions=contributions,
            model_name=self.model_name
        )

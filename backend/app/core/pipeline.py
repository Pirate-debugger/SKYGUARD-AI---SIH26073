"""
Pipeline Orchestrator for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Orchestrates the complete vertical anomaly intelligence pipeline:
AWS Reading
  -> Data Quality Engine
  -> Temporal Analysis
  -> Multivariate Consistency
  -> Spatial Consistency
  -> Machine Learning Inference
  -> Anomaly Decision Fusion
  -> Root Cause Classification
  -> Sensor Health Tracking
  -> Corrected Value Estimation (Imputation)
"""

import uuid
from typing import Optional, Tuple, Dict, Any, List
from app.config import VERSION_INFO
from app.models.schemas import (
    RawReading,
    ProcessedReading,
    AlertRecord,
    SensorHealthSummary,
    DecisionClassification,
    ProbableCause,
    SeverityLevel,
    MaintenanceRecommendation
)
from app.core.data_quality import DataQualityEngine
from app.core.temporal_engine import TemporalEngine
from app.core.multivariate_engine import MultivariateConsistencyEngine
from app.core.spatial_engine import SpatialConsistencyEngine
from app.core.ml_detector import MLAnomalyDetector
from app.core.fusion_engine import AnomalyFusionEngine
from app.core.root_cause import RootCauseClassifier
from app.core.sensor_health import SensorHealthEngine
from app.core.imputation import ImputationEngine


class SkyGuardPipeline:
    def __init__(self):
        self.dq_engine = DataQualityEngine()
        self.temporal_engine = TemporalEngine()
        self.multivariate_engine = MultivariateConsistencyEngine()
        self.spatial_engine = SpatialConsistencyEngine()
        self.ml_detector = MLAnomalyDetector()
        self.fusion_engine = AnomalyFusionEngine()
        self.root_cause_classifier = RootCauseClassifier()
        self.health_engine = SensorHealthEngine()
        self.imputation_engine = ImputationEngine()
        
        # In-memory alert store and history
        self.alerts: List[AlertRecord] = []
        self.processed_history: Dict[str, List[ProcessedReading]] = {} # station_id -> list of readings
        self.prev_raw_readings: Dict[str, RawReading] = {}

    def process_reading(self, reading: RawReading) -> Tuple[ProcessedReading, Optional[AlertRecord]]:
        reading_id = str(uuid.uuid4())
        prev_reading = self.prev_raw_readings.get(reading.station_id)

        # 1. Data Quality Analysis
        dq_result = self.dq_engine.validate_reading(reading)

        # 2. Temporal Analysis
        temporal_evidence = self.temporal_engine.analyze(reading)
        
        # 3. Multivariate Consistency Analysis
        multivariate_evidence = self.multivariate_engine.analyze(reading, prev_reading)

        # 4. Spatial Consistency Analysis
        spatial_evidence = self.spatial_engine.analyze(reading)

        # 5. ML Anomaly Detection (Isolation Forest)
        feature_vector = self.ml_detector.extract_features(
            temperature=reading.temperature,
            pressure=reading.pressure,
            humidity=reading.humidity,
            rates_of_change=temporal_evidence.rates_of_change,
            spatial_diffs=spatial_evidence.relative_deviations,
            mahalanobis_dist=multivariate_evidence.mahalanobis_distance
        )
        ml_evidence = self.ml_detector.predict(feature_vector)

        # 6. Decision Fusion Layer
        buffer = self.temporal_engine.get_or_create_buffer(reading.station_id)
        decision, severity, confidence, explanation = self.fusion_engine.fuse_signals(
            dq=dq_result,
            temporal=temporal_evidence,
            multivariate=multivariate_evidence,
            spatial=spatial_evidence,
            ml=ml_evidence,
            history_len=len(buffer.history)
        )

        # 7. Root-Cause Classification
        probable_cause, rc_conf, supporting_signals = self.root_cause_classifier.classify_root_cause(
            decision=decision,
            dq=dq_result,
            temporal=temporal_evidence,
            multivariate=multivariate_evidence,
            spatial=spatial_evidence,
            ml=ml_evidence
        )

        # 8. Sensor Health Update
        health_summary = self.health_engine.update_and_get_health(
            station_id=reading.station_id,
            decision=decision,
            probable_cause=probable_cause,
            ts=reading.timestamp
        )

        # 9. Corrected Value Estimation (Imputation)
        imputed_values = {}
        if decision in (DecisionClassification.SENSOR_ANOMALY, DecisionClassification.COMMUNICATION_ERROR):
            flagged = dq_result.flagged_parameters or []
            if temporal_evidence.spike_detected or temporal_evidence.drop_detected:
                for p, z in temporal_evidence.robust_z_scores.items():
                    if abs(z) >= 3.0 and p not in flagged:
                        flagged.append(p)
            if not flagged and not spatial_evidence.is_consistent:
                for p, diff in spatial_evidence.relative_deviations.items():
                    if abs(diff) > 3.0 and p not in flagged:
                        flagged.append(p)
            if not flagged:
                flagged = ["temperature"]

            history_dict = {
                "temperature": buffer.get_parameter_series("temperature"),
                "pressure": buffer.get_parameter_series("pressure"),
                "humidity": buffer.get_parameter_series("humidity")
            }
            imputed_values = self.imputation_engine.estimate_corrected_values(
                reading=reading,
                spatial=spatial_evidence,
                flagged_params=flagged,
                temporal_buffer_history=history_dict
            )

        # 10. Assemble ProcessedReading
        processed = ProcessedReading(
            reading_id=reading_id,
            station_id=reading.station_id,
            timestamp=reading.timestamp,
            temperature=reading.temperature,
            pressure=reading.pressure,
            humidity=reading.humidity,
            data_quality=dq_result,
            temporal_evidence=temporal_evidence,
            multivariate_evidence=multivariate_evidence,
            spatial_evidence=spatial_evidence,
            ml_evidence=ml_evidence,
            decision=decision,
            probable_cause=probable_cause,
            severity=severity,
            confidence=confidence,
            explanation=explanation,
            imputed_values=imputed_values,
            model_version=VERSION_INFO.model_version,
            ruleset_version=VERSION_INFO.ruleset_version,
            feature_version=VERSION_INFO.feature_version
        )

        # 11. Generate Alert if abnormal
        alert = None
        if decision not in (DecisionClassification.NORMAL, DecisionClassification.INSUFFICIENT_EVIDENCE):
            flagged = list(set(
                dq_result.flagged_parameters +
                [p for p, z in temporal_evidence.robust_z_scores.items() if abs(z) >= 3.0] +
                [p for p, diff in spatial_evidence.relative_deviations.items() if abs(diff) >= 3.0]
            )) or ["temperature"]
            
            observed = {
                "temperature": reading.temperature,
                "pressure": reading.pressure,
                "humidity": reading.humidity
            }
            expected = {
                "temperature": spatial_evidence.neighbor_medians.get("temperature", temporal_evidence.rolling_means.get("temperature")),
                "pressure": spatial_evidence.neighbor_medians.get("pressure", temporal_evidence.rolling_means.get("pressure")),
                "humidity": spatial_evidence.neighbor_medians.get("humidity", temporal_evidence.rolling_means.get("humidity"))
            }
            deviations = {
                "temperature": spatial_evidence.relative_deviations.get("temperature"),
                "pressure": spatial_evidence.relative_deviations.get("pressure"),
                "humidity": spatial_evidence.relative_deviations.get("humidity")
            }

            alert = AlertRecord(
                alert_id=str(uuid.uuid4())[:8],
                station_id=reading.station_id,
                timestamp=reading.timestamp,
                decision=decision,
                probable_cause=probable_cause,
                severity=severity,
                confidence=confidence,
                flagged_parameters=flagged,
                observed_values=observed,
                expected_values=expected,
                deviations=deviations,
                explanation=explanation,
                recommended_action=health_summary.maintenance_recommendation
            )
            self.alerts.append(alert)

        # Store in rolling processed history
        if reading.station_id not in self.processed_history:
            self.processed_history[reading.station_id] = []
        self.processed_history[reading.station_id].append(processed)
        if len(self.processed_history[reading.station_id]) > 100:
            self.processed_history[reading.station_id].pop(0)

        # Store for consecutive comparisons
        self.prev_raw_readings[reading.station_id] = reading

        return processed, alert

"""
Pipeline Orchestrator for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Orchestrates the synchronized multi-layered intelligence pipeline:
- Synchronized same-timestamp spatial snapshots (order-invariant)
- Strict Anti-Leakage: pre-current temporal baselines, post-imputation buffer commit
- Multi-signal decision fusion & evidence attribution
- Sensor health tracking & predictive degradation
- Non-destructive Spatial IDW Imputation
"""

import uuid
from typing import Optional, Tuple, Dict, Any, List
from collections import defaultdict
from app.config import VERSION_INFO
from app.models.schemas import (
    RawReading,
    ProcessedReading,
    AlertRecord,
    SensorHealthSummary,
    DecisionClassification,
    ProbableCause,
    SeverityLevel,
    MaintenanceRecommendation,
    EvidenceStrength
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

        # Pre-register default stations and initialize health trackers
        from app.simulator.generator import DEFAULT_STATIONS
        for st in DEFAULT_STATIONS:
            self.spatial_engine.register_station(st)
            self.health_engine.get_or_create_tracker(st.station_id)

    def process_batch(self, readings: List[RawReading]) -> List[Tuple[ProcessedReading, Optional[AlertRecord]]]:
        """
        Synchronized same-timestamp batch processing.
        Groups readings by timestamp so that all stations for timestamp t share the exact
        same spatial snapshot, guaranteeing processing-order invariance!
        """
        by_timestamp: Dict[str, List[RawReading]] = defaultdict(list)
        for r in readings:
            by_timestamp[r.timestamp].append(r)

        batch_results: List[Tuple[ProcessedReading, Optional[AlertRecord]]] = []

        # Process chronologically
        sorted_timestamps = sorted(by_timestamp.keys())
        for ts in sorted_timestamps:
            t_readings = by_timestamp[ts]
            # Construct synchronized spatial snapshot for this timestamp
            snapshot = {r.station_id: r for r in t_readings}
            
            # Intermediate storage before committing temporal history
            step_evaluations = []

            for reading in t_readings:
                reading_id = str(uuid.uuid4())
                prev_reading = self.prev_raw_readings.get(reading.station_id)

                # 1. Data Quality Analysis
                dq_result = self.dq_engine.validate_reading(reading)

                # 2. Temporal Analysis (strictly against pre-current history; not committed yet)
                temporal_evidence = self.temporal_engine.analyze(reading)
                
                # 3. Multivariate Consistency Analysis
                multivariate_evidence = self.multivariate_engine.analyze(reading, prev_reading)

                # 4. Spatial Consistency Analysis (evaluated using same-timestamp snapshot)
                spatial_evidence = self.spatial_engine.analyze(reading, snapshot=snapshot)

                # 5. ML Anomaly Detection (Isolation Forest on standardized residual features)
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
                decision, severity, confidence, ev_strength, explanation = self.fusion_engine.fuse_signals(
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
                # Anti-leakage: buffer.history does NOT contain current reading!
                imputed_values = {}
                if decision in (DecisionClassification.SENSOR_ANOMALY, DecisionClassification.COMMUNICATION_ERROR):
                    flagged = dq_result.flagged_parameters or []
                    if temporal_evidence.spike_detected or temporal_evidence.drop_detected:
                        for p, z in temporal_evidence.robust_z_scores.items():
                            if abs(z) >= 3.0 and p not in flagged:
                                flagged.append(p)
                    if not flagged and (temporal_evidence.spike_detected or temporal_evidence.drop_detected):
                        flagged = ["temperature"]

                    if flagged:
                        temporal_history = {
                            "temperature": buffer.get_parameter_series("temperature"),
                            "pressure": buffer.get_parameter_series("pressure"),
                            "humidity": buffer.get_parameter_series("humidity")
                        }
                        neighbor_distances = self.spatial_engine.find_nearest_neighbors(reading.station_id)
                        imputed_values = self.imputation_engine.estimate_corrected_values(
                            reading=reading,
                            spatial=spatial_evidence,
                            flagged_params=flagged,
                            temporal_buffer_history=temporal_history,
                            neighbor_distances=neighbor_distances,
                            neighbor_readings=snapshot,
                            stations_dict=self.spatial_engine.stations
                        )

                # Assemble ProcessedReading
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
                    evidence_strength=ev_strength,
                    explanation=explanation,
                    imputed_values=imputed_values,
                    model_version=VERSION_INFO.model_version,
                    ruleset_version=VERSION_INFO.ruleset_version,
                    feature_version=VERSION_INFO.feature_version
                )

                # Assemble AlertRecord if an operational anomaly or genuine weather event is flagged
                alert: Optional[AlertRecord] = None
                if decision in (DecisionClassification.SENSOR_ANOMALY, DecisionClassification.WEATHER_EVENT, DecisionClassification.COMMUNICATION_ERROR, DecisionClassification.SENSOR_DEGRADATION):
                    observed_map = {"temperature": reading.temperature, "pressure": reading.pressure, "humidity": reading.humidity}
                    expected_map = {}
                    deviation_map = {}
                    
                    for p in ["temperature", "pressure", "humidity"]:
                        med = spatial_evidence.neighbor_medians.get(p)
                        if med is not None:
                            expected_map[p] = med
                            obs = observed_map.get(p)
                            if obs is not None:
                                deviation_map[p] = round(obs - med, 2)

                    alert = AlertRecord(
                        alert_id=str(uuid.uuid4())[:8],
                        station_id=reading.station_id,
                        timestamp=reading.timestamp,
                        decision=decision,
                        probable_cause=probable_cause,
                        severity=severity,
                        confidence=confidence,
                        evidence_strength=ev_strength,
                        flagged_parameters=dq_result.flagged_parameters or (["temperature"] if temporal_evidence.spike_detected else []),
                        observed_values=observed_map,
                        expected_values=expected_map,
                        deviations=deviation_map,
                        explanation=explanation,
                        recommended_action=health_summary.maintenance_recommendation
                    )
                    self.alerts.append(alert)

                step_evaluations.append((reading, processed, alert))

            # POST-EVALUATION COMMIT:
            # Now that all readings at timestamp t have been analyzed and imputed,
            # commit them to temporal buffers and update spatial baseline
            for reading, processed, alert in step_evaluations:
                self.temporal_engine.commit_reading(reading)
                self.prev_raw_readings[reading.station_id] = reading
                
                if reading.station_id not in self.processed_history:
                    self.processed_history[reading.station_id] = []
                self.processed_history[reading.station_id].append(processed)
                if len(self.processed_history[reading.station_id]) > 50:
                    self.processed_history[reading.station_id].pop(0)

                batch_results.append((processed, alert))

            # Update spatial engine synchronized snapshot
            self.spatial_engine.update_snapshot(snapshot)

        return batch_results

    def process_reading(self, reading: RawReading) -> Tuple[ProcessedReading, Optional[AlertRecord]]:
        """Single reading wrapper: delegates to process_batch."""
        results = self.process_batch([reading])
        return results[0]

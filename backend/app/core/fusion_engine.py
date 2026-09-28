"""
Decision Fusion Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

THE CORE INTELLIGENCE:
Distinguishes Genuine Meteorological Events from Sensor & Data Anomalies.

Inputs:
- Data Quality Signal
- Temporal Signal
- Multivariate Signal
- Spatial Signal
- Machine Learning (Isolation Forest) Signal

Outputs:
- Decision: NORMAL, WEATHER_EVENT, SENSOR_ANOMALY, COMMUNICATION_ERROR, SENSOR_DEGRADATION, INSUFFICIENT_EVIDENCE
- Evidence-based Confidence Score (0.0 to 1.0)
- Severity Level (LOW, MEDIUM, HIGH, CRITICAL)
- Comprehensive Explainable Reasoning
"""

from typing import Tuple, Dict, Any, List
from app.models.schemas import (
    DataQualityResult,
    DataQualityStatus,
    TemporalEvidence,
    MultivariateEvidence,
    SpatialEvidence,
    MLEvidence,
    DecisionClassification,
    SeverityLevel
)


class AnomalyFusionEngine:
    def __init__(self):
        pass

    def fuse_signals(
        self,
        dq: DataQualityResult,
        temporal: TemporalEvidence,
        multivariate: MultivariateEvidence,
        spatial: SpatialEvidence,
        ml: MLEvidence,
        history_len: int = 24
    ) -> Tuple[DecisionClassification, SeverityLevel, float, str]:
        """
        Fuses multi-layered signals to produce a deterministic, explainable classification.
        Returns: (decision, severity, confidence, explanation)
        """
        
        # 1. Communication / Data Corruption Checks (Data Quality First)
        if dq.status == DataQualityStatus.INVALID:
            reasons = "; ".join(dq.issues)
            conf = 0.98
            severity = SeverityLevel.CRITICAL if "Physically impossible" in reasons else SeverityLevel.HIGH
            explanation = (
                f"Data Corruption / Hardware Failure: {reasons}. "
                "Raw readings violate physical meteorological boundary conditions."
            )
            return DecisionClassification.COMMUNICATION_ERROR, severity, conf, explanation

        if dq.status == DataQualityStatus.MISSING:
            conf = 0.95
            severity = SeverityLevel.MEDIUM
            explanation = (
                f"Communication Drop / Telemetry Loss: Missing sensor parameters ({', '.join(dq.flagged_parameters)})."
            )
            return DecisionClassification.COMMUNICATION_ERROR, severity, conf, explanation

        # 2. Frozen Sensor Check
        if temporal.freeze_detected:
            frozen_params = [p for p, steps in temporal.frozen_duration_steps.items() if steps >= 4] or ["sensor"]
            conf = 0.94
            severity = SeverityLevel.HIGH
            max_steps = max(temporal.frozen_duration_steps.values()) if temporal.frozen_duration_steps else 4
            explanation = (
                f"Sensor Hardware Malfunction (Frozen Values): {', '.join(frozen_params)} sensor remained static "
                f"without micro-fluctuations over {max_steps} intervals. "
                "Atmospheric surface turbulence precludes zero-variance readings over extended periods."
            )
            return DecisionClassification.SENSOR_ANOMALY, severity, conf, explanation

        # 3. Calibration Drift / Sensor Degradation Check
        if temporal.drift_detected:
            # Distinguish calibration drift from natural diurnal warming:
            # A true sensor calibration drift diverges from neighboring stations (Delta >= 1.0).
            max_spatial_dev = max([abs(v) for v in spatial.relative_deviations.values()] or [0.0])
            if max_spatial_dev >= 1.0 or not spatial.is_consistent:
                conf = 0.92
                severity = SeverityLevel.MEDIUM
                explanation = (
                    "Sensor Degradation Pattern (Creeping Calibration Drift): Station displays continuous "
                    f"monotonic drift ({temporal.explanation}) diverging from regional baseline (Delta={max_spatial_dev:+.1f}). "
                    "Indicates gradual sensor transducer or amplifier decay."
                )
                return DecisionClassification.SENSOR_DEGRADATION, severity, conf, explanation

        # 4. Regional Weather Event vs Isolated Sensor Anomaly
        # Count positive corroborating anomaly signals
        temporal_alert = temporal.spike_detected or temporal.drop_detected
        spatial_outlier = not spatial.is_consistent
        multivariate_discord = not multivariate.is_consistent
        ml_anomaly = ml.is_anomaly

        # CASE A: Regional Weather Event Corroboration
        # Only evaluate as weather event if there is an elevated shift or alert corroborated across neighbors
        if spatial.regional_event_detected and (temporal_alert or ml_anomaly or spatial_outlier):
            conf = 0.92
            severity = SeverityLevel.MEDIUM
            explanation = (
                "Genuine Meteorological Event: Rapid atmospheric change detected, but confirmed by "
                f"{spatial.neighbor_count} neighboring stations ({spatial.explanation}). "
                "Multi-station coherence proves regional weather phenomenon (e.g. convective storm / heatburst / frontal passage)."
            )
            return DecisionClassification.WEATHER_EVENT, severity, conf, explanation

        # If spatial neighbors report similar high/low values within normal tolerance
        max_spat_dev = max([abs(v) for v in spatial.relative_deviations.values()] or [0.0])
        if temporal_alert and not temporal.drift_detected and spatial.is_consistent and max_spat_dev < 2.5 and spatial.neighbor_count >= 2:
            # The station shifted, but nearby stations are also in similar range
            conf = 0.86
            severity = SeverityLevel.LOW
            explanation = (
                f"Regional Weather Fluctuation: Local parameter change ({temporal.explanation}) is corroborated "
                f"by neighboring stations (relative deviation within {max_spat_dev:.1f}). "
                "Classified as genuine atmospheric variation."
            )
            return DecisionClassification.WEATHER_EVENT, severity, conf, explanation

        # CASE B: Isolated Sensor Anomaly (Multi-Signal Corroboration)
        # Abrupt spike + Isolated Spatial Outlier OR Multivariate Inconsistency + Spatial Outlier
        # Must have local defect evidence (temporal spike/drop OR thermodynamic violation).
        # A station at quiet baseline whose neighbors entered a storm should NOT be blamed!
        has_local_fault = temporal_alert or multivariate_discord or (dq.status != DataQualityStatus.VALID)
        if spatial_outlier and has_local_fault:
            # Calculate evidence-based confidence
            evidence_points = 0.0
            evidence_items = []
            
            if spatial_outlier:
                evidence_points += 0.35
                evidence_items.append(f"Spatial Disagreement ({spatial.explanation})")
            if temporal_alert:
                evidence_points += 0.30
                evidence_items.append(f"Abrupt Temporal Deviation ({temporal.explanation})")
            if multivariate_discord:
                evidence_points += 0.20
                evidence_items.append(f"Thermodynamic/Multivariate Inconsistency ({multivariate.explanation})")
            if ml_anomaly:
                evidence_points += 0.15
                top_feat = list(ml.feature_contributions.keys())[:2] if ml.feature_contributions else []
                evidence_items.append(f"ML Isolation Score ({ml.anomaly_score:.3f}, primary drivers: {', '.join(top_feat)})")

            conf = round(min(0.99, max(0.70, evidence_points + 0.10)), 2)
            
            # Severity determined by magnitude of spatial and temporal divergence
            max_spat_dev = max([abs(v) for v in spatial.relative_deviations.values()] or [0])
            if max_spat_dev > 15.0 or temporal.spike_detected:
                severity = SeverityLevel.CRITICAL if max_spat_dev > 25.0 else SeverityLevel.HIGH
            else:
                severity = SeverityLevel.MEDIUM

            explanation = (
                f"Sensor Anomaly Detected: Station observation is uncorroborated by the observation network. "
                f"Supporting evidence: 1) {'; 2) '.join(evidence_items)}. "
                "Lack of spatial consensus and thermodynamic discord confirms observation-system failure."
            )
            return DecisionClassification.SENSOR_ANOMALY, severity, conf, explanation

        # CASE C: Multivariate Inconsistency Alone (without spatial neighbors)
        if multivariate_discord and not spatial_outlier:
            if spatial.neighbor_count == 0:
                conf = 0.72
                severity = SeverityLevel.MEDIUM
                explanation = (
                    f"Probable Sensor Discrepancy: {multivariate.explanation}. "
                    "However, neighbor stations are unavailable for spatial cross-validation."
                )
                return DecisionClassification.SENSOR_ANOMALY, severity, conf, explanation
            else:
                # Neighbors agree with the values, so it might be an unusual microclimate
                conf = 0.60
                severity = SeverityLevel.LOW
                explanation = (
                    f"Marginal Multivariate Anomaly: {multivariate.explanation}, but spatial neighbors observe similar ranges. "
                    "Marked for watch."
                )
                return DecisionClassification.NORMAL, severity, conf, explanation

        # CASE D: Insufficient Evidence Check
        if history_len < 3 and spatial.neighbor_count == 0:
            if temporal_alert or ml_anomaly:
                conf = 0.45
                severity = SeverityLevel.LOW
                explanation = (
                    "Insufficient Evidence: Reading appears unusual, but station history is brief (<3 timesteps) "
                    "and no spatial neighbors are available within 150 km to corroborate."
                )
                return DecisionClassification.INSUFFICIENT_EVIDENCE, severity, conf, explanation

        # CASE E: Default Normal Operating State
        conf = 0.95 if not ml_anomaly else 0.80
        severity = SeverityLevel.LOW
        explanation = "All parameters exhibit natural diurnal variability, thermodynamic consistency, and regional consensus."
        return DecisionClassification.NORMAL, severity, conf, explanation

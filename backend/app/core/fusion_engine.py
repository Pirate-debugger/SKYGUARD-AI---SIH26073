"""
Decision Fusion Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

THE CORE INTELLIGENCE:
Determines: "Did the atmosphere change, or did the observation system fail?"

Inputs:
- Data Quality Signal (Physical & operational bounds)
- Temporal Signal (Instantaneous jump, short-term MAD, CUSUM change-point, freeze, drift)
- Multivariate Signal (Thermodynamic dewpoint limit, dynamic coupling, statistical Mahalanobis)
- Spatial Signal (Elevation-adjusted neighborhood consensus, directional agreement ratio)
- Machine Learning (Isolation Forest on standardized residual features)

Outputs:
- Decision: NORMAL, WEATHER_EVENT, SENSOR_ANOMALY, COMMUNICATION_ERROR, SENSOR_DEGRADATION, INSUFFICIENT_EVIDENCE
- Evidence Strength: LOW, MEDIUM, HIGH
- Severity: LOW, MEDIUM, HIGH, CRITICAL
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
    SeverityLevel,
    EvidenceStrength
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
    ) -> Tuple[DecisionClassification, SeverityLevel, float, EvidenceStrength, str]:
        """
        Fuses multi-layered evidence signals to produce an explainable, deterministic classification.
        Returns: (decision, severity, confidence, evidence_strength, explanation)
        """
        
        # 1. Communication / Data Corruption Checks (Data Quality First)
        if dq.status == DataQualityStatus.INVALID:
            reasons = "; ".join(dq.issues)
            conf = 0.98
            severity = SeverityLevel.CRITICAL if "Physically impossible" in reasons else SeverityLevel.HIGH
            explanation = (
                f"Data Quality / Hardware Failure: {reasons}. "
                "Raw telemetry breaches physical plausibility limits."
            )
            return DecisionClassification.COMMUNICATION_ERROR, severity, conf, EvidenceStrength.HIGH, explanation

        if dq.status == DataQualityStatus.MISSING:
            conf = 0.95
            severity = SeverityLevel.MEDIUM
            explanation = (
                f"Missing Telemetry / Communication Drop: Incomplete parameter packet ({', '.join(dq.flagged_parameters)})."
            )
            return DecisionClassification.COMMUNICATION_ERROR, severity, conf, EvidenceStrength.HIGH, explanation

        # 2. Frozen Sensor Check
        if temporal.freeze_detected:
            frozen_params = [p for p, steps in temporal.frozen_duration_steps.items() if steps >= 4] or ["sensor"]
            conf = 0.94
            severity = SeverityLevel.HIGH
            max_steps = max(temporal.frozen_duration_steps.values()) if temporal.frozen_duration_steps else 4
            explanation = (
                f"Sensor Hardware Failure (Frozen Output): {', '.join(frozen_params)} sensor remained static "
                f"across {max_steps} consecutive intervals. Natural atmospheric micro-turbulence precludes zero variance."
            )
            return DecisionClassification.SENSOR_ANOMALY, severity, conf, EvidenceStrength.HIGH, explanation

        # 3. Regional Weather Event vs Isolated Sensor Anomaly
        temporal_alert = temporal.spike_detected or temporal.drop_detected or temporal.change_point_detected
        spatial_outlier = not spatial.is_consistent
        multivariate_discord = not multivariate.is_consistent
        ml_anomaly = ml.is_anomaly

        # CASE A: Regional Weather Event Corroboration
        # Corroborated when multiple neighboring stations show consistent directional shift
        is_spatially_corroborated_event = (
            spatial.regional_event_detected or 
            (spatial.agreement_ratio >= 0.65 and spatial.corroborating_stations_count >= 2)
        )
        
        if is_spatially_corroborated_event and not multivariate_discord:
            conf = 0.92
            severity = SeverityLevel.MEDIUM
            explanation = (
                "Genuine Meteorological Event: Rapid atmospheric change detected, corroborated by "
                f"{spatial.corroborating_stations_count} neighboring stations with agreement ratio {spatial.agreement_ratio:.2f} "
                f"({spatial.explanation}). Multi-station spatial consensus confirms genuine mesoscale weather phenomenon."
            )
            return DecisionClassification.WEATHER_EVENT, severity, conf, EvidenceStrength.HIGH, explanation

        # 4. Calibration Drift / Sensor Degradation Check
        # Isolated drift: station displays monotonic drift AND either deviates from spatial neighbors or spatial outlier
        has_spatial_divergence = (
            not spatial.is_consistent or 
            abs(spatial.relative_deviations.get("temperature", 0.0)) >= 2.5 or
            abs(spatial.relative_deviations.get("pressure", 0.0)) >= 2.0 or
            abs(spatial.relative_deviations.get("humidity", 0.0)) >= 10.0 or
            spatial.neighbor_count == 0
        )
        if temporal.drift_detected and has_spatial_divergence:
            conf = 0.90
            severity = SeverityLevel.MEDIUM
            explanation = (
                "Sensor Degradation Pattern (Calibration Drift): Station displays continuous "
                f"monotonic drift ({temporal.explanation}) diverging from spatial baseline. "
                "Indicates gradual sensor transducer or conditioning circuit decay."
            )
            return DecisionClassification.SENSOR_DEGRADATION, severity, conf, EvidenceStrength.HIGH, explanation

        # If a minor local variation occurs but spatial neighbors are consistent and report comparable ranges
        max_spat_dev = max([abs(v) for v in spatial.relative_deviations.values()] or [0.0])
        if temporal_alert and not temporal.drift_detected and spatial.is_consistent and max_spat_dev < 2.5 and spatial.valid_neighbor_count >= 2:
            conf = 0.90
            severity = SeverityLevel.LOW
            explanation = (
                f"Normal Regional Fluctuation: Local parameter change ({temporal.explanation}) is consistent "
                f"with neighboring station ranges (relative deviation within {max_spat_dev:.1f}). "
                "Classified as normal atmospheric variation without sensor defect."
            )
            return DecisionClassification.NORMAL, severity, conf, EvidenceStrength.HIGH, explanation

        # CASE B: Isolated Sensor Anomaly (Multi-Signal Corroboration)
        has_local_fault = temporal_alert or multivariate_discord or (dq.status != DataQualityStatus.VALID)
        if spatial_outlier and has_local_fault:
            evidence_points = 0.0
            evidence_items = []
            
            if spatial_outlier:
                evidence_points += 0.35
                evidence_items.append(f"Spatial Disagreement ({spatial.explanation})")
            if temporal_alert:
                evidence_points += 0.30
                evidence_items.append(f"Temporal Excursion ({temporal.explanation})")
            if multivariate_discord:
                evidence_points += 0.20
                evidence_items.append(f"Multivariate Inconsistency ({multivariate.explanation})")
            if ml_anomaly:
                evidence_points += 0.15
                top_feat = list(ml.feature_contributions.keys())[:2] if ml.feature_contributions else []
                evidence_items.append(f"ML Anomaly Score ({ml.anomaly_score:.3f}, primary drivers: {', '.join(top_feat)})")

            conf = round(min(0.99, max(0.70, evidence_points + 0.10)), 2)
            ev_strength = EvidenceStrength.HIGH if evidence_points >= 0.65 else EvidenceStrength.MEDIUM
            
            max_spat_dev = max([abs(v) for v in spatial.relative_deviations.values()] or [0])
            if max_spat_dev > 15.0 or temporal.spike_detected:
                severity = SeverityLevel.CRITICAL if max_spat_dev > 25.0 else SeverityLevel.HIGH
            else:
                severity = SeverityLevel.MEDIUM

            explanation = (
                f"Sensor Anomaly Detected: Station observation is uncorroborated by the observation network. "
                f"Supporting evidence: 1) {'; 2) '.join(evidence_items)}. "
                "Lack of spatial consensus and/or physical discord confirms observation-system failure."
            )
            return DecisionClassification.SENSOR_ANOMALY, severity, conf, ev_strength, explanation

        # CASE C: Multivariate Thermodynamic Violation Alone (e.g. dewpoint ceiling or impossible thermodynamic coupling)
        if multivariate_discord:
            conf = 0.90
            severity = SeverityLevel.HIGH
            explanation = (
                f"Sensor Fault / Multivariate Inconsistency: {multivariate.explanation}. "
                "Thermodynamic relationships between Temperature, Pressure, and Humidity physically violated."
            )
            return DecisionClassification.SENSOR_ANOMALY, severity, conf, EvidenceStrength.HIGH, explanation

        # CASE D: Insufficient Evidence Check
        if history_len < 3 and spatial.valid_neighbor_count == 0:
            if temporal_alert or ml_anomaly:
                conf = 0.45
                severity = SeverityLevel.LOW
                explanation = (
                    "Insufficient Evidence: Reading deviates from nominal range, but station history is brief (<3 timesteps) "
                    "and no spatial neighbors are available within 150 km to cross-corroborate."
                )
                return DecisionClassification.INSUFFICIENT_EVIDENCE, severity, conf, EvidenceStrength.LOW, explanation

        # CASE E: Default Normal Operating State
        conf = 0.95 if not ml_anomaly else 0.80
        severity = SeverityLevel.LOW
        ev_strength = EvidenceStrength.HIGH if not ml_anomaly else EvidenceStrength.MEDIUM
        explanation = "All parameters exhibit natural diurnal variability, thermodynamic consistency, and regional spatial consensus."
        return DecisionClassification.NORMAL, severity, conf, ev_strength, explanation

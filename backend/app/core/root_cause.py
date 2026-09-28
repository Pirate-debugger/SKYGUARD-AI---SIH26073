"""
Root-Cause Classification Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Classifies the root physical or computational cause of flagged observations:
- SENSOR_SPIKE: Sudden transient electronic jump
- SENSOR_FREEZE: Transducer or ADC register lock
- CALIBRATION_DRIFT: Progressive calibration degradation
- COMMUNICATION_FAILURE: Packet loss, dropped reading, transmission timeout
- DATA_CORRUPTION: Impossible parity/checksum or byte overflow
- MULTIVARIATE_INCONSISTENCY: Sensor cross-parameter thermodynamic violation
- SPATIAL_INCONSISTENCY: Localized isolated outlier without regional support
- REGIONAL_WEATHER_EVENT: Coherent atmospheric mesoscale or synoptic event
"""

from typing import Tuple, List, Dict
from app.models.schemas import (
    DecisionClassification,
    ProbableCause,
    DataQualityResult,
    TemporalEvidence,
    MultivariateEvidence,
    SpatialEvidence,
    MLEvidence
)


class RootCauseClassifier:
    def __init__(self):
        pass

    def classify_root_cause(
        self,
        decision: DecisionClassification,
        dq: DataQualityResult,
        temporal: TemporalEvidence,
        multivariate: MultivariateEvidence,
        spatial: SpatialEvidence,
        ml: MLEvidence
    ) -> Tuple[ProbableCause, float, List[str]]:
        """
        Determines the root cause, its specific confidence, and list of supporting signals.
        """
        supporting_signals = []

        if decision == DecisionClassification.NORMAL:
            return ProbableCause.NORMAL_OPERATION, 0.95, ["Parameters conform to diurnal and spatial baselines"]

        if decision == DecisionClassification.WEATHER_EVENT:
            signals = [
                f"Multi-station spatial agreement ({spatial.neighbor_count} stations)",
                "Thermodynamic consistency retained"
            ]
            if spatial.regional_event_detected:
                signals.append("Regional mesoscale signature verified")
            return ProbableCause.REGIONAL_WEATHER_EVENT, 0.92, signals

        if decision == DecisionClassification.COMMUNICATION_ERROR:
            if "Physically impossible" in "; ".join(dq.issues) or "Malformed" in "; ".join(dq.issues):
                return ProbableCause.DATA_CORRUPTION, 0.98, dq.issues
            return ProbableCause.COMMUNICATION_FAILURE, 0.95, dq.issues

        if decision == DecisionClassification.SENSOR_DEGRADATION or temporal.drift_detected:
            signals = [
                f"Monotonic trend slope in telemetry ({temporal.explanation})",
                "Absence of corresponding regional baseline shift"
            ]
            return ProbableCause.CALIBRATION_DRIFT, 0.89, signals

        if temporal.freeze_detected:
            signals = [
                f"Constant ADC output across consecutive intervals ({temporal.explanation})",
                "Turbulent zero-variance violation"
            ]
            return ProbableCause.SENSOR_FREEZE, 0.96, signals

        if temporal.spike_detected or temporal.drop_detected:
            signals = [
                f"Abrupt transient rate-of-change leap ({temporal.explanation})",
                f"Spatial divergence (Δ={max(spatial.relative_deviations.values() or [0]):.1f})"
            ]
            if not multivariate.is_consistent:
                signals.append(f"Decoupled from companion parameters: {', '.join(multivariate.discordant_parameters)}")
            return ProbableCause.SENSOR_SPIKE, 0.94, signals

        if not multivariate.is_consistent:
            return ProbableCause.MULTIVARIATE_INCONSISTENCY, 0.85, [multivariate.explanation]

        if not spatial.is_consistent:
            return ProbableCause.SPATIAL_INCONSISTENCY, 0.87, [spatial.explanation]

        return ProbableCause.UNKNOWN_ANOMALY, 0.50, ["Unclassified deviation pattern; requires manual meteorological review"]

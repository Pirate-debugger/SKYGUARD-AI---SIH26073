"""
Unit Tests: Decision Fusion Engine
SIH26073: Automatic Weather Station Anomaly Detection System

Tests False Alarm Reduction and Discrimination:
- Weather Event vs Sensor Anomaly
- Communication Failure vs Sensor Spike
- Frozen Sensor Detection
- Calibration Drift
"""

import pytest
from app.core.fusion_engine import AnomalyFusionEngine
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


def test_fusion_sensor_spike():
    fe = AnomalyFusionEngine()
    
    dq = DataQualityResult(status=DataQualityStatus.VALID, issues=[], is_valid=True)
    temp = TemporalEvidence(spike_detected=True, robust_z_scores={"temperature": 5.2}, explanation="Abrupt spike +25°C")
    mv = MultivariateEvidence(is_consistent=False, consistency_score=0.2, explanation="Decoupled from humidity")
    spatial = SpatialEvidence(is_consistent=False, neighbor_count=3, relative_deviations={"temperature": 24.5}, explanation="Isolated outlier")
    ml = MLEvidence(is_anomaly=True, anomaly_score=-0.25, confidence=0.92)

    decision, severity, conf, explanation = fe.fuse_signals(dq, temp, mv, spatial, ml)
    assert decision == DecisionClassification.SENSOR_ANOMALY
    assert severity in (SeverityLevel.HIGH, SeverityLevel.CRITICAL)
    assert conf >= 0.85
    assert "Sensor Anomaly" in explanation


def test_fusion_weather_event_false_alarm_reduction():
    fe = AnomalyFusionEngine()
    
    dq = DataQualityResult(status=DataQualityStatus.VALID, issues=[], is_valid=True)
    # Temporal shows high temperature or rapid rise
    temp = TemporalEvidence(spike_detected=True, robust_z_scores={"temperature": 3.8}, explanation="Rapid synoptic heat surge")
    mv = MultivariateEvidence(is_consistent=True, consistency_score=0.8, explanation="Coupled thermodynamic drop in RH")
    # Spatial shows regional event corroboration (neighbors also surged!)
    spatial = SpatialEvidence(is_consistent=True, neighbor_count=4, regional_event_detected=True, relative_deviations={"temperature": 0.8}, explanation="Corroborated by 4 neighbors")
    ml = MLEvidence(is_anomaly=True, anomaly_score=-0.08, confidence=0.70)

    decision, severity, conf, explanation = fe.fuse_signals(dq, temp, mv, spatial, ml)
    # Must NOT be flagged as sensor fault!
    assert decision == DecisionClassification.WEATHER_EVENT
    assert "Genuine Meteorological Event" in explanation


def test_fusion_frozen_sensor():
    fe = AnomalyFusionEngine()
    
    dq = DataQualityResult(status=DataQualityStatus.VALID, issues=[], is_valid=True)
    temp = TemporalEvidence(freeze_detected=True, frozen_duration_steps={"humidity": 8}, explanation="Identical 61.0% across 8 steps")
    mv = MultivariateEvidence(is_consistent=True, consistency_score=0.7)
    spatial = SpatialEvidence(is_consistent=True, neighbor_count=3)
    ml = MLEvidence(is_anomaly=False, anomaly_score=0.05, confidence=0.70)

    decision, severity, conf, explanation = fe.fuse_signals(dq, temp, mv, spatial, ml)
    assert decision == DecisionClassification.SENSOR_ANOMALY
    assert "Frozen Values" in explanation


def test_fusion_data_corruption():
    fe = AnomalyFusionEngine()
    
    dq = DataQualityResult(status=DataQualityStatus.INVALID, issues=["Physically impossible temperature: 150.0°C"], is_valid=False)
    temp = TemporalEvidence()
    mv = MultivariateEvidence()
    spatial = SpatialEvidence()
    ml = MLEvidence()

    decision, severity, conf, explanation = fe.fuse_signals(dq, temp, mv, spatial, ml)
    assert decision == DecisionClassification.COMMUNICATION_ERROR
    assert severity == SeverityLevel.CRITICAL
    assert "Data Corruption" in explanation

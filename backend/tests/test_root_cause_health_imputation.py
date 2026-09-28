"""
Unit Tests: Root Cause, Sensor Health, and Imputation Engines
SIH26073: Automatic Weather Station Anomaly Detection System
"""

import pytest
from app.core.root_cause import RootCauseClassifier
from app.core.sensor_health import SensorHealthEngine, StationHealthTracker
from app.core.imputation import ImputationEngine
from app.models.schemas import (
    DecisionClassification,
    ProbableCause,
    SensorHealthStatus,
    MaintenanceRecommendation,
    DataQualityResult,
    DataQualityStatus,
    TemporalEvidence,
    MultivariateEvidence,
    SpatialEvidence,
    MLEvidence,
    RawReading
)


def test_root_cause_classification():
    rcc = RootCauseClassifier()
    
    # 1. Normal
    cause, conf, sigs = rcc.classify_root_cause(
        DecisionClassification.NORMAL, DataQualityResult(status=DataQualityStatus.VALID),
        TemporalEvidence(), MultivariateEvidence(), SpatialEvidence(), MLEvidence()
    )
    assert cause == ProbableCause.NORMAL_OPERATION

    # 2. Sensor Freeze
    cause, conf, sigs = rcc.classify_root_cause(
        DecisionClassification.SENSOR_ANOMALY, DataQualityResult(status=DataQualityStatus.VALID),
        TemporalEvidence(freeze_detected=True, frozen_duration_steps={"humidity": 7}),
        MultivariateEvidence(), SpatialEvidence(), MLEvidence()
    )
    assert cause == ProbableCause.SENSOR_FREEZE
    assert conf >= 0.90

    # 3. Weather Event
    cause, conf, sigs = rcc.classify_root_cause(
        DecisionClassification.WEATHER_EVENT, DataQualityResult(status=DataQualityStatus.VALID),
        TemporalEvidence(), MultivariateEvidence(), SpatialEvidence(regional_event_detected=True, neighbor_count=4), MLEvidence()
    )
    assert cause == ProbableCause.REGIONAL_WEATHER_EVENT


def test_sensor_health_and_degradation_downgrade():
    she = SensorHealthEngine()
    st_id = "AWS-042"
    tracker = she.get_or_create_tracker(st_id)
    
    # Starts healthy
    h1 = tracker.evaluate_health()
    assert h1.status == SensorHealthStatus.HEALTHY
    assert h1.health_score >= 90.0
    assert h1.maintenance_recommendation == MaintenanceRecommendation.NO_ACTION

    # Simulate 4 spikes and 3 freezes (7 total events >= 6 history threshold)
    for _ in range(4):
        tracker.record_reading_event(DecisionClassification.SENSOR_ANOMALY, ProbableCause.SENSOR_SPIKE, "2026-09-29T10:00:00Z")
    for _ in range(3):
        tracker.record_reading_event(DecisionClassification.SENSOR_ANOMALY, ProbableCause.SENSOR_FREEZE, "2026-09-29T10:05:00Z")

    h2 = tracker.evaluate_health()
    assert h2.status in (SensorHealthStatus.DEGRADED, SensorHealthStatus.CRITICAL)
    assert h2.health_score < 75.0
    assert h2.maintenance_recommendation in (MaintenanceRecommendation.REVIEW_SENSOR, MaintenanceRecommendation.MAINTENANCE_REQUIRED)

    # 5 consecutive communication failures trigger OFFLINE
    for _ in range(5):
        tracker.record_reading_event(DecisionClassification.COMMUNICATION_ERROR, ProbableCause.COMMUNICATION_FAILURE, "2026-09-29T10:10:00Z")

    h3 = tracker.evaluate_health()
    assert h3.status == SensorHealthStatus.OFFLINE
    assert h3.health_score == 0.0
    assert h3.maintenance_recommendation == MaintenanceRecommendation.INSPECT_COMMUNICATION_LINK


def test_imputation_engine():
    ie = ImputationEngine()
    reading = RawReading(
        station_id="AWS-001",
        timestamp="2026-09-29T10:00:00Z",
        temperature=92.5, # Spiked reading
        pressure=1008.0,
        humidity=60.0
    )
    spatial = SpatialEvidence(
        is_consistent=False,
        neighbor_count=3,
        neighbor_medians={"temperature": 32.5, "pressure": 1008.0, "humidity": 60.0}
    )
    history = {
        "temperature": [31.5, 31.8, 32.0, 32.2],
        "pressure": [1008.0, 1008.1],
        "humidity": [61.0, 60.5]
    }
    
    imputed = ie.estimate_corrected_values(reading, spatial, ["temperature"], history)
    assert "temperature" in imputed
    imp_t = imputed["temperature"]
    assert imp_t.is_imputed is True
    assert imp_t.original_value == 92.5
    # Estimated temperature should be around 32°C (spatial median 32.5 and history 32.2)
    assert 31.0 <= imp_t.estimated_value <= 33.5
    assert imp_t.confidence >= 0.80

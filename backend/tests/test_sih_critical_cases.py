"""
Comprehensive Test Suite: SIH26073 Critical Test Cases
AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations

Covers all 10 mandatory cases + processing order invariance + CSV audit:
- CASE 1: Normal station -> NORMAL
- CASE 2: Isolated +12°C valid spike -> SENSOR_ANOMALY / SENSOR_SPIKE
- CASE 3: Repeated same value for multiple cycles -> SENSOR_FREEZE
- CASE 4: Slow sustained sensor bias -> SENSOR_DEGRADATION / CALIBRATION_DRIFT
- CASE 5: No packet for expected interval -> COMMUNICATION_DELAY / OFFLINE
- CASE 6: Multiple neighbors change together -> WEATHER_EVENT
- CASE 7: One station changes while neighbors remain normal -> SENSOR_ANOMALY
- CASE 8: Malformed / impossible data -> DATA_CORRUPTION
- CASE 9: Multivariate contradiction -> MULTIVARIATE_INCONSISTENCY
- CASE 10: Current anomalous point must not influence its own imputation (anti-leakage)
- CASE 11: Station processing order invariance: shuffled arrival order yields identical results
"""

import pytest
from datetime import datetime, timedelta
from app.models.schemas import (
    StationMetadata,
    RawReading,
    SensorHealthStatus,
    DecisionClassification,
    ProbableCause,
    CommunicationState
)
from app.core.pipeline import SkyGuardPipeline
from app.core.sensor_health import StationHealthTracker


def create_mock_pipeline() -> SkyGuardPipeline:
    pipeline = SkyGuardPipeline()
    # Register 4 NCR AWS stations
    stations = [
        StationMetadata(station_id="AWS-001", station_name="Delhi Synoptic", latitude=28.6139, longitude=77.2090, elevation_m=216.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
        StationMetadata(station_id="AWS-002", station_name="Noida AWS", latitude=28.6270, longitude=77.3725, elevation_m=200.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
        StationMetadata(station_id="AWS-003", station_name="Gurugram AWS", latitude=28.4595, longitude=77.0266, elevation_m=220.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
        StationMetadata(station_id="AWS-004", station_name="Faridabad AWS", latitude=28.4089, longitude=77.3178, elevation_m=205.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
    ]
    for s in stations:
        pipeline.spatial_engine.register_station(s)
    return pipeline


# =========================================================================
# CASE 1: Normal Station Observation
# =========================================================================
def test_case_1_normal_station():
    pipeline = create_mock_pipeline()
    base_time = datetime(2026, 4, 15, 10, 0, 0)
    
    # Establish normal history with natural atmospheric micro-variations
    results = None
    for i in range(10):
        t = (base_time + timedelta(minutes=5 * i)).isoformat()
        batch = [
            RawReading(station_id="AWS-001", timestamp=t, temperature=30.0 + i*0.05, pressure=1010.0 + (i%3)*0.1, humidity=55.0 + (i%2)*0.3),
            RawReading(station_id="AWS-002", timestamp=t, temperature=30.2 + i*0.05, pressure=1010.1 + (i%3)*0.1, humidity=54.5 + (i%2)*0.3),
            RawReading(station_id="AWS-003", timestamp=t, temperature=29.9 + i*0.05, pressure=1009.9 + (i%3)*0.1, humidity=55.2 + (i%2)*0.3),
            RawReading(station_id="AWS-004", timestamp=t, temperature=30.1 + i*0.05, pressure=1010.0 + (i%3)*0.1, humidity=54.8 + (i%2)*0.3),
        ]
        results = pipeline.process_batch(batch)
        
    assert results is not None
    final_processed, _ = results[0]
    assert final_processed.decision == DecisionClassification.NORMAL
    assert final_processed.probable_cause == ProbableCause.NORMAL_OPERATION


# =========================================================================
# CASE 2: Isolated Valid Temperature Spike (+12°C)
# =========================================================================
def test_case_2_isolated_temperature_spike():
    pipeline = create_mock_pipeline()
    base_time = datetime(2026, 4, 15, 10, 0, 0)
    
    # Warm baseline with micro-variations
    for i in range(10):
        t = (base_time + timedelta(minutes=5 * i)).isoformat()
        pipeline.process_batch([
            RawReading(station_id="AWS-001", timestamp=t, temperature=30.0 + (i%2)*0.1, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%2)*0.2),
            RawReading(station_id="AWS-002", timestamp=t, temperature=30.1 + (i%2)*0.1, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%2)*0.2),
            RawReading(station_id="AWS-003", timestamp=t, temperature=29.9 + (i%2)*0.1, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%2)*0.2),
            RawReading(station_id="AWS-004", timestamp=t, temperature=30.0 + (i%2)*0.1, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%2)*0.2),
        ])
        
    # AWS-001 experiences isolated +12°C jump (within physical limits)
    t_spike = (base_time + timedelta(minutes=50)).isoformat()
    spike_batch = [
        RawReading(station_id="AWS-001", timestamp=t_spike, temperature=42.0, pressure=1010.0, humidity=55.0),
        RawReading(station_id="AWS-002", timestamp=t_spike, temperature=30.2, pressure=1010.0, humidity=55.0),
        RawReading(station_id="AWS-003", timestamp=t_spike, temperature=30.0, pressure=1010.0, humidity=55.0),
        RawReading(station_id="AWS-004", timestamp=t_spike, temperature=30.1, pressure=1010.0, humidity=55.0),
    ]
    results = pipeline.process_batch(spike_batch)
    p1, _ = results[0]
    
    assert p1.decision == DecisionClassification.SENSOR_ANOMALY
    assert p1.probable_cause == ProbableCause.SENSOR_SPIKE
    assert "Isolated spatial deviation" in p1.spatial_evidence.explanation


# =========================================================================
# CASE 3: Repeated Same Value for Multiple Cycles (Frozen Sensor)
# =========================================================================
def test_case_3_sensor_freeze():
    pipeline = create_mock_pipeline()
    base_time = datetime(2026, 4, 15, 10, 0, 0)
    
    results = None
    for i in range(8):
        t = (base_time + timedelta(minutes=5 * i)).isoformat()
        results = pipeline.process_batch([
            RawReading(station_id="AWS-001", timestamp=t, temperature=28.0 + i*0.1, pressure=1010.0 + (i%2)*0.1, humidity=61.42),
            RawReading(station_id="AWS-002", timestamp=t, temperature=28.1 + i*0.1, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + i*0.5),
            RawReading(station_id="AWS-003", timestamp=t, temperature=27.9 + i*0.1, pressure=1010.0 + (i%2)*0.1, humidity=56.0 + i*0.5),
            RawReading(station_id="AWS-004", timestamp=t, temperature=28.0 + i*0.1, pressure=1010.0 + (i%2)*0.1, humidity=55.5 + i*0.5),
        ])
        
    assert results is not None
    p1, _ = results[0]
    assert p1.decision == DecisionClassification.SENSOR_ANOMALY
    assert p1.probable_cause == ProbableCause.SENSOR_FREEZE
    assert p1.temporal_evidence.freeze_detected is True


# =========================================================================
# CASE 4: Slow Sustained Sensor Bias (Calibration Drift)
# =========================================================================
def test_case_4_sensor_calibration_drift():
    pipeline = create_mock_pipeline()
    base_time = datetime(2026, 4, 15, 10, 0, 0)
    
    # Establish flat baseline first with natural micro-noise
    for i in range(8):
        t = (base_time + timedelta(minutes=5 * i)).isoformat()
        pipeline.process_batch([
            RawReading(station_id="AWS-001", timestamp=t, temperature=25.0 + (i%2)*0.05, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%3)*0.2),
            RawReading(station_id="AWS-002", timestamp=t, temperature=25.1 + (i%2)*0.05, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%3)*0.2),
            RawReading(station_id="AWS-003", timestamp=t, temperature=24.9 + (i%2)*0.05, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%3)*0.2),
            RawReading(station_id="AWS-004", timestamp=t, temperature=25.0 + (i%2)*0.05, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%3)*0.2),
        ])
        
    # AWS-001 starts creeping upwards by +0.38°C each step while neighbors stay flat
    results = None
    for i in range(12):
        t = (base_time + timedelta(minutes=5 * (8 + i))).isoformat()
        drift_temp = 25.0 + (i + 1) * 0.38
        results = pipeline.process_batch([
            RawReading(station_id="AWS-001", timestamp=t, temperature=drift_temp, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%3)*0.2),
            RawReading(station_id="AWS-002", timestamp=t, temperature=25.1, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%3)*0.2),
            RawReading(station_id="AWS-003", timestamp=t, temperature=24.9, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%3)*0.2),
            RawReading(station_id="AWS-004", timestamp=t, temperature=25.0, pressure=1010.0 + (i%2)*0.1, humidity=55.0 + (i%3)*0.2),
        ])
        
    assert results is not None
    p1, _ = results[0]
    assert p1.decision == DecisionClassification.SENSOR_DEGRADATION
    assert p1.probable_cause == ProbableCause.CALIBRATION_DRIFT


# =========================================================================
# CASE 5: Communication Loss and Offline State Tracking
# =========================================================================
def test_case_5_communication_loss_and_offline():
    tracker = StationHealthTracker("AWS-001")
    t0 = datetime(2026, 4, 15, 10, 0, 0)
    
    # Successful initial packet
    tracker.record_reading_event(
        DecisionClassification.NORMAL, ProbableCause.NORMAL_OPERATION, t0.isoformat()
    )
    h0 = tracker.evaluate_health(t0)
    assert h0.communication_state == CommunicationState.ONLINE
    
    # 8 minutes without observation (1-2 missed cycles) -> WARNING
    t1 = t0 + timedelta(minutes=8)
    h1 = tracker.evaluate_health(t1)
    assert h1.communication_state == CommunicationState.WARNING
    
    # 18 minutes without observation (3-4 missed cycles) -> COMMUNICATION_DELAY
    t2 = t0 + timedelta(minutes=18)
    h2 = tracker.evaluate_health(t2)
    assert h2.communication_state == CommunicationState.COMMUNICATION_DELAY
    
    # 50 minutes without observation (>= 5 missed cycles / >45 min) -> OFFLINE
    t3 = t0 + timedelta(minutes=50)
    h3 = tracker.evaluate_health(t3)
    assert h3.communication_state == CommunicationState.OFFLINE


# =========================================================================
# CASE 6: Multiple Neighbors Change Together (Regional Weather Event)
# =========================================================================
def test_case_6_regional_weather_event():
    pipeline = create_mock_pipeline()
    base_time = datetime(2026, 4, 15, 10, 0, 0)
    
    # Baseline
    for i in range(10):
        t = (base_time + timedelta(minutes=5 * i)).isoformat()
        pipeline.process_batch([
            RawReading(station_id="AWS-001", timestamp=t, temperature=30.0, pressure=1010.0, humidity=60.0),
            RawReading(station_id="AWS-002", timestamp=t, temperature=30.2, pressure=1010.0, humidity=60.0),
            RawReading(station_id="AWS-003", timestamp=t, temperature=29.9, pressure=1010.0, humidity=60.0),
            RawReading(station_id="AWS-004", timestamp=t, temperature=30.1, pressure=1010.0, humidity=60.0),
        ])
        
    # Sudden regional heatburst (+8.0°C) across all NCR stations simultaneously
    t_event = (base_time + timedelta(minutes=50)).isoformat()
    event_batch = [
        RawReading(station_id="AWS-001", timestamp=t_event, temperature=38.0, pressure=1007.0, humidity=45.0),
        RawReading(station_id="AWS-002", timestamp=t_event, temperature=38.2, pressure=1007.1, humidity=44.5),
        RawReading(station_id="AWS-003", timestamp=t_event, temperature=37.9, pressure=1006.9, humidity=45.2),
        RawReading(station_id="AWS-004", timestamp=t_event, temperature=38.1, pressure=1007.0, humidity=44.8),
    ]
    results = pipeline.process_batch(event_batch)
    
    for processed, _ in results:
        assert processed.decision == DecisionClassification.WEATHER_EVENT
        assert processed.probable_cause == ProbableCause.REGIONAL_WEATHER_EVENT
        assert processed.spatial_evidence.regional_event_detected is True
        assert processed.spatial_evidence.agreement_ratio >= 0.65


# =========================================================================
# CASE 7: One Station Changes While Neighbors Remain Normal (Spatial Outlier)
# =========================================================================
def test_case_7_isolated_spatial_outlier():
    pipeline = create_mock_pipeline()
    base_time = datetime(2026, 4, 15, 10, 0, 0)
    
    for i in range(6):
        t = (base_time + timedelta(minutes=5 * i)).isoformat()
        pipeline.process_batch([
            RawReading(station_id="AWS-001", timestamp=t, temperature=28.0, pressure=1010.0, humidity=50.0),
            RawReading(station_id="AWS-002", timestamp=t, temperature=28.1, pressure=1010.0, humidity=50.0),
            RawReading(station_id="AWS-003", timestamp=t, temperature=27.9, pressure=1010.0, humidity=50.0),
            RawReading(station_id="AWS-004", timestamp=t, temperature=28.0, pressure=1010.0, humidity=50.0),
        ])
        
    t_out = (base_time + timedelta(minutes=30)).isoformat()
    outlier_batch = [
        RawReading(station_id="AWS-001", timestamp=t_out, temperature=41.5, pressure=1010.0, humidity=50.0),
        RawReading(station_id="AWS-002", timestamp=t_out, temperature=28.2, pressure=1010.0, humidity=50.0),
        RawReading(station_id="AWS-003", timestamp=t_out, temperature=28.0, pressure=1010.0, humidity=50.0),
        RawReading(station_id="AWS-004", timestamp=t_out, temperature=28.1, pressure=1010.0, humidity=50.0),
    ]
    results = pipeline.process_batch(outlier_batch)
    p1, _ = results[0]
    
    assert p1.decision == DecisionClassification.SENSOR_ANOMALY
    assert p1.spatial_evidence.is_consistent is False
    assert p1.spatial_evidence.agreement_ratio == 0.0


# =========================================================================
# CASE 8: Malformed / Impossible Data (Data Corruption)
# =========================================================================
def test_case_8_data_corruption():
    pipeline = create_mock_pipeline()
    t = datetime(2026, 4, 15, 10, 0, 0).isoformat()
    
    # Temperature of 145.0°C breaches physical boundaries
    corrupt_reading = RawReading(station_id="AWS-001", timestamp=t, temperature=145.0, pressure=1010.0, humidity=50.0)
    results = pipeline.process_batch([corrupt_reading])
    p1, _ = results[0]
    
    assert p1.decision == DecisionClassification.COMMUNICATION_ERROR
    assert p1.probable_cause == ProbableCause.DATA_CORRUPTION
    assert p1.data_quality.is_valid is False


# =========================================================================
# CASE 9: Multivariate Contradiction (Dewpoint Ceiling Violation)
# =========================================================================
def test_case_9_multivariate_contradiction():
    pipeline = create_mock_pipeline()
    t = datetime(2026, 4, 15, 10, 0, 0).isoformat()
    
    # 48°C with 99% RH implies an impossible dewpoint of >47°C (exceeds 35°C terrestrial ceiling)
    discord_reading = RawReading(station_id="AWS-001", timestamp=t, temperature=48.0, pressure=1010.0, humidity=99.0)
    results = pipeline.process_batch([discord_reading])
    p1, _ = results[0]
    
    assert p1.decision == DecisionClassification.SENSOR_ANOMALY
    assert p1.probable_cause == ProbableCause.MULTIVARIATE_INCONSISTENCY
    assert p1.multivariate_evidence.is_consistent is False


# =========================================================================
# CASE 10: Anti-Leakage Imputation (Anomalous point excluded from estimation)
# =========================================================================
def test_case_10_anti_leakage_imputation():
    pipeline = create_mock_pipeline()
    base_time = datetime(2026, 4, 15, 10, 0, 0)
    
    # Send 10 clean readings at 30.0°C
    for i in range(10):
        t = (base_time + timedelta(minutes=5 * i)).isoformat()
        pipeline.process_batch([
            RawReading(station_id="AWS-001", timestamp=t, temperature=30.0, pressure=1010.0, humidity=55.0),
            RawReading(station_id="AWS-002", timestamp=t, temperature=30.2, pressure=1010.0, humidity=55.0),
            RawReading(station_id="AWS-003", timestamp=t, temperature=29.8, pressure=1010.0, humidity=55.0),
            RawReading(station_id="AWS-004", timestamp=t, temperature=30.0, pressure=1010.0, humidity=55.0),
        ])
        
    # Anomaly arrives: +30°C spike to 60.0°C
    t_spike = (base_time + timedelta(minutes=50)).isoformat()
    spike_batch = [
        RawReading(station_id="AWS-001", timestamp=t_spike, temperature=60.0, pressure=1010.0, humidity=55.0),
        RawReading(station_id="AWS-002", timestamp=t_spike, temperature=30.2, pressure=1010.0, humidity=55.0),
        RawReading(station_id="AWS-003", timestamp=t_spike, temperature=29.8, pressure=1010.0, humidity=55.0),
        RawReading(station_id="AWS-004", timestamp=t_spike, temperature=30.0, pressure=1010.0, humidity=55.0),
    ]
    results = pipeline.process_batch(spike_batch)
    p1, _ = results[0]
    
    assert "temperature" in p1.imputed_values
    imputed_t = p1.imputed_values["temperature"]
    
    # Verify strict anti-leakage:
    # 1. The original corrupted value 60.0 must be preserved untouched
    assert imputed_t.original_value == 60.0
    # 2. The estimated value must reflect clean pre-current history & neighbor median (~30.0°C)
    # If the 60.0°C leaked into history, estimated value would be pulled towards 40°C
    assert 29.5 <= imputed_t.estimated_value <= 31.0
    assert imputed_t.is_imputed is True


# =========================================================================
# CASE 11: Processing Order Invariance (Section 41 mandatory requirement)
# Take exact same timestamp: A B C D E. Run A B C D E, then E D C B A, then C A E B D.
# Final decisions must be equivalent.
# =========================================================================
def test_case_11_processing_order_invariance_5_stations():
    def create_5_station_pipeline():
        pipeline = SkyGuardPipeline()
        stations = [
            StationMetadata(station_id="AWS-001", station_name="A", latitude=28.6139, longitude=77.2090, elevation_m=216.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
            StationMetadata(station_id="AWS-002", station_name="B", latitude=28.6270, longitude=77.3725, elevation_m=200.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
            StationMetadata(station_id="AWS-003", station_name="C", latitude=28.4595, longitude=77.0266, elevation_m=220.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
            StationMetadata(station_id="AWS-004", station_name="D", latitude=28.4089, longitude=77.3178, elevation_m=205.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
            StationMetadata(station_id="AWS-005", station_name="E", latitude=28.5355, longitude=77.3910, elevation_m=202.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
        ]
        for s in stations:
            pipeline.spatial_engine.register_station(s)
        return pipeline

    p1 = create_5_station_pipeline()
    p2 = create_5_station_pipeline()
    p3 = create_5_station_pipeline()
    t = datetime(2026, 4, 15, 10, 0, 0).isoformat()
    
    rA = RawReading(station_id="AWS-001", timestamp=t, temperature=55.0, pressure=1010.0, humidity=55.0)
    rB = RawReading(station_id="AWS-002", timestamp=t, temperature=30.0, pressure=1010.0, humidity=55.0)
    rC = RawReading(station_id="AWS-003", timestamp=t, temperature=30.2, pressure=1010.0, humidity=55.0)
    rD = RawReading(station_id="AWS-004", timestamp=t, temperature=29.8, pressure=1010.0, humidity=55.0)
    rE = RawReading(station_id="AWS-005", timestamp=t, temperature=30.1, pressure=1010.0, humidity=55.0)

    # Permutation 1: A B C D E
    res1 = p1.process_batch([rA, rB, rC, rD, rE])
    # Permutation 2: E D C B A
    res2 = p2.process_batch([rE, rD, rC, rB, rA])
    # Permutation 3: C A E B D
    res3 = p3.process_batch([rC, rA, rE, rB, rD])

    map1 = {p.station_id: p.decision for p, _ in res1}
    map2 = {p.station_id: p.decision for p, _ in res2}
    map3 = {p.station_id: p.decision for p, _ in res3}

    assert map1 == map2 == map3
    assert map1["AWS-001"] == DecisionClassification.SENSOR_ANOMALY
    assert map1["AWS-002"] == DecisionClassification.NORMAL


# =========================================================================
# CASE 12: Insufficient Evidence Handling
# =========================================================================
def test_case_12_insufficient_evidence():
    pipeline = SkyGuardPipeline()
    # No stations registered in spatial engine, no previous history
    isolated_reading = RawReading(station_id="AWS-ISOLATED", timestamp="2026-04-15T10:00:00Z", temperature=32.0, pressure=1010.0, humidity=55.0)
    results = pipeline.process_batch([isolated_reading])
    p, _ = results[0]
    assert p.spatial_evidence.neighbor_count == 0
    assert p.spatial_evidence.valid_neighbor_count == 0
    assert "not registered" in p.spatial_evidence.explanation or "No neighboring stations" in p.spatial_evidence.explanation


# =========================================================================
# CASE 13: Imputation Neighbor Quality (Reject Corrupted Neighbor)
# =========================================================================
def test_case_13_imputation_rejects_corrupted_neighbor():
    from app.core.imputation import ImputationEngine
    from app.models.schemas import SpatialEvidence
    engine = ImputationEngine()
    
    st_meta = {
        "AWS-001": StationMetadata(station_id="AWS-001", station_name="Target", latitude=28.61, longitude=77.20, elevation_m=200.0, region="NCR"),
        "AWS-002": StationMetadata(station_id="AWS-002", station_name="Corrupt", latitude=28.62, longitude=77.21, elevation_m=200.0, region="NCR"),
        "AWS-003": StationMetadata(station_id="AWS-003", station_name="Clean", latitude=28.60, longitude=77.19, elevation_m=200.0, region="NCR")
    }
    target_reading = RawReading(station_id="AWS-001", timestamp="2026-04-15T10:00:00Z", temperature=None, pressure=1010.0, humidity=55.0)
    
    neighbor_distances = [("AWS-002", 5.0), ("AWS-003", 5.0)]
    neighbor_readings = {
        "AWS-002": RawReading(station_id="AWS-002", timestamp="2026-04-15T10:00:00Z", temperature=145.0, pressure=1010.0, humidity=55.0), # Impossible/corrupt
        "AWS-003": RawReading(station_id="AWS-003", timestamp="2026-04-15T10:00:00Z", temperature=30.0, pressure=1010.0, humidity=55.0)   # Clean valid
    }
    
    imputed = engine.estimate_corrected_values(
        reading=target_reading,
        spatial=SpatialEvidence(valid_neighbor_count=1),
        flagged_params=["temperature"],
        temporal_buffer_history={},
        neighbor_distances=neighbor_distances,
        neighbor_readings=neighbor_readings,
        stations_dict=st_meta
    )
    
    assert "temperature" in imputed
    # The 145.0°C corrupt value must have been filtered out, yielding ~30.0°C from AWS-003
    assert imputed["temperature"].estimated_value == 30.0


# =========================================================================
# CASE 14: Stale Neighbor Exclusion (>15 minutes)
# =========================================================================
def test_case_14_stale_neighbor_exclusion():
    pipeline = create_mock_pipeline()
    t_target = "2026-04-15T10:30:00Z"
    t_stale = "2026-04-15T10:00:00Z" # 30 min old (>15 min threshold)
    
    # Store stale reading for AWS-002 in spatial engine
    pipeline.spatial_engine.latest_readings["AWS-002"] = RawReading(
        station_id="AWS-002", timestamp=t_stale, temperature=30.0, pressure=1010.0, humidity=55.0
    )
    
    target_reading = RawReading(station_id="AWS-001", timestamp=t_target, temperature=32.0, pressure=1010.0, humidity=55.0)
    spatial_ev = pipeline.spatial_engine.analyze(target_reading)
    
    assert "AWS-002" in spatial_ev.stale_neighbor_ids
    assert spatial_ev.valid_neighbor_count == 0


# =========================================================================
# CASE 15 & 16: Database Reading Persistence & Restart Recovery
# =========================================================================
@pytest.mark.asyncio
async def test_case_15_and_16_persistence_and_restart():
    import tempfile, os
    from app.database.db import DatabaseManager
    from app.database.seed import seed_initial_data
    from app.models.schemas import (
        ProcessedReading, DataQualityResult, DataQualityStatus,
        TemporalEvidence, MultivariateEvidence, SpatialEvidence,
        MLEvidence, SeverityLevel, EvidenceStrength
    )
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_file = tmp.name

    try:
        db = DatabaseManager(db_path=db_file)
        await db.init_db()
        
        # Save a reading
        pr = ProcessedReading(
            reading_id="r-test-101",
            station_id="AWS-001",
            timestamp="2026-04-15T10:00:00Z",
            temperature=31.5,
            pressure=1009.5,
            humidity=52.0,
            data_quality=DataQualityResult(status=DataQualityStatus.VALID),
            temporal_evidence=TemporalEvidence(),
            multivariate_evidence=MultivariateEvidence(),
            spatial_evidence=SpatialEvidence(),
            ml_evidence=MLEvidence(),
            decision=DecisionClassification.NORMAL,
            probable_cause=ProbableCause.NORMAL_OPERATION,
            severity=SeverityLevel.LOW,
            confidence=0.92,
            evidence_strength=EvidenceStrength.HIGH,
            explanation="Operational reading",
            model_version="v2.0.0",
            ruleset_version="v2.0.0",
            feature_version="v2.0.0"
        )
        await db.save_reading(pr)
        count = await db.get_readings_count()
        assert count == 1
        
        # Simulate restart recovery: seed_initial_data detects existing readings and avoids clobbering
        pipeline = SkyGuardPipeline()
        await seed_initial_data(pipeline, db)
        
        # Verify history was restored into pipeline temporal engine
        buffer = pipeline.temporal_engine.get_or_create_buffer("AWS-001")
        temp_series = buffer.get_parameter_series("temperature")
        assert len(temp_series) >= 1
        assert temp_series[-1] == 31.5
    finally:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass


# =========================================================================
# CASE 17: Persistent Alert Acknowledgement
# =========================================================================
@pytest.mark.asyncio
async def test_case_17_alert_acknowledgement_persistence():
    import tempfile, os
    from app.database.db import DatabaseManager
    from app.models.schemas import AlertRecord, SeverityLevel, MaintenanceRecommendation
    
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_file = tmp.name

    try:
        db = DatabaseManager(db_path=db_file)
        await db.init_db()
        
        alert = AlertRecord(
            alert_id="alt-001",
            station_id="AWS-001",
            timestamp="2026-04-15T10:00:00Z",
            decision=DecisionClassification.SENSOR_ANOMALY,
            probable_cause=ProbableCause.SENSOR_SPIKE,
            severity=SeverityLevel.HIGH,
            confidence=0.95,
            flagged_parameters=["temperature"],
            observed_values={"temperature": 45.0},
            expected_values={"temperature": 32.0},
            deviations={"temperature": 13.0},
            explanation="Temperature spike detected",
            recommended_action=MaintenanceRecommendation.REVIEW_SENSOR,
            acknowledged=False
        )
        await db.save_alert(alert)
        
        # Acknowledge alert in DB
        ack_res = await db.acknowledge_alert("alt-001", acknowledged_by="Lead_Operator")
        assert ack_res is True
        
        # Verify persistence across DB reconnection (simulating restart)
        db2 = DatabaseManager(db_path=db_file)
        await db2.init_db()
        alerts = await db2.get_alerts(limit=5)
        assert len(alerts) == 1
        assert alerts[0].acknowledged is True
        assert alerts[0].acknowledged_by == "Lead_Operator"
        assert alerts[0].acknowledged_at is not None
    finally:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass


# =========================================================================
# CASE 18: Anomaly Score Semantics (Raw vs Normalized)
# =========================================================================
def test_case_18_anomaly_score_semantics():
    from app.core.ml_detector import MLAnomalyDetector
    detector = MLAnomalyDetector()
    
    # Inlier residual
    inlier_feat = detector.extract_features(
        temperature=28.0,
        pressure=1010.0,
        humidity=65.0,
        rates_of_change={"temperature": 0.05, "pressure": -0.01, "humidity": 0.1},
        spatial_diffs={"temperature": 0.1, "pressure": 0.2, "humidity": 0.5},
        mahalanobis_dist=1.2
    )
    inlier_ev = detector.predict(inlier_feat)
    
    # Highly anomalous residual
    outlier_feat = detector.extract_features(
        temperature=75.0,
        pressure=920.0,
        humidity=99.0,
        rates_of_change={"temperature": 15.0, "pressure": -12.0, "humidity": 45.0},
        spatial_diffs={"temperature": 25.0, "pressure": 15.0, "humidity": 35.0},
        mahalanobis_dist=18.5
    )
    outlier_ev = detector.predict(outlier_feat)
    
    # Verify exact semantics:
    # Inlier has raw_decision_score > outlier_ev.raw_decision_score
    # Inlier has normalized_anomaly_score < outlier_ev.normalized_anomaly_score
    assert inlier_ev.raw_decision_score > outlier_ev.raw_decision_score
    assert inlier_ev.normalized_anomaly_score < outlier_ev.normalized_anomaly_score
    assert 0.0 <= inlier_ev.normalized_anomaly_score <= 1.0
    assert 0.0 <= outlier_ev.normalized_anomaly_score <= 1.0
    assert outlier_ev.is_anomaly is True

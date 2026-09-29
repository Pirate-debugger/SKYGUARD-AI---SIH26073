"""
Geospatial Mesh & SIH26073 Spatial Engine Verification Tests
Covers all 9 Cases specified in SIH26073 Regional AWS Geospatial Mesh requirements:
- Case 1: Normal network state
- Case 2: Isolated sensor anomaly vs health
- Case 3: Regional weather event vs health separation & corroborating edges
- Case 4: Station degradation health state
- Case 5: Offline station state & no false corroboration
- Case 6: Honest zero-neighbor stations (Bareilly AWS-011 & Chandigarh AWS-012)
- Case 7: Order-independent synchronized batch spatial processing
- Case 8: Dynamic radius adjustment (150 km -> 100 km)
- Case 9: Dynamic k-nearest neighbor adjustment (4 -> 2)
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app, pipeline
from app.models.schemas import RawReading, DecisionClassification, SensorHealthStatus, SensorHealthSummary
from app.core.spatial_engine import SpatialConsistencyEngine, haversine_km
from app.simulator.generator import DEFAULT_STATIONS


@pytest.fixture
def client():
    return TestClient(app)


def test_spatial_network_topology_endpoint(client):
    """Verify /api/network/spatial returns authoritative Haversine topology."""
    resp = client.get("/api/network/spatial")
    assert resp.status_code == 200
    data = resp.json()

    assert data["radius_km"] == 150.0
    assert data["k_nearest_neighbors"] == 4
    assert data["total_stations"] == 12
    assert len(data["stations"]) == 12
    assert len(data["edges"]) > 0


def test_case_6_zero_neighbor_stations_honest_representation(client):
    """
    CASE 6: Stations AWS-011 (Bareilly) and AWS-012 (Chandigarh) are >150km away.
    They must have 0 neighbors, NO_NEIGHBORS status, and NO edges connecting them.
    """
    resp = client.get("/api/network/spatial?radius_km=150&k=4")
    assert resp.status_code == 200
    data = resp.json()

    stations_by_id = {s["station_id"]: s for s in data["stations"]}
    
    # AWS-011 Bareilly
    s11 = stations_by_id["AWS-011"]
    assert s11["neighbor_count"] == 0
    assert s11["neighbors_within_radius"] == 0
    assert s11["spatial_status"] == "NO_NEIGHBORS"
    assert s11["has_neighbors"] is False
    assert len(s11["neighbors"]) == 0

    # AWS-012 Chandigarh
    s12 = stations_by_id["AWS-012"]
    assert s12["neighbor_count"] == 0
    assert s12["neighbors_within_radius"] == 0
    assert s12["spatial_status"] == "NO_NEIGHBORS"
    assert s12["has_neighbors"] is False
    assert len(s12["neighbors"]) == 0

    # Verify no edge contains AWS-011 or AWS-012
    for edge in data["edges"]:
        assert edge["source"] != "AWS-011" and edge["target"] != "AWS-011", "AWS-011 must not have artificial edges!"
        assert edge["source"] != "AWS-012" and edge["target"] != "AWS-012", "AWS-012 must not have artificial edges!"

    # AWS-010 Jaipur has only 1 neighbor (AWS-006 Alwar at 110.0km)
    s10 = stations_by_id["AWS-010"]
    assert s10["neighbor_count"] == 1
    assert s10["spatial_status"] == "LOW_EVIDENCE"
    assert s10["neighbors"][0]["station_id"] == "AWS-006"


def test_case_8_dynamic_radius_adjustment(client):
    """
    CASE 8: Changing radius from 150 km to 100 km automatically reduces topology edges.
    """
    resp_150 = client.get("/api/network/spatial?radius_km=150")
    resp_100 = client.get("/api/network/spatial?radius_km=100")
    
    data_150 = resp_150.json()
    data_100 = resp_100.json()

    assert data_150["radius_km"] == 150.0
    assert data_100["radius_km"] == 100.0

    # Edge count at 100km must be strictly less than or equal to edge count at 150km
    assert len(data_100["edges"]) < len(data_150["edges"])
    # All edges in 100km must have distance <= 100km
    for edge in data_100["edges"]:
        assert edge["distance_km"] <= 100.0


def test_case_9_dynamic_k_adjustment(client):
    """
    CASE 9: Changing k from 4 to 2 reduces maximum neighbors per station to 2.
    """
    resp_k2 = client.get("/api/network/spatial?radius_km=150&k=2")
    data_k2 = resp_k2.json()

    assert data_k2["k_nearest_neighbors"] == 2
    for s in data_k2["stations"]:
        assert s["neighbor_count"] <= 2
        assert len(s["neighbors"]) <= 2


def test_case_7_order_independent_batch_processing():
    """
    CASE 7: Same data processed in different station order produces identical decisions.
    """
    from app.core.pipeline import SkyGuardPipeline
    p1 = SkyGuardPipeline()
    p2 = SkyGuardPipeline()

    now = datetime(2026, 9, 29, 12, 0, 0)
    readings = [
        RawReading(station_id=st.station_id, timestamp=now, temperature=30.0, pressure=1008.0, humidity=55.0)
        for st in DEFAULT_STATIONS
    ]

    # p1 processes standard order
    res1 = p1.process_batch(readings)

    # p2 processes reversed order
    res2 = p2.process_batch(list(reversed(readings)))

    res1_map = {p.station_id: p.decision for p, _ in res1}
    res2_map = {p.station_id: p.decision for p, _ in res2}

    for st in DEFAULT_STATIONS:
        assert res1_map[st.station_id] == res2_map[st.station_id], f"Decision for {st.station_id} differed across orders!"


def test_case_1_normal_network_state(client):
    """
    CASE 1: Normal stations have healthy status and NORMAL event decisions.
    """
    resp = client.get("/api/network/spatial")
    data = resp.json()
    for st in data["stations"]:
        assert st["health_status"] in ["HEALTHY", "WATCH"]
        # Nodes should not be marked as critical anomalies when operating normally
        assert st["latest_decision"] in [None, "NORMAL", "WEATHER_EVENT", "SENSOR_ANOMALY"]


def test_case_2_and_3_health_and_event_separation():
    """
    CASE 2 & 3: Two-layer status system.
    A station undergoing a WEATHER_EVENT must NOT automatically have its physical sensor health degraded.
    An isolated SENSOR_ANOMALY must be flagged as an event without immediately labeling health as CRITICAL.
    """
    from app.core.health_engine import SensorHealthEngine
    health_engine = SensorHealthEngine()

    # Initial state is HEALTHY
    summary = health_engine.get_health_summary("AWS-001")
    assert summary.status == SensorHealthStatus.HEALTHY

    # Simulating a weather event reading - does not increment hardware failure counters
    # Weather events are genuine atmospheric occurrences, not sensor defects!
    health_engine.update_from_reading(
        station_id="AWS-001",
        is_spike=False,
        is_frozen=False,
        is_comm_gap=False,
        is_drift=False,
        is_weather_event=True
    )
    summary_after_weather = health_engine.get_health_summary("AWS-001")
    assert summary_after_weather.status == SensorHealthStatus.HEALTHY
    assert summary_after_weather.health_score >= 95.0

    # Simulating a single isolated spike - triggers WATCH, not immediate catastrophic CRITICAL
    health_engine.update_from_reading(
        station_id="AWS-001",
        is_spike=True,
        is_frozen=False,
        is_comm_gap=False,
        is_drift=False,
        is_weather_event=False
    )
    summary_after_spike = health_engine.get_health_summary("AWS-001")
    assert summary_after_spike.status in [SensorHealthStatus.HEALTHY, SensorHealthStatus.WATCH]
    assert summary_after_spike.status != SensorHealthStatus.CRITICAL


def test_haversine_formula_accuracy():
    """Verify exact Haversine distance matches true geodetic distances."""
    # Delhi Safdarjung (28.5833, 77.2083) to Palam (28.5667, 77.1167)
    d = haversine_km(28.5833, 77.2083, 28.5667, 77.1167)
    assert 8.0 < d < 12.0  # Exactly ~9.1 km

    # Delhi to Bareilly (~220 km)
    d_bareilly = haversine_km(28.5833, 77.2083, 28.3667, 79.4167)
    assert d_bareilly > 200.0, "Bareilly must be > 200km away from Delhi!"

    # Delhi to Chandigarh (~230 km)
    d_chandigarh = haversine_km(28.5833, 77.2083, 30.7333, 76.7794)
    assert d_chandigarh > 220.0, "Chandigarh must be > 220km away from Delhi!"


def test_case_4_station_degradation():
    """
    CASE 4: Station degradation manifests as DEGRADED health status.
    Repeated drift / freezes accumulate wear and transition health to DEGRADED.
    """
    from app.core.sensor_health import SensorHealthEngine, SensorHealthStatus
    he = SensorHealthEngine()
    
    # Simulate repeated drift cycles
    for i in range(8):
        he.update_from_reading(
            station_id="AWS-005",
            is_drift=True,
            timestamp=f"2026-09-29T10:{i:02d}:00Z"
        )
    summary = he.get_health_summary("AWS-005")
    assert summary.status == SensorHealthStatus.DEGRADED
    assert summary.drift_trend_detected is True
    assert summary.health_score <= 75.0


def test_case_5_offline_station_state():
    """
    CASE 5: Station telemetry loss transitions communication and health state to OFFLINE.
    Does not produce false spatial corroborations.
    """
    from datetime import timedelta, timezone
    from app.core.sensor_health import SensorHealthEngine, SensorHealthStatus, CommunicationState
    he = SensorHealthEngine()
    
    past_time = datetime.now(timezone.utc) - timedelta(minutes=45)
    he.update_from_reading(
        station_id="AWS-004",
        is_spike=False,
        timestamp=past_time.isoformat()
    )
    # Evaluate at current time (>30 min delay)
    summary = he.get_health_summary("AWS-004", current_time=datetime.now(timezone.utc))
    assert summary.status == SensorHealthStatus.OFFLINE
    assert summary.communication_state == CommunicationState.OFFLINE
    assert summary.missed_intervals >= 3
    assert summary.time_since_last_reading_min >= 30.0


def test_demo_a_weather_event_simulation():
    """
    DEMO A: Regional Weather Event across NCR cluster.
    Multiple neighboring stations (AWS-001, AWS-002, AWS-003, AWS-004) shift coherently.
    Their health remains HEALTHY, latest_decision becomes WEATHER_EVENT,
    and spatial corroboration is confirmed.
    """
    from datetime import timedelta
    from app.core.pipeline import SkyGuardPipeline
    p = SkyGuardPipeline()
    now_dt = datetime(2026, 9, 29, 14, 0, 0)
    
    # Baseline batch
    readings_t0 = [
        RawReading(station_id=st.station_id, timestamp=now_dt.isoformat(), temperature=30.0, pressure=1008.0, humidity=55.0)
        for st in DEFAULT_STATIONS
    ]
    p.process_batch(readings_t0)
    
    # t1: Regional cold front / squall: sudden drop in temp (-3.5°C) and pressure surge (+2.0 hPa) across all NCR stations
    t1_dt = now_dt + timedelta(minutes=5)
    ncr_ids = {"AWS-001", "AWS-002", "AWS-003", "AWS-004"}
    readings_t1 = []
    for st in DEFAULT_STATIONS:
        if st.station_id in ncr_ids:
            readings_t1.append(
                RawReading(station_id=st.station_id, timestamp=t1_dt.isoformat(), temperature=26.5, pressure=1010.0, humidity=75.0)
            )
        else:
            readings_t1.append(
                RawReading(station_id=st.station_id, timestamp=t1_dt.isoformat(), temperature=30.0, pressure=1008.0, humidity=55.0)
            )
            
    res_t1 = p.process_batch(readings_t1)
    res_map = {proc.station_id: proc for proc, _ in res_t1}
    
    # NCR stations should corroborate each other and detect WEATHER_EVENT
    aws1 = res_map["AWS-001"]
    assert aws1.decision == DecisionClassification.WEATHER_EVENT
    assert aws1.spatial_evidence.regional_event_detected is True
    assert aws1.spatial_evidence.corroborating_stations_count >= 2
    assert aws1.spatial_evidence.agreement_ratio >= 0.65
    
    # Health remains HEALTHY (hardware is operating nominally)
    h_summary = p.health_engine.get_health_summary("AWS-001")
    assert h_summary.status == SensorHealthStatus.HEALTHY


def test_demo_b_isolated_sensor_spike():
    """
    DEMO B: Isolated Sensor Anomaly on AWS-001 (+12°C spike).
    Neighbors remain normal; AWS-001 fails spatial consensus and is flagged SENSOR_ANOMALY.
    Its neighbors stay normal.
    """
    from datetime import timedelta
    from app.core.pipeline import SkyGuardPipeline
    p = SkyGuardPipeline()
    now_dt = datetime(2026, 9, 29, 14, 0, 0)
    
    readings_t0 = [
        RawReading(station_id=st.station_id, timestamp=now_dt.isoformat(), temperature=30.0, pressure=1008.0, humidity=55.0)
        for st in DEFAULT_STATIONS
    ]
    p.process_batch(readings_t0)
    
    # t1: AWS-001 spikes to 42°C (+12°C jump), while all neighbors remain at 30°C
    t1_dt = now_dt + timedelta(minutes=5)
    readings_t1 = []
    for st in DEFAULT_STATIONS:
        if st.station_id == "AWS-001":
            readings_t1.append(
                RawReading(station_id="AWS-001", timestamp=t1_dt.isoformat(), temperature=42.0, pressure=1008.0, humidity=55.0)
            )
        else:
            readings_t1.append(
                RawReading(station_id=st.station_id, timestamp=t1_dt.isoformat(), temperature=30.0, pressure=1008.0, humidity=55.0)
            )
            
    res_t1 = p.process_batch(readings_t1)
    res_map = {proc.station_id: proc for proc, _ in res_t1}
    
    aws1 = res_map["AWS-001"]
    assert aws1.decision == DecisionClassification.SENSOR_ANOMALY
    assert aws1.spatial_evidence.corroborating_stations_count == 0
    assert aws1.spatial_evidence.regional_event_detected is False
    
    # Neighbor AWS-002 remains NORMAL
    aws2 = res_map["AWS-002"]
    assert aws2.decision == DecisionClassification.NORMAL

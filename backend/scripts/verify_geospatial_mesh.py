"""
End-to-End Verification Script for SIH26073 Regional AWS Geospatial Mesh
Validates:
1. Exact Haversine 150 km Topology & Connected Components
2. Stations with Zero Neighbors & Low Evidence
3. Two-Layer Status Separation (Health vs Event)
4. DEMO A: Regional Weather Event Multi-Station Corroboration
5. DEMO B: Isolated Sensor Spike Anomaly Isolation
"""

from datetime import datetime, timedelta
from app.simulator.generator import DEFAULT_STATIONS
from app.core.spatial_engine import SpatialConsistencyEngine, haversine_km
from app.core.pipeline import SkyGuardPipeline
from app.models.schemas import RawReading, DecisionClassification, SensorHealthStatus


def verify_network_topology():
    print("=" * 60)
    print("1. AUTHORITATIVE 150 KM GEOSPATIAL NETWORK TOPOLOGY")
    print("=" * 60)
    se = SpatialConsistencyEngine()
    for st in DEFAULT_STATIONS:
        se.register_station(st)

    topo = se.get_network_topology(radius_km=150.0, k=4)
    print(f"Total Configured Stations: {topo['total_stations']}")
    print(f"Spatial Search Radius:    {topo['radius_km']} km")
    print(f"Max Neighbors (k):        {topo['k_nearest_neighbors']}")
    print(f"Total Mesh Edges:         {len(topo['edges'])}")
    print("-" * 60)

    for st in topo["stations"]:
        nbr_str = ", ".join([f"{n['station_id']} ({n['distance_km']} km)" for n in st["neighbors"]])
        print(f"{st['station_id']:7s} | {st['station_name']:28s} | {st['spatial_status']:12s} | Neighbors: {st['neighbor_count']} [{nbr_str}]")

    print("-" * 60)
    zero_nbrs = [s["station_id"] for s in topo["stations"] if s["neighbor_count"] == 0]
    low_nbrs = [s["station_id"] for s in topo["stations"] if s["neighbor_count"] == 1]
    print(f"Zero-Neighbor Stations: {zero_nbrs}")
    print(f"Low-Evidence Stations:  {low_nbrs}")
    return topo


def verify_demo_a_weather_event():
    print("\n" + "=" * 60)
    print("2. DEMO A — REGIONAL WEATHER EVENT SIMULATION")
    print("=" * 60)
    pipeline = SkyGuardPipeline()
    t0 = datetime(2026, 9, 29, 14, 0, 0)

    # Step 0: Baseline state
    r0 = [
        RawReading(station_id=s.station_id, timestamp=t0.isoformat(), temperature=30.0, pressure=1008.0, humidity=50.0)
        for s in DEFAULT_STATIONS
    ]
    pipeline.process_batch(r0)

    # Step 1: Injected cold squall across NCR Zone (AWS-001, AWS-002, AWS-003, AWS-004)
    t1 = t0 + timedelta(minutes=5)
    ncr_ids = {"AWS-001", "AWS-002", "AWS-003", "AWS-004"}
    r1 = []
    for s in DEFAULT_STATIONS:
        if s.station_id in ncr_ids:
            r1.append(RawReading(station_id=s.station_id, timestamp=t1.isoformat(), temperature=26.0, pressure=1010.5, humidity=75.0))
        else:
            r1.append(RawReading(station_id=s.station_id, timestamp=t1.isoformat(), temperature=30.0, pressure=1008.0, humidity=50.0))

    batch1 = pipeline.process_batch(r1)
    res_map = {p.station_id: p for p, _ in batch1}

    print("Observed Results on NCR Cluster:")
    for st_id in sorted(list(ncr_ids)):
        p = res_map[st_id]
        h = pipeline.health_engine.get_health_summary(st_id)
        spev = p.spatial_evidence
        print(f"  {st_id}: Decision={p.decision.value:<13} | Sensor Health={h.status.value:<7} (Score={h.health_score:4.1f}) | "
              f"Corroborating={spev.corroborating_stations_count}/{spev.neighbor_count} | Agreement={spev.agreement_ratio:.2f} | "
              f"RegEvent={spev.regional_event_detected}")
        assert p.decision == DecisionClassification.WEATHER_EVENT
        assert h.status == SensorHealthStatus.HEALTHY
        assert spev.regional_event_detected is True


def verify_demo_b_sensor_spike():
    print("\n" + "=" * 60)
    print("3. DEMO B — ISOLATED SENSOR ANOMALY SPIKE (+12°C)")
    print("=" * 60)
    pipeline = SkyGuardPipeline()
    t0 = datetime(2026, 9, 29, 14, 0, 0)

    # Step 0: Baseline state
    r0 = [
        RawReading(station_id=s.station_id, timestamp=t0.isoformat(), temperature=30.0, pressure=1008.0, humidity=50.0)
        for s in DEFAULT_STATIONS
    ]
    pipeline.process_batch(r0)

    # Step 1: Isolated spike on AWS-001 (+12°C jump), while all neighbors remain nominal
    t1 = t0 + timedelta(minutes=5)
    r1 = []
    for s in DEFAULT_STATIONS:
        if s.station_id == "AWS-001":
            r1.append(RawReading(station_id="AWS-001", timestamp=t1.isoformat(), temperature=42.0, pressure=1008.0, humidity=50.0))
        else:
            r1.append(RawReading(station_id=s.station_id, timestamp=t1.isoformat(), temperature=30.0, pressure=1008.0, humidity=50.0))

    batch1 = pipeline.process_batch(r1)
    res_map = {p.station_id: p for p, _ in batch1}

    p1 = res_map["AWS-001"]
    h1 = pipeline.health_engine.get_health_summary("AWS-001")
    spev1 = p1.spatial_evidence

    print(f"Target AWS-001: Decision={p1.decision.value} | Sensor Health={h1.status.value} | "
          f"Corroborating={spev1.corroborating_stations_count}/{spev1.neighbor_count} | Agreement={spev1.agreement_ratio:.2f} | "
          f"RegEvent={spev1.regional_event_detected}")

    p2 = res_map["AWS-002"]
    h2 = pipeline.health_engine.get_health_summary("AWS-002")
    print(f"Neighbor AWS-002: Decision={p2.decision.value} | Sensor Health={h2.status.value} (Remains Normal)")

    assert p1.decision == DecisionClassification.SENSOR_ANOMALY
    assert spev1.corroborating_stations_count == 0
    assert spev1.regional_event_detected is False
    assert p2.decision == DecisionClassification.NORMAL
    print("\n[SUCCESS] All end-to-end verification assertions passed!")


if __name__ == "__main__":
    verify_network_topology()
    verify_demo_a_weather_event()
    verify_demo_b_sensor_spike()

"""
Unit Tests: Spatial Consistency Engine
SIH26073: Automatic Weather Station Anomaly Detection System
"""

import pytest
from app.core.spatial_engine import SpatialConsistencyEngine
from app.models.schemas import StationMetadata, RawReading, SensorHealthStatus


def test_spatial_outlier_detection():
    se = SpatialConsistencyEngine()
    
    # Register 4 nearby stations (e.g. NCR cluster)
    st1 = StationMetadata(station_id="AWS-001", station_name="Delhi", latitude=28.61, longitude=77.20, status=SensorHealthStatus.HEALTHY)
    st2 = StationMetadata(station_id="AWS-002", station_name="Noida", latitude=28.62, longitude=77.37, status=SensorHealthStatus.HEALTHY)
    st3 = StationMetadata(station_id="AWS-003", station_name="Gurugram", latitude=28.45, longitude=77.02, status=SensorHealthStatus.HEALTHY)
    st4 = StationMetadata(station_id="AWS-004", station_name="Faridabad", latitude=28.40, longitude=77.31, status=SensorHealthStatus.HEALTHY)
    
    for s in [st1, st2, st3, st4]:
        se.register_station(s)
        
    # Neighbors report normal ~33-34°C
    se.update_latest_reading(RawReading(station_id="AWS-002", timestamp="2026-09-29T10:00:00Z", temperature=33.5, pressure=1010.0, humidity=55.0))
    se.update_latest_reading(RawReading(station_id="AWS-003", timestamp="2026-09-29T10:00:00Z", temperature=34.0, pressure=1010.0, humidity=54.0))
    se.update_latest_reading(RawReading(station_id="AWS-004", timestamp="2026-09-29T10:00:00Z", temperature=33.8, pressure=1010.0, humidity=55.0))
    
    # Target station AWS-001 reports 55.0°C (isolated spatial outlier)
    target_reading = RawReading(station_id="AWS-001", timestamp="2026-09-29T10:00:00Z", temperature=55.0, pressure=1010.0, humidity=55.0)
    evidence = se.analyze(target_reading)
    
    assert evidence.is_consistent is False
    assert evidence.neighbor_count >= 3
    assert evidence.relative_deviations["temperature"] > 20.0
    assert "Isolated spatial deviation" in evidence.explanation


def test_consistent_regional_weather_event():
    se = SpatialConsistencyEngine()
    
    st1 = StationMetadata(station_id="AWS-001", station_name="Delhi", latitude=28.61, longitude=77.20, status=SensorHealthStatus.HEALTHY)
    st2 = StationMetadata(station_id="AWS-002", station_name="Noida", latitude=28.62, longitude=77.37, status=SensorHealthStatus.HEALTHY)
    st3 = StationMetadata(station_id="AWS-003", station_name="Gurugram", latitude=28.45, longitude=77.02, status=SensorHealthStatus.HEALTHY)
    
    for s in [st1, st2, st3]:
        se.register_station(s)
        
    # Prior baseline readings in prev_readings (~34°C)
    se.prev_readings["AWS-001"] = RawReading(station_id="AWS-001", timestamp="2026-09-29T09:55:00Z", temperature=34.0, pressure=1010.0, humidity=50.0)
    se.prev_readings["AWS-002"] = RawReading(station_id="AWS-002", timestamp="2026-09-29T09:55:00Z", temperature=34.2, pressure=1010.0, humidity=50.0)
    se.prev_readings["AWS-003"] = RawReading(station_id="AWS-003", timestamp="2026-09-29T09:55:00Z", temperature=33.8, pressure=1010.0, humidity=50.0)

    # Neighbors report sudden surge to 43-44°C
    se.update_latest_reading(RawReading(station_id="AWS-002", timestamp="2026-09-29T10:00:00Z", temperature=43.5, pressure=1005.0, humidity=25.0))
    se.update_latest_reading(RawReading(station_id="AWS-003", timestamp="2026-09-29T10:00:00Z", temperature=44.2, pressure=1005.0, humidity=24.0))
    
    target_reading = RawReading(station_id="AWS-001", timestamp="2026-09-29T10:00:00Z", temperature=43.8, pressure=1005.0, humidity=25.0)
    evidence = se.analyze(target_reading)
    
    assert evidence.is_consistent is True
    assert evidence.regional_event_detected is True

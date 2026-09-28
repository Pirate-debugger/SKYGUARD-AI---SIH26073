"""
Unit Tests: Temporal Analysis Engine
SIH26073: Automatic Weather Station Anomaly Detection System
"""

import pytest
from datetime import datetime, timedelta
from app.core.temporal_engine import TemporalEngine
from app.models.schemas import RawReading


def test_temperature_spike_detection():
    te = TemporalEngine()
    st_id = "AWS-001"
    base_time = datetime(2026, 9, 29, 10, 0, 0)
    
    # Establish warm baseline (normal readings ~30°C)
    for i in range(10):
        t = base_time + timedelta(minutes=5 * i)
        r = RawReading(station_id=st_id, timestamp=t.isoformat(), temperature=30.0 + (i % 2)*0.2, pressure=1010.0, humidity=50.0)
        te.analyze(r)
        te.commit_reading(r)
        
    # Sudden abrupt spike to 55°C
    spike_time = base_time + timedelta(minutes=50)
    spike_reading = RawReading(station_id=st_id, timestamp=spike_time.isoformat(), temperature=55.0, pressure=1010.0, humidity=50.0)
    evidence = te.analyze(spike_reading)
    
    assert evidence.spike_detected is True
    assert evidence.rates_of_change["temperature"] > 2.5
    assert evidence.robust_z_scores["temperature"] > 3.5


def test_frozen_sensor_detection():
    te = TemporalEngine()
    st_id = "AWS-002"
    base_time = datetime(2026, 9, 29, 10, 0, 0)
    
    # 7 identical humidity readings
    evidence = None
    for i in range(7):
        t = base_time + timedelta(minutes=5 * i)
        r = RawReading(station_id=st_id, timestamp=t.isoformat(), temperature=25.0 + i*0.1, pressure=1010.0, humidity=61.0)
        evidence = te.analyze(r)
        te.commit_reading(r)
        
    assert evidence is not None
    assert evidence.freeze_detected is True
    assert evidence.frozen_duration_steps["humidity"] >= 4


def test_calibration_drift_detection():
    te = TemporalEngine()
    st_id = "AWS-003"
    base_time = datetime(2026, 9, 29, 10, 0, 0)
    
    # Systematic creeping drift of +0.35°C per step over 15 steps
    evidence = None
    for i in range(15):
        t = base_time + timedelta(minutes=5 * i)
        drift_temp = 25.0 + i * 0.35
        r = RawReading(station_id=st_id, timestamp=t.isoformat(), temperature=drift_temp, pressure=1010.0, humidity=50.0)
        evidence = te.analyze(r)
        te.commit_reading(r)
        
    assert evidence is not None
    assert evidence.drift_detected is True
    assert evidence.trend_slopes["temperature"] > 0.05

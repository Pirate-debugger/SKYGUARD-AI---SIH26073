"""
Unit Tests: Data Quality Engine
SIH26073: Automatic Weather Station Anomaly Detection System
"""

import pytest
from app.core.data_quality import DataQualityEngine
from app.models.schemas import RawReading, DataQualityStatus


def test_valid_reading():
    dq = DataQualityEngine()
    reading = RawReading(
        station_id="AWS-001",
        timestamp="2026-09-29T10:00:00Z",
        temperature=28.5,
        pressure=1008.2,
        humidity=62.0
    )
    result = dq.validate_reading(reading)
    assert result.status == DataQualityStatus.VALID
    assert result.is_valid is True
    assert len(result.issues) == 0


def test_impossible_physical_ranges():
    dq = DataQualityEngine()
    
    # Extreme high temperature
    r1 = RawReading(station_id="AWS-001", timestamp="2026-09-29T10:00:00Z", temperature=92.5, pressure=1010.0, humidity=50.0)
    res1 = dq.validate_reading(r1)
    assert res1.status == DataQualityStatus.INVALID
    assert "temperature" in res1.flagged_parameters
    assert any("Physically impossible" in issue for issue in res1.issues)

    # Impossible negative humidity
    r2 = RawReading(station_id="AWS-001", timestamp="2026-09-29T10:05:00Z", temperature=25.0, pressure=1010.0, humidity=-15.0)
    res2 = dq.validate_reading(r2)
    assert res2.status == DataQualityStatus.INVALID
    assert "humidity" in res2.flagged_parameters

    # Impossible pressure
    r3 = RawReading(station_id="AWS-001", timestamp="2026-09-29T10:10:00Z", temperature=25.0, pressure=350.0, humidity=50.0)
    res3 = dq.validate_reading(r3)
    assert res3.status == DataQualityStatus.INVALID
    assert "pressure" in res3.flagged_parameters


def test_missing_values():
    dq = DataQualityEngine()
    reading = RawReading(
        station_id="AWS-001",
        timestamp="2026-09-29T10:00:00Z",
        temperature=None,
        pressure=1008.0,
        humidity=60.0
    )
    res = dq.validate_reading(reading)
    assert res.status == DataQualityStatus.MISSING
    assert "temperature" in res.flagged_parameters


def test_duplicate_and_malformed_timestamp():
    dq = DataQualityEngine()
    # Malformed
    r_bad = RawReading(station_id="AWS-001", timestamp="not-a-timestamp", temperature=25.0, pressure=1010.0, humidity=50.0)
    res_bad = dq.validate_reading(r_bad)
    assert res_bad.status == DataQualityStatus.INVALID
    assert any("Malformed timestamp" in issue for issue in res_bad.issues)

    # Duplicate
    r1 = RawReading(station_id="AWS-002", timestamp="2026-09-29T12:00:00Z", temperature=25.0, pressure=1010.0, humidity=50.0)
    dq.validate_reading(r1)
    res_dup = dq.validate_reading(r1)
    assert res_dup.status == DataQualityStatus.SUSPICIOUS
    assert any("Duplicate timestamp" in issue for issue in res_dup.issues)

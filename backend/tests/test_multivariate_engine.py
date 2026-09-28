"""
Unit Tests: Multivariate Consistency Engine
SIH26073: Automatic Weather Station Anomaly Detection System
"""

import pytest
from app.core.multivariate_engine import MultivariateConsistencyEngine
from app.models.schemas import RawReading


def test_normal_multivariate_consistency():
    mve = MultivariateConsistencyEngine()
    reading = RawReading(
        station_id="AWS-001",
        timestamp="2026-09-29T10:00:00Z",
        temperature=28.0,
        pressure=1008.0,
        humidity=65.0
    )
    evidence = mve.analyze(reading)
    assert evidence.is_consistent is True
    assert evidence.consistency_score >= 0.7
    assert len(evidence.discordant_parameters) == 0


def test_dewpoint_thermodynamic_violation():
    mve = MultivariateConsistencyEngine()
    # Dewpoint cannot exceed air temperature.
    # At 15°C with 99% RH, dewpoint is ~14.8°C (physically normal).
    # But if dewpoint formula evaluates higher than T due to impossible inputs or sensor glitch:
    # E.g. T = 12.0, dewpoint calculation check:
    dew = mve.calculate_dewpoint(12.0, 99.0)
    assert dew is not None
    assert dew <= 12.0 + 0.5


def test_multivariate_decoupling_jump():
    mve = MultivariateConsistencyEngine()
    prev = RawReading(station_id="AWS-001", timestamp="2026-09-29T10:00:00Z", temperature=30.0, pressure=1010.0, humidity=60.0)
    # Sudden +25°C temperature leap while humidity and pressure remain perfectly static
    curr = RawReading(station_id="AWS-001", timestamp="2026-09-29T10:05:00Z", temperature=55.0, pressure=1010.0, humidity=60.0)
    
    evidence = mve.analyze(curr, prev)
    assert evidence.is_consistent is False
    assert "temperature" in evidence.discordant_parameters
    assert "Multivariate decoupling" in evidence.explanation

"""
Integration & Regression Tests: Database Persistence & API Endpoints
SIH26073: Automatic Weather Station Anomaly Detection System

Validates:
- Database schema and UNIQUE(station_id, timestamp) constraint
- Non-destructive CSV ingestion with row-level error reporting
- Batch ingestion endpoint (/api/ingest/batch)
- Diagnostics and system health endpoints
"""

import pytest
import tempfile
import os
from fastapi.testclient import TestClient
from app.main import app
from app.database.db import DatabaseManager
from app.models.schemas import (
    ProcessedReading,
    DataQualityResult,
    DataQualityStatus,
    TemporalEvidence,
    MultivariateEvidence,
    SpatialEvidence,
    MLEvidence,
    DecisionClassification,
    ProbableCause,
    SeverityLevel,
    EvidenceStrength
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.mark.asyncio
async def test_database_unique_constraint_and_restart():
    """
    Verifies that readings table enforces UNIQUE(station_id, timestamp) constraint
    to prevent duplicate rows across stream restarts or re-ingestion.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_file = tmp.name

    try:
        db = DatabaseManager(db_path=db_file)
        await db.init_db()
        
        pr1 = ProcessedReading(
            reading_id="r-001",
            station_id="AWS-001",
            timestamp="2026-04-15T12:00:00Z",
            temperature=32.5,
            pressure=1008.0,
            humidity=55.0,
            data_quality=DataQualityResult(status=DataQualityStatus.VALID),
            temporal_evidence=TemporalEvidence(),
            multivariate_evidence=MultivariateEvidence(),
            spatial_evidence=SpatialEvidence(),
            ml_evidence=MLEvidence(),
            decision=DecisionClassification.NORMAL,
            probable_cause=ProbableCause.NORMAL_OPERATION,
            severity=SeverityLevel.LOW,
            confidence=0.95,
            evidence_strength=EvidenceStrength.HIGH,
            explanation="Normal observation",
            model_version="v2.0.0",
            ruleset_version="v2.0.0",
            feature_version="v2.0.0"
        )
        
        # First save
        await db.save_reading(pr1)
        
        # Second save with exact same (station_id, timestamp), updated reading_id & value
        pr2 = pr1.model_copy()
        pr2.reading_id = "r-002"
        pr2.temperature = 32.8
        await db.save_reading(pr2)
        
        # Verify deduplication / replacement: exactly 1 row exists for this station+timestamp
        readings = await db.get_station_readings("AWS-001", limit=10)
        assert len(readings) == 1
        assert readings[0]["temperature"] == 32.8
        assert readings[0]["reading_id"] == "r-002"

        # Verify restart persistence by opening new connection to the same file
        db2 = DatabaseManager(db_path=db_file)
        await db2.init_db()
        history = await db2.get_station_readings("AWS-001", limit=10)
        assert len(history) == 1
        assert history[0]["temperature"] == 32.8

    finally:
        if os.path.exists(db_file):
            try:
                os.remove(db_file)
            except Exception:
                pass


def test_csv_ingest_row_level_error_reporting(client):
    """
    Verifies non-destructive CSV upload returns row-level diagnostics:
    records_received, records_processed, records_failed, and specific row error details.
    """
    csv_content = (
        "station_id,timestamp,temperature,pressure,humidity\n"
        "AWS-001,2026-04-15T10:00:00Z,32.5,1008.2,55.0\n"
        "AWS-002,2026-04-15T10:00:00Z,33.0,1008.0,54.0\n"
        "AWS-003,invalid-date,31.0,1007.5,56.0\n"  # Invalid timestamp
        "AWS-004,2026-04-15T10:00:00Z,bad_num,1008.0,55.0\n"  # Non-numeric temperature
        "AWS-005,2026-04-15T10:00:00Z,32.8,1008.1,55.2\n"
    )
    
    files = {"file": ("test_weather.csv", csv_content.encode("utf-8"), "text/csv")}
    response = client.post("/api/ingest/csv", files=files)
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["records_received"] == 5
    assert data["records_processed"] == 3
    assert data["records_failed"] == 2
    assert len(data["errors"]) == 2
    
    # Check row-level error reporting
    err1 = data["errors"][0]
    assert err1["row_number"] == 4
    assert err1["column"] == "timestamp"
    
    err2 = data["errors"][1]
    assert err2["row_number"] == 5
    assert err2["column"] == "temperature"


def test_batch_ingest_and_diagnostics_endpoints(client):
    """
    Verifies /api/ingest/batch, /api/health, and /api/diagnostics/config endpoints.
    """
    # 1. Health endpoint
    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "OPERATIONAL"
    
    # 2. Config diagnostics
    diag_resp = client.get("/api/diagnostics/config")
    assert diag_resp.status_code == 200
    cfg = diag_resp.json()
    assert "version_info" in cfg
    assert "physical_limits" in cfg
    assert "spatial_config" in cfg
    assert cfg["spatial_config"]["regional_event_ratio"] == 0.65
    
    # 3. Synchronized batch ingestion
    t = "2026-04-15T11:00:00Z"
    batch_payload = [
        {"station_id": "AWS-001", "timestamp": t, "temperature": 31.0, "pressure": 1009.0, "humidity": 58.0},
        {"station_id": "AWS-002", "timestamp": t, "temperature": 31.2, "pressure": 1009.1, "humidity": 57.5},
    ]
    batch_resp = client.post("/api/ingest/batch", json=batch_payload)
    assert batch_resp.status_code == 200
    res_data = batch_resp.json()
    assert res_data["status"] == "SUCCESS"
    assert res_data["count"] == 2
    assert len(res_data["results"]) == 2
    assert res_data["results"][0]["station_id"] == "AWS-001"

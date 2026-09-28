"""
SQLite Database Layer for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Provides asynchronous persistence for:
- Registered AWS Stations
- Historical Ingested & Processed Readings (with UNIQUE constraint on station_id + timestamp)
- Active & Historical Anomaly Alerts
- Station Health & Degradation Summaries
"""

import os
import json
import aiosqlite
from typing import List, Dict, Optional, Any
from app.config import DB_PATH
from app.models.schemas import StationMetadata, ProcessedReading, AlertRecord, SensorHealthSummary


class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    async def init_db(self):
        """Initializes tables, unique constraints, and indices."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                station_id TEXT PRIMARY KEY,
                station_name TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                elevation_m REAL NOT NULL,
                station_type TEXT NOT NULL,
                region TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """)

            await db.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                reading_id TEXT PRIMARY KEY,
                station_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                temperature REAL,
                pressure REAL,
                humidity REAL,
                decision TEXT NOT NULL,
                probable_cause TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence REAL NOT NULL,
                evidence_strength TEXT NOT NULL,
                explanation TEXT NOT NULL,
                data_quality TEXT NOT NULL,
                imputed_values TEXT,
                model_version TEXT NOT NULL,
                ruleset_version TEXT NOT NULL,
                feature_version TEXT NOT NULL,
                FOREIGN KEY(station_id) REFERENCES stations(station_id),
                UNIQUE(station_id, timestamp)
            );
            """)

            await db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id TEXT PRIMARY KEY,
                station_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                decision TEXT NOT NULL,
                probable_cause TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence REAL NOT NULL,
                evidence_strength TEXT NOT NULL,
                flagged_parameters TEXT NOT NULL,
                observed_values TEXT NOT NULL,
                expected_values TEXT NOT NULL,
                deviations TEXT NOT NULL,
                explanation TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0,
                FOREIGN KEY(station_id) REFERENCES stations(station_id)
            );
            """)

            await db.execute("CREATE INDEX IF NOT EXISTS idx_readings_station ON readings(station_id);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp);")
            await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_station ON alerts(station_id);")

            # Safe column additions if migrating from previous prototype schema
            for col, col_type in [
                ("evidence_strength", "TEXT DEFAULT 'MEDIUM'"),
                ("imputed_values", "TEXT DEFAULT '{}'"),
                ("model_version", "TEXT DEFAULT 'v2.0.0'"),
                ("ruleset_version", "TEXT DEFAULT 'v2.0.0'"),
                ("feature_version", "TEXT DEFAULT 'v2.0.0'"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE readings ADD COLUMN {col} {col_type};")
                except Exception:
                    pass
            for col, col_type in [
                ("evidence_strength", "TEXT DEFAULT 'MEDIUM'"),
            ]:
                try:
                    await db.execute(f"ALTER TABLE alerts ADD COLUMN {col} {col_type};")
                except Exception:
                    pass

            await db.commit()

    async def save_station(self, station: StationMetadata):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            INSERT OR REPLACE INTO stations 
            (station_id, station_name, latitude, longitude, elevation_m, station_type, region, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                station.station_id,
                station.station_name,
                station.latitude,
                station.longitude,
                station.elevation_m,
                station.station_type,
                station.region,
                station.status.value
            ))
            await db.commit()

    async def save_reading(self, processed: ProcessedReading):
        async with aiosqlite.connect(self.db_path) as db:
            imputed_json = json.dumps({k: v.model_dump() for k, v in processed.imputed_values.items()}) if processed.imputed_values else None
            dq_json = json.dumps(processed.data_quality.model_dump())
            await db.execute("""
            INSERT OR REPLACE INTO readings
            (reading_id, station_id, timestamp, temperature, pressure, humidity, decision, probable_cause, severity, confidence, evidence_strength, explanation, data_quality, imputed_values, model_version, ruleset_version, feature_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                processed.reading_id,
                processed.station_id,
                processed.timestamp,
                processed.temperature,
                processed.pressure,
                processed.humidity,
                processed.decision.value,
                processed.probable_cause.value,
                processed.severity.value,
                processed.confidence,
                processed.evidence_strength.value,
                processed.explanation,
                dq_json,
                imputed_json,
                processed.model_version,
                processed.ruleset_version,
                processed.feature_version
            ))
            await db.commit()

    async def save_alert(self, alert: AlertRecord):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            INSERT OR REPLACE INTO alerts
            (alert_id, station_id, timestamp, decision, probable_cause, severity, confidence, evidence_strength, flagged_parameters, observed_values, expected_values, deviations, explanation, recommended_action, acknowledged)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id,
                alert.station_id,
                alert.timestamp,
                alert.decision.value,
                alert.probable_cause.value,
                alert.severity.value,
                alert.confidence,
                alert.evidence_strength.value,
                json.dumps(alert.flagged_parameters),
                json.dumps(alert.observed_values),
                json.dumps(alert.expected_values),
                json.dumps(alert.deviations),
                alert.explanation,
                alert.recommended_action.value,
                1 if alert.acknowledged else 0
            ))
            await db.commit()

    async def get_station_readings(self, station_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
            SELECT * FROM readings WHERE station_id = ? ORDER BY timestamp DESC LIMIT ?
            """, (station_id, limit))
            rows = await cursor.fetchall()
            return [dict(r) for r in reversed(rows)]

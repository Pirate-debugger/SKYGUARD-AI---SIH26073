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
                acknowledged_by TEXT,
                acknowledged_at TEXT,
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
                ("acknowledged_by", "TEXT"),
                ("acknowledged_at", "TEXT"),
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
            (alert_id, station_id, timestamp, decision, probable_cause, severity, confidence, evidence_strength, flagged_parameters, observed_values, expected_values, deviations, explanation, recommended_action, acknowledged, acknowledged_by, acknowledged_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id,
                alert.station_id,
                alert.timestamp,
                alert.decision.value if hasattr(alert.decision, "value") else str(alert.decision),
                alert.probable_cause.value if hasattr(alert.probable_cause, "value") else str(alert.probable_cause),
                alert.severity.value if hasattr(alert.severity, "value") else str(alert.severity),
                alert.confidence,
                alert.evidence_strength.value if hasattr(alert.evidence_strength, "value") else str(alert.evidence_strength),
                json.dumps(alert.flagged_parameters),
                json.dumps(alert.observed_values),
                json.dumps(alert.expected_values),
                json.dumps(alert.deviations),
                alert.explanation,
                alert.recommended_action.value if hasattr(alert.recommended_action, "value") else str(alert.recommended_action),
                1 if alert.acknowledged else 0,
                alert.acknowledged_by,
                alert.acknowledged_at
            ))
            await db.commit()

    async def acknowledge_alert(
        self,
        alert_id: str,
        operator_name: str = "Operator",
        acknowledged_by: Optional[str] = None,
        acknowledged_at: Optional[str] = None
    ) -> bool:
        """Persists alert acknowledgement state into the database."""
        name = acknowledged_by or operator_name
        if not acknowledged_at:
            from datetime import datetime, timezone
            acknowledged_at = datetime.now(timezone.utc).isoformat()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
            UPDATE alerts 
            SET acknowledged = 1, acknowledged_by = ?, acknowledged_at = ?
            WHERE alert_id = ?
            """, (name, acknowledged_at, alert_id))
            await db.commit()
            return cursor.rowcount > 0

    async def get_alerts(self, limit: int = 50, acknowledged: Optional[bool] = None) -> List[AlertRecord]:
        """Retrieves persistent alerts from SQLite database."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if acknowledged is not None:
                ack_int = 1 if acknowledged else 0
                cursor = await db.execute("""
                SELECT * FROM alerts WHERE acknowledged = ? ORDER BY timestamp DESC LIMIT ?
                """, (ack_int, limit))
            else:
                cursor = await db.execute("""
                SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?
                """, (limit,))
            rows = await cursor.fetchall()
            alerts = []
            for r in rows:
                d = dict(r)
                alerts.append(AlertRecord(
                    alert_id=d["alert_id"],
                    station_id=d["station_id"],
                    timestamp=d["timestamp"],
                    decision=d["decision"],
                    probable_cause=d["probable_cause"],
                    severity=d["severity"],
                    confidence=d["confidence"],
                    evidence_strength=d.get("evidence_strength", "MEDIUM"),
                    flagged_parameters=json.loads(d["flagged_parameters"]) if isinstance(d["flagged_parameters"], str) else d["flagged_parameters"],
                    observed_values=json.loads(d["observed_values"]) if isinstance(d["observed_values"], str) else d["observed_values"],
                    expected_values=json.loads(d["expected_values"]) if isinstance(d["expected_values"], str) else d["expected_values"],
                    deviations=json.loads(d["deviations"]) if isinstance(d["deviations"], str) else d["deviations"],
                    explanation=d["explanation"],
                    recommended_action=d["recommended_action"],
                    acknowledged=bool(d["acknowledged"]),
                    acknowledged_by=d.get("acknowledged_by"),
                    acknowledged_at=d.get("acknowledged_at")
                ))
            return alerts

    async def get_readings_count(self) -> int:
        """Returns total historical observations recorded in database."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM readings;")
            row = await cursor.fetchone()
            return int(row[0]) if row else 0

    async def get_station_readings(self, station_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
            SELECT * FROM readings WHERE station_id = ? ORDER BY timestamp DESC LIMIT ?
            """, (station_id, limit))
            rows = await cursor.fetchall()
            return [dict(r) for r in reversed(rows)]

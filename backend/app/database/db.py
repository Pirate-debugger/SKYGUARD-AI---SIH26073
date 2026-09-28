"""
SQLite Database Layer for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Provides asynchronous persistence for:
- Registered AWS Stations
- Historical Ingested & Processed Readings
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
        """Initializes tables and indices."""
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
                explanation TEXT NOT NULL,
                data_quality TEXT NOT NULL,
                imputed_values TEXT,
                model_version TEXT NOT NULL,
                FOREIGN KEY(station_id) REFERENCES stations(station_id)
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

    async def save_reading(self, reading: ProcessedReading):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            INSERT OR REPLACE INTO readings
            (reading_id, station_id, timestamp, temperature, pressure, humidity,
             decision, probable_cause, severity, confidence, explanation, data_quality, imputed_values, model_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                reading.reading_id,
                reading.station_id,
                reading.timestamp,
                reading.temperature,
                reading.pressure,
                reading.humidity,
                reading.decision.value,
                reading.probable_cause.value,
                reading.severity.value,
                reading.confidence,
                reading.explanation,
                json.dumps(reading.data_quality.model_dump()),
                json.dumps({k: v.model_dump() for k, v in reading.imputed_values.items()}),
                reading.model_version
            ))
            await db.commit()

    async def save_alert(self, alert: AlertRecord):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
            INSERT OR REPLACE INTO alerts
            (alert_id, station_id, timestamp, decision, probable_cause, severity,
             confidence, flagged_parameters, observed_values, expected_values, deviations, explanation, recommended_action, acknowledged)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                alert.alert_id,
                alert.station_id,
                alert.timestamp,
                alert.decision.value,
                alert.probable_cause.value,
                alert.severity.value,
                alert.confidence,
                json.dumps(alert.flagged_parameters),
                json.dumps(alert.observed_values),
                json.dumps(alert.expected_values),
                json.dumps(alert.deviations),
                alert.explanation,
                alert.recommended_action.value,
                1 if alert.acknowledged else 0
            ))
            await db.commit()

    async def get_all_stations(self) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM stations ORDER BY station_id ASC") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_recent_readings(self, station_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if station_id:
                query = "SELECT * FROM readings WHERE station_id = ? ORDER BY timestamp DESC LIMIT ?"
                params = (station_id, limit)
            else:
                query = "SELECT * FROM readings ORDER BY timestamp DESC LIMIT ?"
                params = (limit,)
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_recent_alerts(self, limit: int = 50) -> List[Dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,)) as cursor:
                rows = await cursor.fetchall()
                alerts = []
                for row in rows:
                    d = dict(row)
                    d["flagged_parameters"] = json.loads(d["flagged_parameters"])
                    d["observed_values"] = json.loads(d["observed_values"])
                    d["expected_values"] = json.loads(d["expected_values"])
                    d["deviations"] = json.loads(d["deviations"])
                    d["acknowledged"] = bool(d["acknowledged"])
                    alerts.append(d)
                return alerts

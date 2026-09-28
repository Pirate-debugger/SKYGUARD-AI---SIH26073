"""
Database Seeding Script for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Seeds the database and pipeline with default stations and 24 hours of warm-up historical telemetry:
- Establishes rolling temporal baselines
- Establishes spatial neighborhood medians
- Pre-warms sensor health trackers
"""

import asyncio
from datetime import datetime, timedelta
from app.database.db import DatabaseManager
from app.simulator.generator import DEFAULT_STATIONS, WeatherDataGenerator
from app.core.pipeline import SkyGuardPipeline


async def seed_initial_data(pipeline: SkyGuardPipeline, db: DatabaseManager):
    print("[Seed] Initializing database schema...")
    await db.init_db()

    print("[Seed] Registering 12 AWS stations...")
    for st in DEFAULT_STATIONS:
        pipeline.spatial_engine.register_station(st)
        await db.save_station(st)

    generator = WeatherDataGenerator(stations=DEFAULT_STATIONS)
    base_time = datetime(2026, 9, 28, 10, 0, 0)
    
    print("[Seed] Generating 24 warm-up reporting intervals per station...")
    for step in range(24):
        step_time = base_time + timedelta(minutes=5 * step)
        for st in DEFAULT_STATIONS:
            raw_reading, _ = generator.generate_reading_with_scenarios(st, step_time)
            processed, alert = pipeline.process_reading(raw_reading)
            await db.save_reading(processed)
            if alert:
                await db.save_alert(alert)

    print("[Seed] Initial data seeding complete. System fully operational.")


if __name__ == "__main__":
    p = SkyGuardPipeline()
    d = DatabaseManager()
    asyncio.run(seed_initial_data(p, d))

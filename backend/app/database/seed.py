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

    count = await db.get_readings_count()
    if count > 0:
        print(f"[Seed] Found {count} existing historical readings in database. Restoring operational state...")
        # Restore existing alerts
        existing_alerts = await db.get_alerts(limit=100)
        pipeline.alerts = list(reversed(existing_alerts))
        
        # Restore recent readings per station to rebuild temporal context and health state
        for st in DEFAULT_STATIONS:
            recent_readings = await db.get_station_readings(st.station_id, limit=30)
            for r_dict in recent_readings:
                from app.models.schemas import RawReading, DecisionClassification, ProbableCause
                raw = RawReading(
                    station_id=st.station_id,
                    timestamp=r_dict["timestamp"],
                    temperature=r_dict.get("temperature"),
                    pressure=r_dict.get("pressure"),
                    humidity=r_dict.get("humidity"),
                    latitude=st.latitude,
                    longitude=st.longitude,
                    elevation_m=st.elevation_m,
                    station_type=st.station_type,
                    region=st.region
                )
                pipeline.temporal_engine.commit_reading(raw)
                pipeline.spatial_engine.update_latest_reading(raw)
                pipeline.health_engine.update_and_get_health(
                    st.station_id,
                    DecisionClassification(r_dict["decision"]),
                    ProbableCause(r_dict["probable_cause"]),
                    r_dict["timestamp"]
                )
        print(f"[Seed] Restart recovery complete. Restored {len(pipeline.alerts)} alerts and active temporal context.")
        return

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

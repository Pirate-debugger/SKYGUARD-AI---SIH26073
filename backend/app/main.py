"""
FastAPI Main Application for SkyGuard AI
SIH26073: AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations

Provides RESTful and WebSocket APIs for:
- Telemetry ingestion (JSON & CSV)
- Real-time anomaly detection & decision fusion
- Spatial neighborhood analysis & thermodynamic verification
- Station health & degradation monitoring
- Real-time simulation & anomaly injection controls
- WebSocket live feed for operator dashboard
"""

import os
import io
import csv
import json
import asyncio
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.config import (
    VERSION_INFO, DB_PATH, PHYSICAL_LIMITS, MAX_RATE_OF_CHANGE_PER_MIN,
    TEMPORAL_CONFIG, CUSUM_CONFIG, SPATIAL_CONFIG, OFFLINE_CONFIG
)
from app.models.schemas import (
    RawReading,
    ProcessedReading,
    AlertRecord,
    SensorHealthSummary,
    NetworkOverview,
    StreamInjectionPayload,
    StationMetadata,
    SensorHealthStatus,
    CommunicationState,
    CsvIngestResult,
    CsvRowError
)
from app.core.pipeline import SkyGuardPipeline
from app.core.reporter import AnomalyReportGenerator
from app.simulator.generator import DEFAULT_STATIONS
from app.simulator.stream_manager import StreamSimulatorManager
from app.database.db import DatabaseManager
from app.database.seed import seed_initial_data


# Global Pipeline and Simulator instances
pipeline = SkyGuardPipeline()
db_manager = DatabaseManager()
stream_manager = StreamSimulatorManager(pipeline=pipeline, stations=DEFAULT_STATIONS)
report_generator = AnomalyReportGenerator()

# Connected WebSocket clients
active_websockets: List[WebSocket] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Seed warm-up data
    await seed_initial_data(pipeline, db_manager)
    
    # Register stream listener to push over WebSockets and save to DB
    async def on_stream_tick(packet: Dict[str, Any]):
        # Save to DB asynchronously
        for rd in packet.get("readings", []):
            try:
                processed_obj = ProcessedReading(**rd)
                await db_manager.save_reading(processed_obj)
            except Exception as e:
                print(f"[DB Stream Warning] Failed to persist reading: {e}")
        
        for alt in packet.get("alerts", []):
            try:
                alert_obj = AlertRecord(**alt)
                await db_manager.save_alert(alert_obj)
            except Exception as e:
                print(f"[DB Stream Warning] Failed to persist alert: {e}")
        
        # Broadcast to active WebSockets
        dead_sockets = []
        for ws in active_websockets:
            try:
                await ws.send_json(packet)
            except Exception:
                dead_sockets.append(ws)
        for dead in dead_sockets:
            if dead in active_websockets:
                active_websockets.remove(dead)

    stream_manager.add_listener(on_stream_tick)
    yield
    # Shutdown
    await stream_manager.stop()


app = FastAPI(
    title="SkyGuard AI — SIH26073 API",
    description="AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations",
    version=VERSION_INFO.model_version,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- System Info & Health ---
@app.get("/api/health")
async def get_health():
    return {
        "status": "OPERATIONAL",
        "system": "SkyGuard AI",
        "problem_statement": VERSION_INFO.problem_statement_id,
        "versions": VERSION_INFO.model_dump(),
        "stream_running": stream_manager.is_running,
        "stations_monitored": len(DEFAULT_STATIONS)
    }


# --- Network Overview Metrics ---
@app.get("/api/network/overview", response_model=NetworkOverview)
async def get_network_overview():
    health_dict = pipeline.health_engine.get_all_health_summaries()
    
    healthy = 0
    watch = 0
    degraded = 0
    critical = 0
    offline = 0
    
    for st in DEFAULT_STATIONS:
        h = health_dict.get(st.station_id)
        if not h:
            healthy += 1
            continue
        if h.status == SensorHealthStatus.HEALTHY:
            healthy += 1
        elif h.status == SensorHealthStatus.WATCH:
            watch += 1
        elif h.status == SensorHealthStatus.DEGRADED:
            degraded += 1
        elif h.status == SensorHealthStatus.CRITICAL:
            critical += 1
        elif h.status == SensorHealthStatus.OFFLINE:
            offline += 1

    active_anomalies = sum(1 for a in pipeline.alerts if not a.acknowledged and a.decision == "SENSOR_ANOMALY")
    weather_events = sum(1 for a in pipeline.alerts if a.decision == "WEATHER_EVENT")

    return NetworkOverview(
        total_stations=len(DEFAULT_STATIONS),
        healthy_count=healthy,
        watch_count=watch,
        degraded_count=degraded,
        critical_count=critical,
        offline_count=offline,
        active_anomalies_count=active_anomalies,
        alerts_today_count=len(pipeline.alerts),
        weather_events_count=weather_events,
        system_status="OPERATIONAL"
    )


# --- Station APIs ---
@app.get("/api/stations")
async def list_stations():
    stations_data = []
    health_dict = pipeline.health_engine.get_all_health_summaries()

    for st in DEFAULT_STATIONS:
        h = health_dict.get(st.station_id)
        last_reading = None
        history = pipeline.processed_history.get(st.station_id, [])
        if history:
            last_reading = history[-1].model_dump()
        
        stations_data.append({
            "metadata": st.model_dump(),
            "health": h.model_dump() if h else None,
            "latest_reading": last_reading
        })
    return stations_data


@app.get("/api/stations/{station_id}")
async def get_station_detail(station_id: str):
    st = next((s for s in DEFAULT_STATIONS if s.station_id == station_id), None)
    if not st:
        raise HTTPException(status_code=404, detail="Station not found")
        
    health = pipeline.health_engine.get_or_create_tracker(station_id).evaluate_health()
    history = pipeline.processed_history.get(station_id, [])
    neighbors = pipeline.spatial_engine.find_nearest_neighbors(station_id)
    
    return {
        "metadata": st.model_dump(),
        "health": health.model_dump(),
        "neighbors": [{"station_id": nid, "distance_km": round(dist, 1)} for nid, dist in neighbors],
        "readings_history": [r.model_dump() for r in history[-30:]]
    }


# --- Ingestion APIs ---
@app.post("/api/ingest/reading")
async def ingest_single_reading(reading: RawReading):
    processed, alert = pipeline.process_reading(reading)
    await db_manager.save_reading(processed)
    if alert:
        await db_manager.save_alert(alert)
    return {
        "processed": processed.model_dump(),
        "alert": alert.model_dump() if alert else None
    }


@app.post("/api/ingest/batch")
async def ingest_batch_readings(readings: List[RawReading]):
    """Ingests a batch of observations across stations, evaluating via synchronized spatial snapshots."""
    batch_results = pipeline.process_batch(readings)
    for processed, alert in batch_results:
        await db_manager.save_reading(processed)
        if alert:
            await db_manager.save_alert(alert)
    return {
        "status": "SUCCESS",
        "count": len(batch_results),
        "results": [p.model_dump() for p, _ in batch_results[:50]],
        "alerts_generated": sum(1 for _, a in batch_results if a is not None)
    }


@app.post("/api/ingest/csv", response_model=CsvIngestResult)
async def ingest_csv_file(file: UploadFile = File(...)):
    """
    Ingests AWS CSV telemetry file.
    Does NOT silently discard malformed rows. Returns records_received,
    records_processed, records_failed, and detailed row errors.
    """
    content = await file.read()
    try:
        text = content.decode("utf-8")
        reader = list(csv.DictReader(io.StringIO(text)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV file: {str(e)}")

    valid_readings: List[RawReading] = []
    errors: List[CsvRowError] = []
    row_num = 1  # 1-indexed (header is row 1, data starts row 2)

    for row in reader:
        row_num += 1
        st_id = row.get("station_id") or row.get("station")
        if not st_id or not st_id.strip():
            errors.append(CsvRowError(
                row_number=row_num,
                column="station_id",
                error_type="MISSING_STATION_ID",
                message="station_id is empty or missing"
            ))
            continue

        ts = row.get("timestamp") or row.get("datetime")
        if not ts or not ts.strip():
            errors.append(CsvRowError(
                row_number=row_num,
                column="timestamp",
                error_type="MISSING_TIMESTAMP",
                message="timestamp is empty or missing"
            ))
            continue

        try:
            datetime.fromisoformat(ts.strip().replace("Z", "+00:00"))
        except Exception:
            errors.append(CsvRowError(
                row_number=row_num,
                column="timestamp",
                error_type="INVALID_TIMESTAMP_FORMAT",
                message=f"Invalid timestamp format: '{ts.strip()}'. Expected ISO-8601 (YYYY-MM-DDTHH:MM:SSZ)"
            ))
            continue

        # Parse numeric parameters
        t_val = None
        p_val = None
        rh_val = None
        has_num_err = False

        if row.get("temperature") not in (None, "", "null"):
            try:
                t_val = float(row["temperature"])
            except ValueError:
                errors.append(CsvRowError(
                    row_number=row_num,
                    column="temperature",
                    error_type="INVALID_NUMERIC_FORMAT",
                    message=f"Non-numeric temperature value: {row['temperature']}"
                ))
                has_num_err = True

        if row.get("pressure") not in (None, "", "null"):
            try:
                p_val = float(row["pressure"])
            except ValueError:
                errors.append(CsvRowError(
                    row_number=row_num,
                    column="pressure",
                    error_type="INVALID_NUMERIC_FORMAT",
                    message=f"Non-numeric pressure value: {row['pressure']}"
                ))
                has_num_err = True

        if row.get("humidity") not in (None, "", "null"):
            try:
                rh_val = float(row["humidity"])
            except ValueError:
                errors.append(CsvRowError(
                    row_number=row_num,
                    column="humidity",
                    error_type="INVALID_NUMERIC_FORMAT",
                    message=f"Non-numeric humidity value: {row['humidity']}"
                ))
                has_num_err = True

        if has_num_err:
            continue

        valid_readings.append(RawReading(
            station_id=st_id.strip(),
            timestamp=ts.strip(),
            temperature=t_val,
            pressure=p_val,
            humidity=rh_val
        ))

    # Process valid readings synchronously through pipeline
    processed_results = []
    if valid_readings:
        batch_results = pipeline.process_batch(valid_readings)
        for processed, alert in batch_results:
            await db_manager.save_reading(processed)
            if alert:
                await db_manager.save_alert(alert)
            processed_results.append({
                "station_id": processed.station_id,
                "timestamp": processed.timestamp,
                "decision": processed.decision.value,
                "probable_cause": processed.probable_cause.value,
                "confidence": processed.confidence
            })

    return CsvIngestResult(
        status="SUCCESS",
        records_received=len(reader),
        records_processed=len(valid_readings),
        records_failed=len(errors),
        errors=errors[:50],
        sample_processed=processed_results[:50]
    )


# --- Configuration & Diagnostics ---
@app.get("/api/diagnostics/config")
async def get_system_diagnostics():
    return {
        "version_info": VERSION_INFO.model_dump(),
        "physical_limits": PHYSICAL_LIMITS,
        "max_rates_of_change": MAX_RATE_OF_CHANGE_PER_MIN,
        "temporal_config": TEMPORAL_CONFIG,
        "cusum_config": CUSUM_CONFIG,
        "spatial_config": SPATIAL_CONFIG,
        "offline_config": OFFLINE_CONFIG
    }


# --- Alert APIs ---
@app.get("/api/alerts")
async def list_alerts(limit: int = 50, acknowledged: Optional[bool] = None):
    if pipeline.alerts:
        alerts = pipeline.alerts
        if acknowledged is not None:
            alerts = [a for a in alerts if a.acknowledged == acknowledged]
        return [a.model_dump() for a in reversed(alerts[-limit:])]
    else:
        # Fallback to persistent SQLite DB if memory is empty after restart
        db_alerts = await db_manager.get_alerts(limit=limit, acknowledged=acknowledged)
        return [a.model_dump() for a in db_alerts]


@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, operator_name: str = "Operator"):
    ack_time = datetime.now(timezone.utc).isoformat()
    found = False
    for a in pipeline.alerts:
        if a.alert_id == alert_id:
            a.acknowledged = True
            a.acknowledged_by = operator_name
            a.acknowledged_at = ack_time
            found = True
            break
            
    # Persist in SQLite database so acknowledgement survives restart
    try:
        await db_manager.acknowledge_alert(alert_id, operator_name, ack_time)
        return {"status": "SUCCESS", "alert_id": alert_id, "acknowledged": True}
    except Exception as e:
        if found:
            return {"status": "SUCCESS", "alert_id": alert_id, "acknowledged": True}
        raise HTTPException(status_code=404, detail=f"Alert ID not found: {e}")


# --- Simulator Controls ---
@app.get("/api/simulator/status")
async def get_simulator_status():
    return {
        "is_running": stream_manager.is_running,
        "tick_count": stream_manager.tick_count,
        "current_sim_time": stream_manager.current_sim_time.isoformat(),
        "tick_interval_sec": stream_manager.tick_interval,
        "active_injections": stream_manager.active_injections
    }


@app.post("/api/simulator/start")
async def start_simulator():
    await stream_manager.start()
    return {"status": "STARTED", "is_running": True}


@app.post("/api/simulator/stop")
async def stop_simulator():
    await stream_manager.stop()
    return {"status": "STOPPED", "is_running": False}


@app.post("/api/simulator/tick")
async def manual_simulator_tick():
    """Triggers one manual simulation step across all stations."""
    await stream_manager.tick_step()
    return {
        "status": "STEP_COMPLETE",
        "tick": stream_manager.tick_count,
        "sim_time": stream_manager.current_sim_time.isoformat()
    }


@app.post("/api/simulator/inject")
async def inject_scenario(payload: StreamInjectionPayload):
    res = stream_manager.inject_anomaly(payload)
    return res


# --- Audit Report Export ---
@app.get("/api/report")
async def get_anomaly_report(format: str = Query("json", enum=["json", "markdown"])):
    st_dict = {s.station_id: s for s in DEFAULT_STATIONS}
    health_dict = pipeline.health_engine.get_all_health_summaries()
    
    if format == "markdown":
        md = report_generator.generate_markdown_report(
            stations=st_dict,
            health_summaries=health_dict,
            alerts=pipeline.alerts,
            processed_history=pipeline.processed_history
        )
        return PlainTextResponse(content=md, media_type="text/markdown")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system_info": VERSION_INFO.model_dump(),
        "summary": {
            "total_stations": len(DEFAULT_STATIONS),
            "total_alerts": len(pipeline.alerts),
            "alerts": [a.model_dump() for a in pipeline.alerts[-30:]]
        },
        "station_health": {k: v.model_dump() for k, v in health_dict.items()}
    }


# --- WebSocket Live Stream ---
@app.websocket("/ws/stream")
async def websocket_stream_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        # Send initial network state immediately
        initial_packet = {
            "type": "INIT_STATE",
            "is_running": stream_manager.is_running,
            "tick": stream_manager.tick_count,
            "sim_time": stream_manager.current_sim_time.isoformat(),
            "stations": [s.model_dump() for s in DEFAULT_STATIONS]
        }
        await websocket.send_json(initial_packet)
        while True:
            # Keep socket open and receive any incoming control messages from UI
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                if cmd.get("action") == "TICK":
                    await stream_manager.tick_step()
                elif cmd.get("action") == "START":
                    await stream_manager.start()
                elif cmd.get("action") == "STOP":
                    await stream_manager.stop()
            except Exception:
                pass
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
    except Exception:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


# Static frontend & SPA fallback for standalone offline operation
dist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")
if os.path.exists(dist_path):
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    
    assets_path = os.path.join(dist_path, "assets")
    if os.path.exists(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path == "api" or full_path.startswith("ws/") or full_path == "ws":
            raise HTTPException(status_code=404, detail="API endpoint not found")
        file_path = os.path.join(dist_path, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        index_file = os.path.join(dist_path, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return PlainTextResponse("SkyGuard AI API is operational.")

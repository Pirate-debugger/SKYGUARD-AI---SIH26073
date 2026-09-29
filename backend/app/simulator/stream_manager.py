"""
Live Stream Simulator & Injection Manager for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Controls real-time continuous AWS telemetry streaming:
- Synchronized multi-station tick broadcasting
- Batch same-timestamp pipeline ingestion
- Real-time fault injection on any station (Spike, Freeze, Drift, Comm Gap, Weather Event, etc.)
- Event broadcasting to subscribed WebSocket clients and pipeline orchestrator
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from app.models.schemas import StationMetadata, RawReading, ProcessedReading, AlertRecord, StreamInjectionPayload, SensorHealthStatus
from app.simulator.generator import WeatherDataGenerator, DEFAULT_STATIONS
from app.core.pipeline import SkyGuardPipeline


class StreamSimulatorManager:
    def __init__(self, pipeline: SkyGuardPipeline, stations: List[StationMetadata] = DEFAULT_STATIONS):
        self.pipeline = pipeline
        self.stations = stations
        self.generator = WeatherDataGenerator(stations=stations)
        
        # Register stations in spatial engine
        for st in stations:
            self.pipeline.spatial_engine.register_station(st)
            
        self.is_running: bool = False
        self.tick_interval: float = 2.0  # seconds
        self.current_sim_time = datetime(2026, 9, 29, 10, 0, 0)
        self.tick_count = 0
        self.task: Optional[asyncio.Task] = None
        
        # Active injection overrides: station_id -> StreamInjectionPayload
        self.active_injections: Dict[str, StreamInjectionPayload] = {}
        self.injection_remaining_steps: Dict[str, int] = {}
        
        # Subscribed WebSocket dispatchers
        self.listeners: List[Callable[[Dict[str, Any]], Any]] = []

    def add_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        if callback not in self.listeners:
            self.listeners.append(callback)

    def remove_listener(self, callback: Callable[[Dict[str, Any]], Any]):
        if callback in self.listeners:
            self.listeners.remove(callback)

    async def broadcast(self, payload: Dict[str, Any]):
        for listener in list(self.listeners):
            try:
                res = listener(payload)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass

    def inject_anomaly(self, injection: StreamInjectionPayload) -> Dict[str, Any]:
        """Queues a deterministic anomaly injection for real-time demonstration."""
        station_id = injection.station_id
        
        # If Regional Weather Event, apply to all stations in that station's region
        if injection.anomaly_type == "WEATHER_EVENT":
            target_st = next((s for s in self.stations if s.station_id == station_id), None)
            target_region = target_st.region if target_st else "NCR Zone"
            for st in self.stations:
                if st.region == target_region:
                    self.active_injections[st.station_id] = injection
                    self.injection_remaining_steps[st.station_id] = injection.duration_steps
            return {
                "status": "QUEUED",
                "message": f"Regional Weather Event queued across all stations in {target_region}",
                "duration_steps": injection.duration_steps
            }
            
        self.active_injections[station_id] = injection
        self.injection_remaining_steps[station_id] = injection.duration_steps
        return {
            "status": "QUEUED",
            "station_id": station_id,
            "anomaly_type": injection.anomaly_type,
            "duration_steps": injection.duration_steps
        }

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.task = asyncio.create_task(self._run_loop())

    async def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()
            self.task = None

    async def _run_loop(self):
        while self.is_running:
            try:
                await self.tick_step()
                await asyncio.sleep(self.tick_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[StreamSimulator] Error during tick: {e}")
                await asyncio.sleep(self.tick_interval)

    async def tick_step(self):
        """
        Executes a single simulation step across the station network.
        Processes all stations synchronously via pipeline.process_batch.
        """
        self.tick_count += 1
        self.current_sim_time += timedelta(minutes=5)
        
        step_raw_readings: List[RawReading] = []
        
        for station in self.stations:
            st_id = station.station_id
            forced_scenario = None
            magnitude = None
            
            # Check for active injection
            if st_id in self.active_injections:
                inj = self.active_injections[st_id]
                forced_scenario = inj.anomaly_type
                magnitude = inj.magnitude
                
                # Decrement steps
                self.injection_remaining_steps[st_id] -= 1
                if self.injection_remaining_steps[st_id] <= 0:
                    del self.active_injections[st_id]
                    del self.injection_remaining_steps[st_id]
                    self.generator.station_state[st_id]["frozen_val"] = None
                    self.generator.station_state[st_id]["drift_offset"] = 0.0

            raw_reading, _ = self.generator.generate_reading_with_scenarios(
                station=station,
                dt=self.current_sim_time,
                force_scenario=forced_scenario,
                magnitude=magnitude
            )
            step_raw_readings.append(raw_reading)

        # Batch synchronous evaluation across synchronized spatial snapshot
        batch_results = self.pipeline.process_batch(step_raw_readings)
        
        step_readings = [p.model_dump() for p, _ in batch_results]
        step_alerts = [a.model_dump() for _, a in batch_results if a]

        # Real-time health summaries across all stations
        health_dict = self.pipeline.health_engine.get_all_health_summaries()
        health_summaries = {
            sid: h.model_dump() for sid, h in health_dict.items()
        }

        # Calculate network overview in lockstep with the tick
        healthy = 0
        watch = 0
        degraded = 0
        critical = 0
        offline = 0
        for st in self.stations:
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

        active_anomalies = sum(1 for a in self.pipeline.alerts if not a.acknowledged and a.decision == "SENSOR_ANOMALY")
        weather_events = sum(1 for a in self.pipeline.alerts if a.decision == "WEATHER_EVENT")

        network_overview = {
            "total_stations": len(self.stations),
            "healthy_count": healthy,
            "watch_count": watch,
            "degraded_count": degraded,
            "critical_count": critical,
            "offline_count": offline,
            "active_anomalies_count": active_anomalies,
            "alerts_today_count": len(self.pipeline.alerts),
            "weather_events_count": weather_events,
            "system_status": "OPERATIONAL"
        }

        # Broadcast update to web clients
        packet = {
            "type": "STREAM_TICK",
            "tick": self.tick_count,
            "sim_time": self.current_sim_time.isoformat(),
            "readings": step_readings,
            "alerts": step_alerts,
            "health_summaries": health_summaries,
            "network_overview": network_overview,
            "active_injections": list(self.active_injections.keys())
        }
        await self.broadcast(packet)

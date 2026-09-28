"""
Live Stream Simulator & Injection Manager for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Controls real-time continuous AWS telemetry streaming:
- Start / Stop streaming
- Configurable broadcast rate (default 2 seconds / tick)
- Real-time fault injection on any station (Spike, Freeze, Drift, Comm Gap, Weather Event, etc.)
- Event broadcasting to subscribed WebSocket clients and pipeline orchestrator
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from app.models.schemas import StationMetadata, RawReading, ProcessedReading, AlertRecord, StreamInjectionPayload
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
        self.tick_interval: float = 2.0 # seconds
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
        
        # If Regional Weather Event, apply to all stations in that station's region!
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
        """Simulation tick loop: emits readings for all AWS stations sequentially or concurrently."""
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
        """Executes a single simulation step across the station network."""
        self.tick_count += 1
        self.current_sim_time += timedelta(minutes=5)
        
        step_readings = []
        step_alerts = []
        
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
                    # Reset frozen / drift state in generator
                    self.generator.station_state[st_id]["frozen_val"] = None
                    self.generator.station_state[st_id]["drift_offset"] = 0.0

            raw_reading, _ = self.generator.generate_reading_with_scenarios(
                station=station,
                dt=self.current_sim_time,
                force_scenario=forced_scenario,
                magnitude=magnitude
            )

            processed, alert = self.pipeline.process_reading(raw_reading)
            step_readings.append(processed.model_dump())
            if alert:
                step_alerts.append(alert.model_dump())

        # Broadcast update to web clients
        packet = {
            "type": "STREAM_TICK",
            "tick": self.tick_count,
            "sim_time": self.current_sim_time.isoformat(),
            "readings": step_readings,
            "alerts": step_alerts,
            "active_injections": list(self.active_injections.keys())
        }
        await self.broadcast(packet)

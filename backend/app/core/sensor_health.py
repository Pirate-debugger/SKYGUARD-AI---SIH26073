"""
Sensor Health & Degradation Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Tracks sensor operational degradation over time:
- Anomaly frequency within rolling operational window
- Spike counts, frozen intervals, communication drops, drift trends
- Time-since-last-observation offline / delay detection
- Communication states: ONLINE, WARNING, COMMUNICATION_DELAY, OFFLINE
- Composite Health Score (0 to 100)
- Health States: HEALTHY, WATCH, DEGRADED, CRITICAL, OFFLINE
- Health Trends: IMPROVING, STABLE, DECLINING
- Degradation Signals: LOW, MODERATE, HIGH (with explicit history threshold)
- Maintenance Action Recommendations
"""

from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.config import OFFLINE_CONFIG
from app.models.schemas import (
    SensorHealthStatus,
    SensorHealthSummary,
    CommunicationState,
    MaintenanceRecommendation,
    DegradationLevel,
    DecisionClassification,
    ProbableCause,
    EvidenceStrength
)


class StationHealthTracker:
    def __init__(self, station_id: str, window_size: int = 50):
        self.station_id = station_id
        self.window_size = window_size
        self.recent_events: deque = deque(maxlen=window_size)
        self.last_seen_dt: Optional[datetime] = None
        self.consecutive_comm_failures = 0
        self.total_readings_processed = 0

    def record_reading_event(self, decision: DecisionClassification, probable_cause: ProbableCause, ts: str):
        self.total_readings_processed += 1
        try:
            self.last_seen_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            self.last_seen_dt = datetime.now(timezone.utc)
        
        if decision == DecisionClassification.COMMUNICATION_ERROR:
            self.consecutive_comm_failures += 1
        else:
            self.consecutive_comm_failures = 0
            
        self.recent_events.append({
            "timestamp": ts,
            "decision": decision,
            "probable_cause": probable_cause
        })

    def evaluate_health(self, current_time: Optional[datetime] = None) -> SensorHealthSummary:
        now_dt = current_time or (self.last_seen_dt or datetime.now(timezone.utc))
        now_iso = now_dt.isoformat()
        
        # Calculate time since last observation
        time_since_last_min = 0.0
        missed_intervals = 0
        expected_interval_min = OFFLINE_CONFIG["expected_reporting_interval_min"]
        
        if self.last_seen_dt:
            delta_sec = (now_dt - self.last_seen_dt).total_seconds()
            time_since_last_min = max(0.0, delta_sec / 60.0)
            missed_intervals = int(time_since_last_min // expected_interval_min)

        # Evaluate communication state
        if missed_intervals >= OFFLINE_CONFIG["consecutive_missed_for_offline"] or self.consecutive_comm_failures >= 5 or time_since_last_min >= OFFLINE_CONFIG["offline_delay_min"]:
            comm_state = CommunicationState.OFFLINE
            status = SensorHealthStatus.OFFLINE
            return SensorHealthSummary(
                station_id=self.station_id,
                status=status,
                communication_state=comm_state,
                health_score=0.0,
                degradation_signal=DegradationLevel.HIGH,
                health_trend="DECLINING",
                recent_spikes_count=0,
                recent_frozen_intervals=0,
                recent_comm_gaps=max(self.consecutive_comm_failures, missed_intervals),
                missed_intervals=missed_intervals,
                time_since_last_reading_min=round(time_since_last_min, 1),
                drift_trend_detected=False,
                maintenance_recommendation=MaintenanceRecommendation.INSPECT_COMMUNICATION_LINK,
                summary_text=f"Telemetry lost for {time_since_last_min:.1f} minutes ({missed_intervals} expected cycles missed). Communication link or power failure suspected.",
                last_updated=now_iso
            )
        elif missed_intervals >= 3 or time_since_last_min >= OFFLINE_CONFIG["comm_delay_min"]:
            comm_state = CommunicationState.COMMUNICATION_DELAY
        elif missed_intervals >= 1 or time_since_last_min >= OFFLINE_CONFIG["warning_delay_min"]:
            comm_state = CommunicationState.WARNING
        else:
            comm_state = CommunicationState.ONLINE

        # Count occurrences in recent operational window
        spikes = sum(1 for e in self.recent_events if e["probable_cause"] == ProbableCause.SENSOR_SPIKE)
        freezes = sum(1 for e in self.recent_events if e["probable_cause"] == ProbableCause.SENSOR_FREEZE)
        drifts = sum(1 for e in self.recent_events if e["probable_cause"] == ProbableCause.CALIBRATION_DRIFT)
        comm_errors = sum(1 for e in self.recent_events if e["decision"] == DecisionClassification.COMMUNICATION_ERROR)
        anomalies = sum(1 for e in self.recent_events if e["decision"] == DecisionClassification.SENSOR_ANOMALY)
        
        # Calculate health trend: compare recent 8 events vs earlier window
        events_list = list(self.recent_events)
        if len(events_list) >= 15:
            recent_sub = events_list[-8:]
            earlier_sub = events_list[:-8]
            rec_anom_rate = sum(1 for e in recent_sub if e["decision"] != DecisionClassification.NORMAL) / len(recent_sub)
            ear_anom_rate = sum(1 for e in earlier_sub if e["decision"] != DecisionClassification.NORMAL) / len(earlier_sub)
            if rec_anom_rate > ear_anom_rate + 0.15:
                trend = "DECLINING"
            elif rec_anom_rate < ear_anom_rate - 0.15:
                trend = "IMPROVING"
            else:
                trend = "STABLE"
        else:
            trend = "STABLE"

        # Explainable Health Scoring
        score = 100.0
        score -= min(35.0, spikes * 7.0)
        score -= min(40.0, freezes * 12.0)
        score -= min(30.0, drifts * 10.0)
        score -= min(25.0, comm_errors * 5.0)
        score = max(5.0, min(100.0, score))
        
        # Degradation Level
        if score > 85.0 and drifts == 0 and freezes == 0:
            deg_signal = DegradationLevel.LOW
        elif score > 60.0 or drifts > 0:
            deg_signal = DegradationLevel.MODERATE
        else:
            deg_signal = DegradationLevel.HIGH

        # Maintenance Recommendation & Status
        if score >= 90.0:
            status = SensorHealthStatus.HEALTHY
            rec = MaintenanceRecommendation.NO_ACTION
            if self.total_readings_processed < 6:
                summary = "Establishing baseline; station operating within standard meteorological specifications."
            else:
                summary = "Station operating within standard meteorological specifications."
        elif score >= 75.0:
            status = SensorHealthStatus.WATCH
            rec = MaintenanceRecommendation.CONTINUE_MONITORING
            summary = f"Intermittent minor anomalies observed ({spikes} spikes, {comm_errors} drops). Within acceptable watch tolerances."
        elif score >= 45.0:
            status = SensorHealthStatus.DEGRADED
            if drifts > 0:
                rec = MaintenanceRecommendation.RECALIBRATION_RECOMMENDED
                summary = "Persistent calibration drift detected. Sensor recalibration recommended."
            elif freezes > 0:
                rec = MaintenanceRecommendation.REVIEW_SENSOR
                summary = f"Repeated sensor freeze events ({freezes} occurrences). Hardware aspiration/ADC review advised."
            else:
                rec = MaintenanceRecommendation.REVIEW_SENSOR
                summary = f"Elevated anomaly frequency ({anomalies} events in window). Component inspection advised."
        else:
            status = SensorHealthStatus.CRITICAL
            rec = MaintenanceRecommendation.MAINTENANCE_REQUIRED
            summary = f"Multiple severe fault signatures ({spikes} spikes, {freezes} freezes, {drifts} drift periods). On-site maintenance required."

        return SensorHealthSummary(
            station_id=self.station_id,
            status=status,
            communication_state=comm_state,
            health_score=round(score, 1),
            degradation_signal=deg_signal,
            health_trend=trend,
            recent_spikes_count=spikes,
            recent_frozen_intervals=freezes,
            recent_comm_gaps=comm_errors,
            missed_intervals=missed_intervals,
            time_since_last_reading_min=round(time_since_last_min, 1),
            drift_trend_detected=(drifts > 0),
            maintenance_recommendation=rec,
            summary_text=summary,
            last_updated=now_iso
        )


class SensorHealthEngine:
    def __init__(self):
        self.trackers: Dict[str, StationHealthTracker] = {}

    def get_or_create_tracker(self, station_id: str) -> StationHealthTracker:
        if station_id not in self.trackers:
            self.trackers[station_id] = StationHealthTracker(station_id)
        return self.trackers[station_id]

    def get_health_summary(self, station_id: str, current_time: Optional[datetime] = None) -> SensorHealthSummary:
        tracker = self.get_or_create_tracker(station_id)
        return tracker.evaluate_health(current_time)

    def update_and_get_health(
        self,
        station_id: str,
        decision: DecisionClassification,
        probable_cause: ProbableCause,
        ts: str
    ) -> SensorHealthSummary:
        tracker = self.get_or_create_tracker(station_id)
        tracker.record_reading_event(decision, probable_cause, ts)
        return tracker.evaluate_health()

    def update_from_reading(
        self,
        station_id: str,
        is_spike: bool = False,
        is_frozen: bool = False,
        is_comm_gap: bool = False,
        is_drift: bool = False,
        is_weather_event: bool = False,
        timestamp: Optional[str] = None
    ) -> SensorHealthSummary:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        if is_weather_event:
            decision = DecisionClassification.WEATHER_EVENT
            cause = ProbableCause.REGIONAL_WEATHER_EVENT
        elif is_spike:
            decision = DecisionClassification.SENSOR_ANOMALY
            cause = ProbableCause.SENSOR_SPIKE
        elif is_frozen:
            decision = DecisionClassification.SENSOR_ANOMALY
            cause = ProbableCause.SENSOR_FREEZE
        elif is_drift:
            decision = DecisionClassification.SENSOR_DEGRADATION
            cause = ProbableCause.CALIBRATION_DRIFT
        elif is_comm_gap:
            decision = DecisionClassification.COMMUNICATION_ERROR
            cause = ProbableCause.COMMUNICATION_FAILURE
        else:
            decision = DecisionClassification.NORMAL
            cause = ProbableCause.NORMAL_OPERATION
        return self.update_and_get_health(station_id, decision, cause, ts)

    def get_all_health_summaries(self, current_time: Optional[datetime] = None) -> Dict[str, SensorHealthSummary]:
        return {st_id: tracker.evaluate_health(current_time) for st_id, tracker in self.trackers.items()}

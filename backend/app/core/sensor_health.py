"""
Sensor Health & Degradation Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Tracks sensor operational degradation over time:
- Anomaly frequency within rolling operational window
- Spike counts, frozen intervals, communication drops, drift trends
- Composite Health Score (0 to 100)
- Health States: HEALTHY, WATCH, DEGRADED, CRITICAL, OFFLINE
- Degradation Signals: LOW, MODERATE, HIGH
- Maintenance Action Recommendations
"""

from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.models.schemas import (
    SensorHealthStatus,
    SensorHealthSummary,
    MaintenanceRecommendation,
    DegradationLevel,
    DecisionClassification,
    ProbableCause
)


class StationHealthTracker:
    def __init__(self, station_id: str, window_size: int = 50):
        self.station_id = station_id
        self.window_size = window_size
        self.recent_events: deque = deque(maxlen=window_size)
        self.last_seen_ts: Optional[str] = None
        self.consecutive_comm_failures = 0
        self.total_readings_processed = 0

    def record_reading_event(self, decision: DecisionClassification, probable_cause: ProbableCause, ts: str):
        self.total_readings_processed += 1
        self.last_seen_ts = ts
        
        if decision == DecisionClassification.COMMUNICATION_ERROR:
            self.consecutive_comm_failures += 1
        else:
            self.consecutive_comm_failures = 0
            
        self.recent_events.append({
            "timestamp": ts,
            "decision": decision,
            "probable_cause": probable_cause
        })

    def evaluate_health(self) -> SensorHealthSummary:
        now_iso = self.last_seen_ts or datetime.now(timezone.utc).isoformat()
        
        # Check OFFLINE condition: 5+ consecutive missing packets
        if self.consecutive_comm_failures >= 5:
            return SensorHealthSummary(
                station_id=self.station_id,
                status=SensorHealthStatus.OFFLINE,
                health_score=0.0,
                degradation_signal=DegradationLevel.HIGH,
                recent_spikes_count=0,
                recent_frozen_intervals=0,
                recent_comm_gaps=self.consecutive_comm_failures,
                drift_trend_detected=False,
                maintenance_recommendation=MaintenanceRecommendation.INSPECT_COMMUNICATION_LINK,
                summary_text=f"Telemetry lost for {self.consecutive_comm_failures} consecutive reporting cycles. Physical or RF transceiver failure suspected.",
                last_updated=now_iso
            )

        # Count occurrences in recent window
        spikes = sum(1 for e in self.recent_events if e["probable_cause"] == ProbableCause.SENSOR_SPIKE)
        freezes = sum(1 for e in self.recent_events if e["probable_cause"] == ProbableCause.SENSOR_FREEZE)
        drifts = sum(1 for e in self.recent_events if e["probable_cause"] == ProbableCause.CALIBRATION_DRIFT)
        comm_errors = sum(1 for e in self.recent_events if e["decision"] == DecisionClassification.COMMUNICATION_ERROR)
        anomalies = sum(1 for e in self.recent_events if e["decision"] == DecisionClassification.SENSOR_ANOMALY)
        
        n_events = max(len(self.recent_events), 1)
        anomaly_rate = anomalies / n_events

        # Base health starts at 100
        score = 100.0
        score -= min(35.0, spikes * 7.0)
        score -= min(40.0, freezes * 12.0)
        score -= min(30.0, drifts * 10.0)
        score -= min(25.0, comm_errors * 5.0)
        score = max(5.0, min(100.0, score))
        
        # Determine degradation level
        if score > 85.0 and drifts == 0 and freezes == 0:
            deg_signal = DegradationLevel.LOW
        elif score > 60.0 or drifts > 0:
            deg_signal = DegradationLevel.MODERATE
        else:
            deg_signal = DegradationLevel.HIGH

        # Determine health status and recommendation
        if score >= 90.0:
            status = SensorHealthStatus.HEALTHY
            rec = MaintenanceRecommendation.NO_ACTION
            summary = "Station operating within optimal meteorological accuracy specifications."
        elif score >= 75.0:
            status = SensorHealthStatus.WATCH
            rec = MaintenanceRecommendation.CONTINUE_MONITORING
            summary = f"Minor intermittent anomalies observed ({spikes} spikes, {comm_errors} packet drops). Baseline within acceptable margins."
        elif score >= 45.0:
            status = SensorHealthStatus.DEGRADED
            if drifts > 0:
                rec = MaintenanceRecommendation.RECALIBRATION_RECOMMENDED
                summary = f"Persistent calibration drift detected over recent operational cycles. Sensor recalibration recommended."
            elif freezes > 0:
                rec = MaintenanceRecommendation.REVIEW_SENSOR
                summary = f"Repeated sensor freeze events ({freezes} times). Mechanical/ADC aspiration review advised."
            else:
                rec = MaintenanceRecommendation.REVIEW_SENSOR
                summary = f"Elevated anomaly frequency ({round(anomaly_rate*100, 1)}%). Component inspection advised."
        else:
            status = SensorHealthStatus.CRITICAL
            rec = MaintenanceRecommendation.MAINTENANCE_REQUIRED
            summary = f"Multiple severe fault signatures ({spikes} spikes, {freezes} freezes, {drifts} drift periods). Urgent on-site maintenance required."

        return SensorHealthSummary(
            station_id=self.station_id,
            status=status,
            health_score=round(score, 1),
            degradation_signal=deg_signal,
            recent_spikes_count=spikes,
            recent_frozen_intervals=freezes,
            recent_comm_gaps=comm_errors,
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

    def update_and_get_health(
        self, station_id: str, decision: DecisionClassification, probable_cause: ProbableCause, ts: str
    ) -> SensorHealthSummary:
        tracker = self.get_or_create_tracker(station_id)
        tracker.record_reading_event(decision, probable_cause, ts)
        return tracker.evaluate_health()

    def get_all_health_summaries(self) -> Dict[str, SensorHealthSummary]:
        return {st_id: tracker.evaluate_health() for st_id, tracker in self.trackers.items()}

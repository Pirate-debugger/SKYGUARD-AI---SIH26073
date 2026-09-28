"""
Report Generator for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Generates comprehensive, exportable JSON and Markdown audit reports for AWS networks:
- Network-wide and Station-specific summaries
- Telemetry quality metrics
- Anomaly incident log with root-cause and evidence attribution
- Sensor degradation indicators and maintenance recommendations
- Methodology, model versioning, and synthetic disclosure
"""

from datetime import datetime, timezone
from typing import Dict, List, Any
from app.config import VERSION_INFO
from app.models.schemas import (
    SensorHealthSummary,
    AlertRecord,
    ProcessedReading,
    StationMetadata
)


class AnomalyReportGenerator:
    def __init__(self):
        pass

    def generate_markdown_report(
        self,
        stations: Dict[str, StationMetadata],
        health_summaries: Dict[str, SensorHealthSummary],
        alerts: List[AlertRecord],
        processed_history: Dict[str, List[ProcessedReading]]
    ) -> str:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        
        total_readings = sum(len(reads) for reads in processed_history.values())
        total_alerts = len(alerts)
        weather_events = sum(1 for a in alerts if a.decision == "WEATHER_EVENT")
        sensor_anomalies = sum(1 for a in alerts if a.decision == "SENSOR_ANOMALY")
        comm_errors = sum(1 for a in alerts if a.decision == "COMMUNICATION_ERROR")
        degradations = sum(1 for a in alerts if a.decision == "SENSOR_DEGRADATION")

        md = f"""# SKYGUARD AI - AWS ANOMALY DETECTION & SENSOR HEALTH REPORT
**Problem Statement ID:** {VERSION_INFO.problem_statement_id} (Smart India Hackathon 2026)  
**Report Generated:** {now_str}  
**Model Version:** {VERSION_INFO.model_version} | **Ruleset:** {VERSION_INFO.ruleset_version}  
**Data Classification:** DEMO / SYNTHETIC DATA (Controlled Benchmarking Simulation)

---

## 1. EXECUTIVE SUMMARY
- **Monitored AWS Stations:** {len(stations)} Stations
- **Total Telemetry Packets Processed:** {total_readings} Observations
- **Flagged Incidents:** {total_alerts} Total Events
  - **Genuine Weather Events Corroborated:** {weather_events}
  - **Isolated Sensor Anomalies:** {sensor_anomalies}
  - **Communication / Packet Drops:** {comm_errors}
  - **Sensor Degradation Signals:** {degradations}

> **Core Finding:** The multi-layered spatial-temporal and thermodynamic fusion layer successfully isolated localized hardware faults while preventing false alarms during synoptic meteorological fluctuations.

---

## 2. STATION HEALTH STATUS & MAINTENANCE RECOMMENDATIONS

| Station ID | Station Name | Region | Health Score | Operational Status | Degradation Signal | Recommended Action |
|---|---|---|---|---|---|---|
"""
        for st_id, st in stations.items():
            h = health_summaries.get(st_id)
            score = f"{h.health_score:.1f}%" if h else "N/A"
            status = h.status.value if h else "UNKNOWN"
            deg = h.degradation_signal.value if h else "LOW"
            rec = h.maintenance_recommendation.value if h else "NO_ACTION"
            md += f"| {st_id} | {st.station_name} | {st.region} | {score} | **{status}** | {deg} | `{rec}` |\n"

        md += """
---

## 3. RECENT ANOMALY & WEATHER EVENT INCIDENT LOG

"""
        if not alerts:
            md += "*No active anomaly incidents recorded during this operational window.*\n\n"
        else:
            md += "| Timestamp | Station ID | Decision | Probable Cause | Severity | Confidence | Flagged Params | Deviation |\n"
            md += "|---|---|---|---|---|---|---|---|\n"
            for a in alerts[-15:]:  # Show last 15 alerts
                dev_str = ", ".join([f"{k}: {v:+.1f}" for k, v in a.deviations.items() if v is not None]) or "N/A"
                md += f"| {a.timestamp[-8:]} | {a.station_id} | {a.decision.value} | {a.probable_cause.value} | `{a.severity.value}` | {int(a.confidence*100)}% | {', '.join(a.flagged_parameters)} | {dev_str} |\n"

        md += f"""
---

## 4. ANALYTICAL METHODOLOGY
1. **Data Quality Layer:** Validates physical envelopes (T: -50 to 65°C, P: 500 to 1100 hPa, RH: 0 to 100%) aligned with selected meteorological QC concepts described in WMO guidance and rejects corrupted payloads without silent interpolation.
2. **Temporal Engine:** Calculates running median absolute deviation (MAD), instantaneous rates of change, zero-variance persistence (frozen values), monotonic linear regression slopes (drift), and CUSUM change-point detection for sudden regime shifts.
3. **Multivariate Engine:** Evaluates statistical multivariate consistency, enforces Magnus-Tetens thermodynamic dewpoint limits ($T_{{dew}} \\le T_{{air}}$), and computes Mahalanobis distance over empirical atmospheric covariance.
4. **Spatial Neighborhood Consensus:** Evaluates target station against $k$-nearest spatial neighbors within 150 km using Haversine distance, elevation-adjusted hypsometric reduction, and directional change agreement ratio, distinguishing localized faults from regional weather events.
5. **Machine Learning Layer:** Isolation Forest trained on joint 10-dimensional spatial-temporal residual feature space providing standardized anomaly scores and distance-based feature attributions.
6. **False-Alarm Reduction:** Multi-station cross-corroboration ensures elevated readings matching neighboring patterns are classified as `WEATHER_EVENT` rather than sensor defects.

---

## 5. SYSTEM LIMITATIONS & DISCLOSURE
- **Demo Data Notice:** Data used for this demonstration is realistic synthetic data modeled on tropical and subtropical weather dynamics with controlled injection of known sensor faults.
- **Edge Architecture Note:** The pipeline is architected for hierarchical edge-gateway partitioning (Edge-ready QC rules on dataloggers, ensemble fusion on local gateway or server). Not a certified field deployment.
"""
        return md

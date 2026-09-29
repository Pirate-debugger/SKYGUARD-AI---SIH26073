"""
Re-export SensorHealthEngine and health tracking definitions.
Guarantees compatibility with both `app.core.health_engine` and `app.core.sensor_health`.
"""

from app.core.sensor_health import (
    StationHealthTracker,
    SensorHealthEngine,
    SensorHealthStatus,
    SensorHealthSummary,
    CommunicationState,
    MaintenanceRecommendation,
    DegradationLevel,
    DecisionClassification,
    ProbableCause,
    EvidenceStrength
)

__all__ = [
    "StationHealthTracker",
    "SensorHealthEngine",
    "SensorHealthStatus",
    "SensorHealthSummary",
    "CommunicationState",
    "MaintenanceRecommendation",
    "DegradationLevel",
    "DecisionClassification",
    "ProbableCause",
    "EvidenceStrength"
]

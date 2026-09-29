"""
Pydantic Schemas for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

All schemas enforce transparent, evidence-based meteorological data quality,
spatial-temporal tracking, explainability without unsupported probability claims,
and deterministic sensor health monitoring.
"""

from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class DataQualityStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    MISSING = "MISSING"
    SUSPICIOUS = "SUSPICIOUS"


class DecisionClassification(str, Enum):
    NORMAL = "NORMAL"
    WEATHER_EVENT = "WEATHER_EVENT"
    SENSOR_ANOMALY = "SENSOR_ANOMALY"
    COMMUNICATION_ERROR = "COMMUNICATION_ERROR"
    SENSOR_DEGRADATION = "SENSOR_DEGRADATION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class ProbableCause(str, Enum):
    NORMAL_OPERATION = "NORMAL_OPERATION"
    REGIONAL_WEATHER_EVENT = "REGIONAL_WEATHER_EVENT"
    SENSOR_SPIKE = "SENSOR_SPIKE"
    SENSOR_FREEZE = "SENSOR_FREEZE"
    CALIBRATION_DRIFT = "CALIBRATION_DRIFT"
    COMMUNICATION_FAILURE = "COMMUNICATION_FAILURE"
    DATA_CORRUPTION = "DATA_CORRUPTION"
    MULTIVARIATE_INCONSISTENCY = "MULTIVARIATE_INCONSISTENCY"
    SPATIAL_INCONSISTENCY = "SPATIAL_INCONSISTENCY"
    UNKNOWN_ANOMALY = "UNKNOWN_ANOMALY"


class SensorHealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    OFFLINE = "OFFLINE"


class CommunicationState(str, Enum):
    ONLINE = "ONLINE"
    WARNING = "WARNING"
    COMMUNICATION_DELAY = "COMMUNICATION_DELAY"
    OFFLINE = "OFFLINE"


class EvidenceStrength(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class MaintenanceRecommendation(str, Enum):
    NO_ACTION = "NO_ACTION"
    CONTINUE_MONITORING = "CONTINUE_MONITORING"
    REVIEW_SENSOR = "REVIEW_SENSOR"
    RECALIBRATION_RECOMMENDED = "RECALIBRATION_RECOMMENDED"
    INSPECT_COMMUNICATION_LINK = "INSPECT_COMMUNICATION_LINK"
    MAINTENANCE_REQUIRED = "MAINTENANCE_REQUIRED"


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DegradationLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class StationMetadata(BaseModel):
    station_id: str
    station_name: str
    latitude: float
    longitude: float
    elevation_m: float = 100.0
    station_type: str = "Standard AWS"
    region: str = "North Zone"
    status: SensorHealthStatus = SensorHealthStatus.HEALTHY
    created_at: Optional[str] = None


class RawReading(BaseModel):
    station_id: str
    timestamp: str
    temperature: Optional[float] = None
    pressure: Optional[float] = None
    humidity: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    station_type: Optional[str] = None
    region: Optional[str] = None


class DataQualityResult(BaseModel):
    status: DataQualityStatus
    flagged_parameters: List[str] = []
    issues: List[str] = []
    is_valid: bool = True


class TemporalEvidence(BaseModel):
    spike_detected: bool = False
    drop_detected: bool = False
    freeze_detected: bool = False
    drift_detected: bool = False
    change_point_detected: bool = False
    change_point_param: Optional[str] = None
    change_point_direction: Optional[str] = None
    change_point_magnitude: Optional[float] = None
    rates_of_change: Dict[str, float] = {}  # parameter -> value/min
    rolling_means: Dict[str, float] = {}
    rolling_stds: Dict[str, float] = {}
    robust_z_scores: Dict[str, float] = {}
    frozen_duration_steps: Dict[str, int] = {}
    trend_slopes: Dict[str, float] = {}
    explanation: str = ""


class MultivariateEvidence(BaseModel):
    is_consistent: bool = True
    consistency_score: float = 1.0  # 1.0 = highly consistent, 0.0 = physically discordant
    mahalanobis_distance: float = 0.0
    discordant_parameters: List[str] = []
    explanation: str = ""


class SpatialEvidence(BaseModel):
    is_consistent: bool = True
    neighbor_count: int = 0
    valid_neighbor_count: int = 0
    neighbor_station_ids: List[str] = []
    stale_neighbor_ids: List[str] = []
    neighbor_medians: Dict[str, float] = {}
    neighbor_mads: Dict[str, float] = {}
    relative_deviations: Dict[str, float] = {}
    agreement_ratio: float = 0.0
    corroborating_stations_count: int = 0
    directional_agreement: bool = False
    regional_event_detected: bool = False
    explanation: str = ""


class MLEvidence(BaseModel):
    is_anomaly: bool = False
    raw_decision_score: float = 0.0  # Raw scikit-learn decision_function output (positive = inlier, negative = outlier)
    normalized_anomaly_score: float = 0.0  # Calibrated anomaly index [0.0..1.0] (0 = normal, 1 = extreme anomaly)
    anomaly_score: float = 0.0  # Alias to normalized_anomaly_score for consistent API compatibility
    confidence: float = 0.0
    feature_contributions: Dict[str, float] = {}  # Standardized feature contribution (distance-based attribution)
    model_name: str = "IsolationForest-v2.0.0"


class ImputedValue(BaseModel):
    parameter: str
    original_value: Optional[float]
    estimated_value: float
    method: str = "Spatial Inverse Distance Weighting + Temporal Persistence"
    confidence: float
    is_imputed: bool = True


class ProcessedReading(BaseModel):
    reading_id: Optional[str] = None
    station_id: str
    timestamp: str
    temperature: Optional[float] = None
    pressure: Optional[float] = None
    humidity: Optional[float] = None
    
    # Layered Analysis Outputs
    data_quality: DataQualityResult
    temporal_evidence: TemporalEvidence
    multivariate_evidence: MultivariateEvidence
    spatial_evidence: SpatialEvidence
    ml_evidence: MLEvidence
    
    # Synthesis & Fused Decision
    decision: DecisionClassification
    probable_cause: ProbableCause
    severity: SeverityLevel
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_strength: EvidenceStrength = EvidenceStrength.MEDIUM
    explanation: str
    
    # Imputation (optional corrected values)
    imputed_values: Dict[str, ImputedValue] = {}
    
    # Traceability
    model_version: str
    ruleset_version: str
    feature_version: str


class AlertRecord(BaseModel):
    alert_id: str
    station_id: str
    timestamp: str
    decision: DecisionClassification
    probable_cause: ProbableCause
    severity: SeverityLevel
    confidence: float
    evidence_strength: EvidenceStrength = EvidenceStrength.MEDIUM
    flagged_parameters: List[str]
    observed_values: Dict[str, Optional[float]]
    expected_values: Dict[str, Optional[float]]
    deviations: Dict[str, Optional[float]]
    explanation: str
    recommended_action: MaintenanceRecommendation
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None


class SensorHealthSummary(BaseModel):
    station_id: str
    status: SensorHealthStatus
    communication_state: CommunicationState = CommunicationState.ONLINE
    health_score: float = Field(ge=0.0, le=100.0)  # 100 = perfect, 0 = failing/offline
    degradation_signal: DegradationLevel
    health_trend: str = "STABLE"  # "IMPROVING", "STABLE", "DECLINING"
    recent_spikes_count: int = 0
    recent_frozen_intervals: int = 0
    recent_comm_gaps: int = 0
    missed_intervals: int = 0
    time_since_last_reading_min: float = 0.0
    drift_trend_detected: bool = False
    maintenance_recommendation: MaintenanceRecommendation
    summary_text: str
    last_updated: str


class NetworkOverview(BaseModel):
    total_stations: int
    healthy_count: int
    watch_count: int
    degraded_count: int
    critical_count: int
    offline_count: int
    active_anomalies_count: int
    alerts_today_count: int
    weather_events_count: int
    system_status: str = "OPERATIONAL"


class StreamInjectionPayload(BaseModel):
    station_id: str
    anomaly_type: str  # "SPIKE", "FREEZE", "DRIFT", "COMM_GAP", "WEATHER_EVENT", "SPATIAL_OUTLIER", "MULTIVARIATE_DISCORD"
    target_parameter: Optional[str] = "temperature"
    duration_steps: int = 5
    magnitude: Optional[float] = None


class CsvRowError(BaseModel):
    row_number: int
    column: Optional[str] = None
    error_type: str
    message: str


class CsvIngestResult(BaseModel):
    status: str
    records_received: int
    records_processed: int
    records_failed: int
    errors: List[CsvRowError] = []
    sample_processed: List[Dict[str, Any]] = []

/**
 * SkyGuard AI Frontend TypeScript Types
 * SIH26073: Automatic Weather Station Anomaly Detection System
 */

export type DataQualityStatus = 'VALID' | 'INVALID' | 'MISSING' | 'SUSPICIOUS';

export type DecisionClassification = 
  | 'NORMAL'
  | 'WEATHER_EVENT'
  | 'SENSOR_ANOMALY'
  | 'COMMUNICATION_ERROR'
  | 'SENSOR_DEGRADATION'
  | 'INSUFFICIENT_EVIDENCE';

export type ProbableCause = 
  | 'NORMAL_OPERATION'
  | 'REGIONAL_WEATHER_EVENT'
  | 'SENSOR_SPIKE'
  | 'SENSOR_FREEZE'
  | 'CALIBRATION_DRIFT'
  | 'COMMUNICATION_FAILURE'
  | 'DATA_CORRUPTION'
  | 'MULTIVARIATE_INCONSISTENCY'
  | 'SPATIAL_INCONSISTENCY'
  | 'UNKNOWN_ANOMALY';

export type SensorHealthStatus = 'HEALTHY' | 'WATCH' | 'DEGRADED' | 'CRITICAL' | 'OFFLINE';

export type MaintenanceRecommendation = 
  | 'NO_ACTION'
  | 'CONTINUE_MONITORING'
  | 'REVIEW_SENSOR'
  | 'RECALIBRATION_RECOMMENDED'
  | 'INSPECT_COMMUNICATION_LINK'
  | 'MAINTENANCE_REQUIRED';

export type SeverityLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type DegradationLevel = 'LOW' | 'MODERATE' | 'HIGH';

export interface StationMetadata {
  station_id: string;
  station_name: string;
  latitude: float;
  longitude: float;
  elevation_m: number;
  station_type: string;
  region: string;
  status: SensorHealthStatus;
  created_at?: string;
}

export type float = number;

export interface SensorHealthSummary {
  station_id: string;
  status: SensorHealthStatus;
  communication_state?: string;
  health_score: number;
  degradation_signal: DegradationLevel;
  recent_spikes_count: number;
  recent_frozen_intervals: number;
  recent_comm_gaps: number;
  missed_intervals?: number;
  time_since_last_reading_min?: number;
  drift_trend_detected: boolean;
  maintenance_recommendation: MaintenanceRecommendation;
  summary_text: string;
  last_updated: string;
}

export interface ImputedValue {
  parameter: string;
  original_value: number | null;
  estimated_value: number;
  method: string;
  confidence: number;
  is_imputed: boolean;
}

export interface ProcessedReading {
  reading_id?: string;
  station_id: string;
  timestamp: string;
  temperature: number | null;
  pressure: number | null;
  humidity: number | null;
  
  data_quality: {
    status: DataQualityStatus;
    flagged_parameters: string[];
    issues: string[];
    is_valid: boolean;
  };
  temporal_evidence: {
    spike_detected: boolean;
    drop_detected: boolean;
    freeze_detected: boolean;
    drift_detected: boolean;
    change_point_detected: boolean;
    rates_of_change: Record<string, number>;
    rolling_means: Record<string, number>;
    rolling_stds: Record<string, number>;
    robust_z_scores: Record<string, number>;
    frozen_duration_steps: Record<string, number>;
    trend_slopes: Record<string, number>;
    explanation: string;
  };
  multivariate_evidence: {
    is_consistent: boolean;
    consistency_score: number;
    mahalanobis_distance: number;
    discordant_parameters: string[];
    explanation: string;
  };
  spatial_evidence: {
    is_consistent: boolean;
    neighbor_count: number;
    valid_neighbor_count?: number;
    corroborating_stations_count?: number;
    agreement_ratio?: number;
    directional_agreement?: boolean;
    neighbor_station_ids: string[];
    stale_neighbor_ids?: string[];
    neighbor_medians: Record<string, number>;
    neighbor_mads: Record<string, number>;
    relative_deviations: Record<string, number>;
    regional_event_detected: boolean;
    explanation: string;
  };
  ml_evidence: {
    is_anomaly: boolean;
    anomaly_score: number;
    confidence: number;
    feature_contributions: Record<string, number>;
    model_name: string;
  };
  
  decision: DecisionClassification;
  probable_cause: ProbableCause;
  severity: SeverityLevel;
  confidence: number;
  explanation: string;
  imputed_values: Record<string, ImputedValue>;
  model_version: string;
  ruleset_version: string;
  feature_version: string;
}

export interface AlertRecord {
  alert_id: string;
  station_id: string;
  timestamp: string;
  decision: DecisionClassification;
  probable_cause: ProbableCause;
  severity: SeverityLevel;
  confidence: number;
  flagged_parameters: string[];
  observed_values: Record<string, number | null>;
  expected_values: Record<string, number | null>;
  deviations: Record<string, number | null>;
  explanation: string;
  recommended_action: MaintenanceRecommendation;
  acknowledged: boolean;
  acknowledged_by?: string;
  acknowledged_at?: string;
}

export interface NetworkOverview {
  total_stations: number;
  healthy_count: number;
  watch_count: number;
  degraded_count: number;
  critical_count: number;
  offline_count: number;
  active_anomalies_count: number;
  alerts_today_count: number;
  weather_events_count: number;
  system_status: string;
}

export interface StationData {
  metadata: StationMetadata;
  health: SensorHealthSummary | null;
  latest_reading: ProcessedReading | null;
}

export interface SpatialNeighbor {
  station_id: string;
  distance_km: number;
}

export interface SpatialTopologyStation {
  station_id: string;
  station_name: string;
  latitude: number;
  longitude: number;
  elevation_m: number;
  region: string;
  station_type: string;
  radius_km: number;
  neighbor_count: number;
  neighbors_within_radius: number;
  k_neighbors_count: number;
  neighbors: SpatialNeighbor[];
  nearest_neighbors: SpatialNeighbor[];
  has_neighbors: boolean;
  spatial_status: 'NORMAL' | 'LOW_EVIDENCE' | 'NO_NEIGHBORS';
  is_corroborating_event: boolean;
  health_status: SensorHealthStatus;
  communication_state: string;
  health_score: number;
  latest_decision: DecisionClassification | null;
  latest_reading?: {
    temperature: number | null;
    pressure: number | null;
    humidity: number | null;
    timestamp: string;
  } | null;
  spatial_evidence?: {
    is_consistent: boolean;
    neighbor_count: number;
    valid_neighbor_count: number;
    corroborating_stations_count: number;
    agreement_ratio: number;
    directional_agreement: boolean;
    regional_event_detected: boolean;
    explanation: string;
  } | null;
}

export interface SpatialTopologyEdge {
  source: string;
  target: string;
  distance_km: number;
  is_corroborating: boolean;
}

export interface SpatialTopologyResponse {
  radius_km: number;
  k_nearest_neighbors: number;
  total_stations: number;
  stations: SpatialTopologyStation[];
  edges: SpatialTopologyEdge[];
}

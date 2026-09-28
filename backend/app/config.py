"""
SkyGuard AI - Configuration and Version Tracking
SIH26073: AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations

Note: Meteorological quality-control thresholds are aligned with selected quality-control
concepts described in WMO guidance documents (e.g. WMO-No. 8, CIMO Guide).
This prototype is an engineering research implementation for SIH26073.
"""

import os
from pydantic import BaseModel


class SystemVersionInfo(BaseModel):
    system_name: str = "SkyGuard AI"
    problem_statement_id: str = "SIH26073"
    model_version: str = "v2.0.0-isoforest-residual"
    feature_version: str = "v2.0.0-synchronized-spatial-temporal"
    ruleset_version: str = "v2.0.0-qc-corroborated"
    dataset_version: str = "v2.0.0-synthetic-sih-multiclass"


VERSION_INFO = SystemVersionInfo()

# Physical Plausibility Limits (aligned with selected meteorological QC concepts)
PHYSICAL_LIMITS = {
    "temperature": {"min": -50.0, "max": 65.0, "unit": "°C"},
    "pressure": {"min": 500.0, "max": 1100.0, "unit": "hPa"},
    "humidity": {"min": 0.0, "max": 100.0, "unit": "%"}
}

# Maximum physically plausible rates of change per minute under extreme meteorological conditions
MAX_RATE_OF_CHANGE_PER_MIN = {
    "temperature": 2.5,   # °C/min (e.g. violent cold front / heatburst max ~2.5°C/min)
    "pressure": 3.0,      # hPa/min (e.g. tornado/violent squall)
    "humidity": 15.0      # %/min (e.g. sudden cloudburst / frontal passage)
}

# Multi-timescale Temporal Analysis Configuration
TEMPORAL_CONFIG = {
    "window_size": 24,              # Short-term buffer size (timesteps)
    "min_window_for_stats": 5,      # Minimum readings needed for rolling z-score / robust MAD
    "spike_z_threshold": 3.5,       # Robust Z-score (MAD-based) threshold for spikes
    "freeze_min_consecutive": 4,    # Number of consecutive identical readings to flag frozen sensor
    "drift_min_steps": 6,           # Minimum steps required to evaluate drift trend
    "drift_slope_threshold": 0.011, # Normalized trend slope indicating calibration drift (>0.33°C/step)
}

# CUSUM Change-Point Detector Configuration
CUSUM_CONFIG = {
    "drift_allowance_k": 0.5,       # Allowance parameter (slack)
    "decision_threshold_h": 4.5,    # Decision boundary in normalized units
    "min_history_steps": 6
}

# Spatial Consistency Configuration
SPATIAL_CONFIG = {
    "k_nearest_neighbors": 4,       # Number of neighboring stations to compare with
    "max_distance_km": 150.0,       # Max radius for spatial neighborhood
    "spatial_mad_threshold": 2.8,   # Deviation multiplier relative to neighborhood MAD
    "regional_event_ratio": 0.65,   # Fraction of valid neighbors needing directional corroboration
    "min_valid_neighbors": 2,       # Minimum neighbors required for spatial consensus
    "min_event_change": {
        "temperature": 3.0,         # Minimum °C change to consider a rapid weather event
        "pressure": 2.0,            # Minimum hPa change to consider a rapid weather event
        "humidity": 12.0            # Minimum % change to consider a rapid weather event
    },
    "event_persistence_window": 8   # Timesteps to maintain regional event status while corroborated
}

# Offline and Communication State Configuration
OFFLINE_CONFIG = {
    "expected_reporting_interval_min": 5.0, # Normal reporting frequency (minutes)
    "warning_delay_min": 12.0,              # Threshold for WARNING communication status
    "comm_delay_min": 25.0,                 # Threshold for COMMUNICATION_DELAY
    "offline_delay_min": 45.0,              # Threshold for OFFLINE state
    "consecutive_missed_for_offline": 5     # Missed intervals before declaring OFFLINE
}

# Database and Stream settings
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skyguard.db")
DEFAULT_STREAM_INTERVAL_SEC = 2.0

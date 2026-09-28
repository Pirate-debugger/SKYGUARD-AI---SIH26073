"""
SkyGuard AI - Configuration and Version Tracking
SIH26073: AI/ML-Based Intelligent Anomaly Detection for Automatic Weather Stations
"""

import os
from pydantic import BaseModel

class SystemVersionInfo(BaseModel):
    system_name: str = "SkyGuard AI"
    problem_statement_id: str = "SIH26073"
    model_version: str = "v1.4.0-isoforest-hybrid"
    feature_version: str = "v1.2.0-spatial-temporal-mv"
    ruleset_version: str = "v2.1.0-wmo-corroborated"
    dataset_version: str = "v1.0.0-synthetic-sih-benchmark"

VERSION_INFO = SystemVersionInfo()

# Meteorological Physical Limits (WMO standard acceptable envelope for ground AWS)
# Any reading outside these is physically impossible (sensor failure/corruption)
PHYSICAL_LIMITS = {
    "temperature": {"min": -50.0, "max": 65.0, "unit": "°C"},
    "pressure": {"min": 500.0, "max": 1100.0, "unit": "hPa"},
    "humidity": {"min": 0.0, "max": 100.0, "unit": "%"}
}

# Maximum physically plausible rates of change per minute under extreme meteorological conditions
# Anything beyond this without multi-station corroboration is highly likely an instrumentation spike
MAX_RATE_OF_CHANGE_PER_MIN = {
    "temperature": 2.5,   # °C/min (e.g. violent cold front / heatburst max ~2.5°C/min)
    "pressure": 3.0,      # hPa/min (e.g. tornado/violent squall)
    "humidity": 15.0      # %/min (e.g. sudden cloudburst / frontal passage)
}

# Temporal analysis parameters
TEMPORAL_CONFIG = {
    "window_size": 24,           # Number of historical timesteps to maintain in memory buffer
    "min_window_for_stats": 5,   # Minimum readings needed for rolling z-score / robust MAD
    "spike_z_threshold": 3.5,    # Robust Z-score (MAD-based) threshold for spikes
    "freeze_min_consecutive": 4, # Number of consecutive identical readings to flag frozen sensor
    "drift_slope_threshold": 0.011, # Normalized trend slope indicating calibration drift (>0.33°C/step)
}

# Spatial consistency parameters
SPATIAL_CONFIG = {
    "k_nearest_neighbors": 4,     # Number of neighboring stations to compare with
    "max_distance_km": 150.0,     # Max radius for spatial neighborhood
    "spatial_mad_threshold": 2.8, # Deviation multiplier relative to neighborhood MAD
    "regional_event_ratio": 0.65  # Fraction of neighbors needing similar shift for Regional Weather Event
}

# Database and Stream settings
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "skyguard.db")
DEFAULT_STREAM_INTERVAL_SEC = 2.0

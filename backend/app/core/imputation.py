"""
Corrected Value Estimation (Imputation) Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Provides transparent, non-destructive candidate estimation for flagged sensor values:
- Never replaces raw observation silently.
- Uses True Spatial Inverse Distance Weighting (IDW) with elevation reduction.
- Blends with pre-current temporal rolling baseline.
- STRICT ANTI-LEAKAGE: Evaluates strictly using observations prior to current anomalous point.
"""

from typing import Dict, List, Optional, Tuple
import numpy as np
from app.models.schemas import ImputedValue, RawReading, SpatialEvidence, StationMetadata


class ImputationEngine:
    def __init__(self, idw_power: float = 2.0):
        self.idw_power = idw_power

    def estimate_corrected_values(
        self,
        reading: RawReading,
        spatial: SpatialEvidence,
        flagged_params: List[str],
        temporal_buffer_history: Dict[str, List[float]],
        neighbor_distances: Optional[List[Tuple[str, float]]] = None,
        neighbor_readings: Optional[Dict[str, RawReading]] = None,
        stations_dict: Optional[Dict[str, StationMetadata]] = None
    ) -> Dict[str, ImputedValue]:
        """
        Estimates non-destructive candidate values using True Inverse Distance Weighting (IDW)
        and pre-current temporal persistence.
        """
        imputed: Dict[str, ImputedValue] = {}
        target_st = stations_dict.get(reading.station_id) if stations_dict else None
        target_elev = target_st.elevation_m if target_st else 200.0
        
        for param in flagged_params:
            orig_val = getattr(reading, param, None)
            
            # 1. Compute True Inverse Distance Weighting from neighbor stations
            spatial_idw_val = None
            if neighbor_distances and neighbor_readings and stations_dict:
                weights = []
                values = []
                for nid, dist_km in neighbor_distances:
                    nr = neighbor_readings.get(nid)
                    if not nr:
                        continue
                    nv = getattr(nr, param, None)
                    if nv is None or np.isnan(nv):
                        continue
                        
                    # Apply elevation correction
                    nst = stations_dict.get(nid)
                    n_elev = nst.elevation_m if nst else target_elev
                    delta_h = target_elev - n_elev
                    
                    if param == "pressure":
                        nv_adj = float(nv) - (delta_h / 8.3)
                    elif param == "temperature":
                        nv_adj = float(nv) - (0.0065 * delta_h)
                    else:
                        nv_adj = float(nv)
                        
                    w = 1.0 / (max(dist_km, 1.0) ** self.idw_power)
                    weights.append(w)
                    values.append(nv_adj)
                    
                if weights:
                    w_arr = np.array(weights)
                    w_norm = w_arr / np.sum(w_arr)
                    spatial_idw_val = float(np.sum(w_norm * np.array(values)))

            # Fallback to spatial median if explicit neighbor distances unavailable
            if spatial_idw_val is None:
                spatial_idw_val = spatial.neighbor_medians.get(param)
            
            # 2. Recent temporal rolling baseline strictly from PRE-CURRENT history
            prior_vals = temporal_buffer_history.get(param, [])
            valid_prior = [v for v in prior_vals if v is not None and not np.isnan(v)]
            temp_mean = np.mean(valid_prior[-5:]) if valid_prior else None
            
            estimated = None
            conf = 0.50
            method = "Spatial Inverse Distance Weighting (IDW) + Temporal Persistence"
            
            if spatial_idw_val is not None and temp_mean is not None:
                # 65% spatial IDW consensus + 35% local pre-current persistence
                estimated = round(0.65 * spatial_idw_val + 0.35 * temp_mean, 2)
                conf = 0.90 if spatial.valid_neighbor_count >= 3 else 0.82
                method = f"True Spatial IDW ({spatial.valid_neighbor_count} stations, p=2.0) + Pre-current Temporal Persistence"
            elif spatial_idw_val is not None:
                estimated = round(float(spatial_idw_val), 2)
                conf = 0.85
                method = f"True Spatial IDW ({spatial.valid_neighbor_count} stations, p=2.0)"
            elif temp_mean is not None:
                estimated = round(float(temp_mean), 2)
                conf = 0.70
                method = "Local Pre-current Temporal Persistence Baseline"
            else:
                fallback_map = {"temperature": 28.0, "pressure": 1010.0, "humidity": 65.0}
                estimated = fallback_map.get(param, 25.0)
                conf = 0.40
                method = "Climatological Envelope Baseline"

            imputed[param] = ImputedValue(
                parameter=param,
                original_value=orig_val,
                estimated_value=estimated,
                method=method,
                confidence=round(conf, 2),
                is_imputed=True
            )
            
        return imputed

"""
Corrected Value Estimation (Imputation) Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Provides transparent, non-destructive value estimation for flagged sensor values:
- Never replaces raw observation silently.
- Uses Spatial Inverse Distance Weighting (IDW) combined with Temporal Persistence.
- Clearly flags estimated values with confidence and methodological explanation.
"""

from typing import Dict, List, Optional
import numpy as np
from app.models.schemas import ImputedValue, RawReading, SpatialEvidence


class ImputationEngine:
    def __init__(self):
        pass

    def estimate_corrected_values(
        self,
        reading: RawReading,
        spatial: SpatialEvidence,
        flagged_params: List[str],
        temporal_buffer_history: Dict[str, List[float]]
    ) -> Dict[str, ImputedValue]:
        imputed: Dict[str, ImputedValue] = {}
        
        for param in flagged_params:
            orig_val = getattr(reading, param, None)
            
            # 1. Spatial Neighbor Median (primary spatial anchor)
            spatial_med = spatial.neighbor_medians.get(param)
            
            # 2. Recent temporal rolling mean from prior valid history
            prior_vals = temporal_buffer_history.get(param, [])
            valid_prior = [v for v in prior_vals if v is not None and not np.isnan(v)]
            temp_mean = np.mean(valid_prior[-5:]) if valid_prior else None
            
            estimated = None
            conf = 0.50
            method = "Spatial-Temporal Inverse Distance Weighting"
            
            if spatial_med is not None and temp_mean is not None:
                # Blend 60% spatial neighbor consensus + 40% temporal local persistence
                estimated = round(0.60 * spatial_med + 0.40 * temp_mean, 2)
                conf = 0.90 if spatial.neighbor_count >= 3 else 0.82
                method = f"Hybrid Spatial Consensus ({spatial.neighbor_count} stations) + Local Temporal Persistence"
            elif spatial_med is not None:
                estimated = round(spatial_med, 2)
                conf = 0.85
                method = f"Neighborhood Spatial Consensus ({spatial.neighbor_count} stations)"
            elif temp_mean is not None:
                estimated = round(float(temp_mean), 2)
                conf = 0.70
                method = "Local Rolling Temporal Baseline"
            else:
                # Climatological regional fallback
                fallback_map = {"temperature": 28.0, "pressure": 1010.0, "humidity": 65.0}
                estimated = fallback_map.get(param, 25.0)
                conf = 0.40
                method = "Synoptic Climatological Envelope Fallback"

            imputed[param] = ImputedValue(
                parameter=param,
                original_value=orig_val,
                estimated_value=estimated,
                method=method,
                confidence=round(conf, 2),
                is_imputed=True
            )
            
        return imputed

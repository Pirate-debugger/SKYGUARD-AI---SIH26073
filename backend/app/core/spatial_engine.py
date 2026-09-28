"""
Spatial Consistency Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Compares observations across neighboring stations using geospatial distances:
- Haversine great-circle distance
- Neighborhood median and Median Absolute Deviation (MAD)
- Relative deviations per parameter
- Regional coherent event detection vs isolated station outlier
"""

import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from app.config import SPATIAL_CONFIG
from app.models.schemas import RawReading, SpatialEvidence, StationMetadata


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points on Earth in kilometers."""
    R = 6371.0 # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class SpatialConsistencyEngine:
    def __init__(self):
        # station_id -> StationMetadata
        self.stations: Dict[str, StationMetadata] = {}
        # station_id -> latest RawReading
        self.latest_readings: Dict[str, RawReading] = {}

    def register_station(self, station: StationMetadata):
        self.stations[station.station_id] = station

    def update_latest_reading(self, reading: RawReading):
        self.latest_readings[reading.station_id] = reading

    def find_nearest_neighbors(
        self, target_station_id: str, k: int = SPATIAL_CONFIG["k_nearest_neighbors"]
    ) -> List[Tuple[str, float]]:
        """Finds k nearest neighboring stations with their distances in km."""
        if target_station_id not in self.stations:
            return []
        
        target = self.stations[target_station_id]
        distances: List[Tuple[str, float]] = []
        
        for st_id, st in self.stations.items():
            if st_id == target_station_id:
                continue
            dist = haversine_km(target.latitude, target.longitude, st.latitude, st.longitude)
            if dist <= SPATIAL_CONFIG["max_distance_km"]:
                distances.append((st_id, dist))
                
        distances.sort(key=lambda x: x[1])
        return distances[:k]

    def analyze(self, reading: RawReading) -> SpatialEvidence:
        target_id = reading.station_id
        if target_id not in self.stations:
            return SpatialEvidence(
                is_consistent=True,
                neighbor_count=0,
                neighbor_station_ids=[],
                neighbor_medians={},
                neighbor_mads={},
                relative_deviations={},
                regional_event_detected=False,
                explanation="Station coordinates not registered; spatial verification skipped"
            )

        neighbors = self.find_nearest_neighbors(target_id)
        if not neighbors:
            return SpatialEvidence(
                is_consistent=True,
                neighbor_count=0,
                neighbor_station_ids=[],
                neighbor_medians={},
                neighbor_mads={},
                relative_deviations={},
                regional_event_detected=False,
                explanation="No neighboring stations found within spatial envelope (<150km)"
            )

        neighbor_ids = [nid for nid, _ in neighbors]
        
        medians: Dict[str, float] = {}
        mads: Dict[str, float] = {}
        rel_deviations: Dict[str, float] = {}
        
        is_consistent = True
        regional_event_detected = False
        reasons: List[str] = []
        
        params = ["temperature", "pressure", "humidity"]
        
        for param in params:
            target_val = getattr(reading, param, None)
            if target_val is None or np.isnan(target_val):
                continue
                
            target_st = self.stations.get(target_id)
            target_elev = target_st.elevation_m if target_st else 200.0
            
            neighbor_vals = []
            for nid in neighbor_ids:
                nr = self.latest_readings.get(nid)
                if nr:
                    nv = getattr(nr, param, None)
                    if nv is not None and not np.isnan(nv):
                        nst = self.stations.get(nid)
                        n_elev = nst.elevation_m if nst else target_elev
                        delta_h = target_elev - n_elev
                        
                        # Apply standard WMO barometric & hypsometric elevation adjustments
                        if param == "pressure":
                            # 1 hPa per 8.3 meters
                            nv_norm = float(nv) - (delta_h / 8.3)
                        elif param == "temperature":
                            # Environmental lapse rate: -6.5°C per 1000m
                            nv_norm = float(nv) - (0.0065 * delta_h)
                        else:
                            nv_norm = float(nv)
                            
                        neighbor_vals.append(nv_norm)
                        
            if len(neighbor_vals) >= 2:
                n_arr = np.array(neighbor_vals)
                n_med = float(np.median(n_arr))
                n_mad = float(np.median(np.abs(n_arr - n_med)))
                
                medians[param] = round(n_med, 2)
                mads[param] = round(n_mad, 2)
                
                # Deviation from neighbor median
                diff = target_val - n_med
                rel_deviations[param] = round(diff, 2)
                
                # Check spatial anomaly: target deviates by more than spatial threshold * MAD
                # (Minimum floor on MAD to prevent oversensitivity in very uniform conditions)
                floor_mad = 1.2 if param == "temperature" else (1.5 if param == "pressure" else 4.0)
                effective_mad = max(n_mad * 1.4826, floor_mad)
                
                spatial_z = abs(diff) / effective_mad
                
                if spatial_z >= SPATIAL_CONFIG["spatial_mad_threshold"]:
                    # Station significantly disagrees with its spatial neighbors!
                    is_consistent = False
                    reasons.append(
                        f"Isolated spatial deviation in {param}: Obs={target_val:.1f} vs Neighbors Median={n_med:.1f} "
                        f"(Delta={diff:+.1f}, MAD={n_mad:.1f}, {len(neighbor_vals)} neighbors reporting)"
                    )
                else:
                    # Check if neighbors themselves also show a coherent shift from seasonal baseline
                    # indicating a Regional Weather Event (severe heatwave >43°C or severe squall <985 hPa)
                    if param == "temperature" and target_val > 43.0 and n_med > 42.0 and abs(diff) < 2.0:
                        regional_event_detected = True
                    elif param == "pressure" and target_val < 985.0 and n_med < 988.0 and abs(diff) < 2.5:
                        regional_event_detected = True # Regional cyclone / squall

        # Update latest reading for this station
        self.latest_readings[target_id] = reading
        
        if regional_event_detected and not is_consistent:
            # If neighboring stations agree on a major trend, it's a regional weather event rather than isolated sensor fault
            is_consistent = True

        explanation = "; ".join(reasons) if reasons else (
            f"Consistent with {len(neighbor_ids)} neighboring AWS stations within radius"
        )
        if regional_event_detected:
            explanation += " [Regional meteorological event signature corroborated by neighborhood]"

        return SpatialEvidence(
            is_consistent=is_consistent,
            neighbor_count=len(neighbor_ids),
            neighbor_station_ids=neighbor_ids,
            neighbor_medians=medians,
            neighbor_mads=mads,
            relative_deviations=rel_deviations,
            regional_event_detected=regional_event_detected,
            explanation=explanation
        )

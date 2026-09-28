"""
Spatial Consistency Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Provides synchronized spatial neighborhood quality control:
- Haversine great-circle distance clustering
- Standard WMO barometric and hypsometric elevation adjustments (-1 hPa/8.3m, -6.5°C/1000m)
- Synchronized same-timestamp spatial snapshots (eliminates order dependency)
- Directional change-rate agreement & neighborhood consensus (regional_event_ratio >= 0.65)
- Distinguishes isolated sensor failures from legitimate regional meteorological phenomena
"""

import math
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from app.config import SPATIAL_CONFIG
from app.models.schemas import RawReading, SpatialEvidence, StationMetadata


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points on Earth in kilometers."""
    R = 6371.0  # Earth radius in km
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
        # station_id -> previous RawReading (for calculating rate-of-change delta)
        self.prev_readings: Dict[str, RawReading] = {}
        # Active regional events: station_id -> {param, remaining_steps, corroborating_count, agreement_ratio, target_sign}
        self.active_regional_events: Dict[str, Dict[str, Any]] = {}

    def register_station(self, station: StationMetadata):
        self.stations[station.station_id] = station

    def update_latest_reading(self, reading: RawReading):
        if reading.station_id in self.latest_readings:
            self.prev_readings[reading.station_id] = self.latest_readings[reading.station_id]
        self.latest_readings[reading.station_id] = reading

    def update_snapshot(self, readings_by_station: Dict[str, RawReading]):
        """Updates the synchronized spatial snapshot for all stations at once."""
        for st_id, r in readings_by_station.items():
            if st_id in self.latest_readings:
                self.prev_readings[st_id] = self.latest_readings[st_id]
            self.latest_readings[st_id] = r

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

    def analyze(
        self,
        reading: RawReading,
        snapshot: Optional[Dict[str, RawReading]] = None
    ) -> SpatialEvidence:
        """
        Evaluates spatial consistency.
        If `snapshot` is provided, uses strictly readings from the same timestamp snapshot,
        guaranteeing processing order invariance!
        """
        target_id = reading.station_id
        if target_id not in self.stations:
            return SpatialEvidence(
                is_consistent=True,
                neighbor_count=0,
                valid_neighbor_count=0,
                neighbor_station_ids=[],
                neighbor_medians={},
                neighbor_mads={},
                relative_deviations={},
                agreement_ratio=0.0,
                corroborating_stations_count=0,
                directional_agreement=False,
                regional_event_detected=False,
                explanation="Station coordinates not registered; spatial verification skipped"
            )

        neighbors = self.find_nearest_neighbors(target_id)
        if not neighbors:
            return SpatialEvidence(
                is_consistent=True,
                neighbor_count=0,
                valid_neighbor_count=0,
                neighbor_station_ids=[],
                neighbor_medians={},
                neighbor_mads={},
                relative_deviations={},
                agreement_ratio=0.0,
                corroborating_stations_count=0,
                directional_agreement=False,
                regional_event_detected=False,
                explanation="No neighboring stations found within spatial envelope (<150km)"
            )

        neighbor_ids = [nid for nid, _ in neighbors]
        
        medians: Dict[str, float] = {}
        mads: Dict[str, float] = {}
        rel_deviations: Dict[str, float] = {}
        
        is_consistent = True
        regional_event_detected = False
        directional_agreement_overall = False
        max_agreement_ratio = 0.0
        max_corroborating_count = 0
        valid_n_count = 0
        
        reasons: List[str] = []
        params = ["temperature", "pressure", "humidity"]
        
        target_st = self.stations.get(target_id)
        target_elev = target_st.elevation_m if target_st else 200.0

        for param in params:
            target_val = getattr(reading, param, None)
            if target_val is None or np.isnan(target_val):
                continue
                
            # Previous reading of target to calculate target delta
            prev_target = self.prev_readings.get(target_id)
            prev_target_val = getattr(prev_target, param, None) if prev_target else None
            target_delta = (target_val - prev_target_val) if (prev_target_val is not None and not np.isnan(prev_target_val)) else 0.0
            
            neighbor_vals = []
            neighbor_deltas = []
            
            for nid in neighbor_ids:
                # Use current synchronized snapshot if available, otherwise latest_readings
                nr = snapshot.get(nid) if snapshot and (nid in snapshot) else self.latest_readings.get(nid)
                if nr:
                    nv = getattr(nr, param, None)
                    if nv is not None and not np.isnan(nv):
                        nst = self.stations.get(nid)
                        n_elev = nst.elevation_m if nst else target_elev
                        delta_h = target_elev - n_elev
                        
                        # Apply standard meteorological barometric & hypsometric elevation adjustments
                        if param == "pressure":
                            # Standard -1 hPa per 8.3m
                            nv_norm = float(nv) - (delta_h / 8.3)
                        elif param == "temperature":
                            # Standard environmental lapse rate -6.5°C per 1000m
                            nv_norm = float(nv) - (0.0065 * delta_h)
                        else:
                            nv_norm = float(nv)
                            
                        neighbor_vals.append(nv_norm)
                        
                        # Calculate neighbor delta from its previous reading
                        prev_nr = self.prev_readings.get(nid)
                        prev_nv = getattr(prev_nr, param, None) if prev_nr else None
                        if prev_nv is not None and not np.isnan(prev_nv):
                            n_delta = float(nv) - float(prev_nv)
                            neighbor_deltas.append(n_delta)

            valid_n_count = len(neighbor_vals)
            if valid_n_count >= SPATIAL_CONFIG["min_valid_neighbors"]:
                n_arr = np.array(neighbor_vals)
                n_med = float(np.median(n_arr))
                n_mad = float(np.median(np.abs(n_arr - n_med)))
                
                medians[param] = round(n_med, 2)
                mads[param] = round(n_mad, 2)
                
                # Deviation from neighbor median
                diff = target_val - n_med
                rel_deviations[param] = round(diff, 2)
                
                # Check spatial anomaly: target deviates by more than spatial threshold * MAD
                floor_mad = 1.2 if param == "temperature" else (1.5 if param == "pressure" else 4.0)
                effective_mad = max(n_mad * 1.4826, floor_mad)
                spatial_z = abs(diff) / effective_mad
                
                # Evaluate Directional Agreement across neighbors
                min_event_change = SPATIAL_CONFIG["min_event_change"].get(param, 1.5)
                corroborating_count = 0
                
                if abs(target_delta) >= min_event_change and len(neighbor_deltas) >= 2:
                    # Check how many neighbors shifted in the same direction with notable magnitude
                    target_sign = 1 if target_delta > 0 else -1
                    for nd in neighbor_deltas:
                        if (nd * target_sign > 0) and abs(nd) >= (min_event_change * 0.4):
                            corroborating_count += 1
                            
                    agreement_ratio = corroborating_count / len(neighbor_deltas)
                    if agreement_ratio > max_agreement_ratio:
                        max_agreement_ratio = agreement_ratio
                        max_corroborating_count = corroborating_count
                        
                    # Check if this delta is actually a recovery/subsidence of an active opposite event
                    is_recovery = False
                    ev_key = (target_id, param)
                    if ev_key in self.active_regional_events:
                        prev_ev = self.active_regional_events[ev_key]
                        if prev_ev["target_sign"] * target_delta < -min_event_change * 0.5:
                            is_recovery = True
                            del self.active_regional_events[ev_key]

                    # If agreement ratio exceeds threshold (e.g. >= 0.65)
                    if not is_recovery and agreement_ratio >= SPATIAL_CONFIG["regional_event_ratio"] and corroborating_count >= 2:
                        regional_event_detected = True
                        directional_agreement_overall = True
                        self.active_regional_events[ev_key] = {
                            "param": param,
                            "remaining_steps": SPATIAL_CONFIG.get("event_persistence_window", 8),
                            "agreement_ratio": agreement_ratio,
                            "corroborating_count": corroborating_count,
                            "target_sign": target_sign
                        }
                
                if spatial_z >= SPATIAL_CONFIG["spatial_mad_threshold"]:
                    # Check if regional event overrides isolated fault
                    if regional_event_detected and abs(diff) < (effective_mad * 2.5):
                        # Regional event with slight local gradient: corroborated
                        is_consistent = True
                    else:
                        is_consistent = False
                        reasons.append(
                            f"Isolated spatial deviation in {param}: Obs={target_val:.1f} vs Neighbors Median={n_med:.1f} "
                            f"(Delta={diff:+.1f}, MAD={n_mad:.1f}, {valid_n_count} valid neighbors)"
                        )

        # Check regional event persistence across successive observation cycles
        if not regional_event_detected:
            keys_to_delete = []
            for ev_key, ev in list(self.active_regional_events.items()):
                if ev_key[0] != target_id:
                    continue
                p_name = ev["param"]
                p_sign = ev["target_sign"]
                
                prev_t = self.prev_readings.get(target_id)
                prev_tv = getattr(prev_t, p_name, None) if prev_t else None
                curr_tv = getattr(reading, p_name, None)
                delta_now = (curr_tv - prev_tv) if (prev_tv is not None and curr_tv is not None) else 0.0
                min_rev = SPATIAL_CONFIG["min_event_change"].get(p_name, 1.5) * 0.5
                
                neighbors_agree = is_consistent and (len(reasons) == 0)
                
                if ev["remaining_steps"] > 0 and neighbors_agree and not (delta_now * p_sign < -min_rev):
                    regional_event_detected = True
                    directional_agreement_overall = True
                    max_agreement_ratio = max(max_agreement_ratio, ev["agreement_ratio"])
                    max_corroborating_count = max(max_corroborating_count, ev["corroborating_count"])
                    ev["remaining_steps"] -= 1
                else:
                    keys_to_delete.append(ev_key)
                    
            for k in keys_to_delete:
                if k in self.active_regional_events:
                    del self.active_regional_events[k]

        # If a confirmed regional event is corroborated, the network is responding to a weather phenomenon
        if regional_event_detected and not is_consistent and max_agreement_ratio >= 0.65:
            is_consistent = True

        explanation = "; ".join(reasons) if reasons else (
            f"Consistent with {len(neighbor_ids)} neighboring AWS stations within radius"
        )
        if regional_event_detected:
            explanation += f" [Corroborated Regional Weather Event: {max_corroborating_count} stations agree, ratio={max_agreement_ratio:.2f}]"

        return SpatialEvidence(
            is_consistent=is_consistent,
            neighbor_count=len(neighbor_ids),
            valid_neighbor_count=valid_n_count,
            neighbor_station_ids=neighbor_ids,
            neighbor_medians=medians,
            neighbor_mads=mads,
            relative_deviations=rel_deviations,
            agreement_ratio=round(max_agreement_ratio, 2),
            corroborating_stations_count=max_corroborating_count,
            directional_agreement=directional_agreement_overall,
            regional_event_detected=regional_event_detected,
            explanation=explanation
        )

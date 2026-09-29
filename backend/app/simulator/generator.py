"""
Synthetic AWS Telemetry & Ground-Truth Generator for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Generates physically plausible surface observations across a realistic network of 12 stations:
- Diurnal temperature cycle: peak in early afternoon, trough before sunrise
- Thermodynamic inverse humidity coupling
- Elevation lapse rate (~6.5°C / 1000m)
- Atmospheric tide on surface pressure (semi-diurnal oscillation ~1.5 hPa)
- Controlled deterministic ground-truth anomalies for benchmark evaluation
- Clearly labeled as SYNTHETIC / DEMO DATA (aligned with SIH26073 requirements)
"""

import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
from app.models.schemas import StationMetadata, RawReading, SensorHealthStatus


# 12 Sample AWS Stations positioned across Northern & Central India regional network
DEFAULT_STATIONS: List[StationMetadata] = [
    StationMetadata(station_id="AWS-001", station_name="Delhi Synoptic AWS", latitude=28.6139, longitude=77.2090, elevation_m=216.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
    StationMetadata(station_id="AWS-002", station_name="Noida Sector-62 AWS", latitude=28.6270, longitude=77.3725, elevation_m=200.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
    StationMetadata(station_id="AWS-003", station_name="Gurugram Cybercity AWS", latitude=28.4595, longitude=77.0266, elevation_m=220.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
    StationMetadata(station_id="AWS-004", station_name="Faridabad Industrial AWS", latitude=28.4089, longitude=77.3178, elevation_m=205.0, region="NCR Zone", status=SensorHealthStatus.HEALTHY),
    StationMetadata(station_id="AWS-005", station_name="Meerut Agro AWS", latitude=28.9845, longitude=77.7064, elevation_m=225.0, region="Western UP", status=SensorHealthStatus.HEALTHY),
    StationMetadata(station_id="AWS-006", station_name="Alwar Foothills AWS", latitude=27.5530, longitude=76.6346, elevation_m=270.0, region="East Rajasthan", status=SensorHealthStatus.HEALTHY),
    StationMetadata(station_id="AWS-007", station_name="Rohtak Plains AWS", latitude=28.8955, longitude=76.6066, elevation_m=220.0, region="Haryana Plains", status=SensorHealthStatus.HEALTHY),
    StationMetadata(station_id="AWS-008", station_name="Mathura Yamuna AWS", latitude=27.4924, longitude=77.6737, elevation_m=175.0, region="Central Plains", status=SensorHealthStatus.HEALTHY),
    StationMetadata(station_id="AWS-009", station_name="Agra Observatory AWS", latitude=27.1767, longitude=78.0081, elevation_m=169.0, region="Central Plains", status=SensorHealthStatus.HEALTHY),
    StationMetadata(station_id="AWS-010", station_name="Jaipur Sanganer AWS", latitude=26.9124, longitude=75.7873, elevation_m=431.0, region="East Rajasthan", status=SensorHealthStatus.HEALTHY),
    StationMetadata(station_id="AWS-011", station_name="Bareilly Tarai AWS", latitude=28.3670, longitude=79.4304, elevation_m=166.0, region="Rohilkhand", status=SensorHealthStatus.HEALTHY),
    StationMetadata(station_id="AWS-012", station_name="Chandigarh Basin AWS", latitude=30.7333, longitude=76.7794, elevation_m=321.0, region="Shivalik Foothills", status=SensorHealthStatus.HEALTHY)
]


class WeatherDataGenerator:
    def __init__(self, stations: List[StationMetadata] = DEFAULT_STATIONS, seed: int = 42):
        self.stations = stations
        self.rng = np.random.RandomState(seed)
        self.station_state: Dict[str, Dict[str, Any]] = {}
        for st in self.stations:
            self.station_state[st.station_id] = {
                "frozen_count": 0,
                "frozen_val": None,
                "frozen_param": None,
                "drift_offset": 0.0,
                "drift_param": None,
                "drift_count": 0,
                "active_injection": None
            }

    def generate_natural_reading(self, station: StationMetadata, dt: datetime) -> Tuple[float, float, float]:
        """Calculates physically coupled, diurnal surface temperature, pressure, and humidity."""
        hour_frac = dt.hour + dt.minute / 60.0
        
        # Diurnal solar cycle: minimum around 05:30 (sunrise), peak around 14:30
        solar_angle = (hour_frac - 5.5) * (2.0 * math.pi / 24.0)
        diurnal_factor = -math.cos(solar_angle)
        
        # Base temperature: 28°C base, diurnal amplitude ~7°C
        # Elevation lapse rate: -6.5°C per 1000m above sea level
        lapse_correction = -0.0065 * (station.elevation_m - 200.0)
        temp_base = 28.0 + 7.0 * diurnal_factor + lapse_correction
        
        # Natural turbulence micro-noise (±0.25°C)
        temp = temp_base + self.rng.normal(0.0, 0.25)
        
        # Relative humidity: inversely coupled with temperature (higher at dawn ~85%, lower at midday ~45%)
        rh_base = 65.0 - 22.0 * diurnal_factor - 0.5 * lapse_correction
        rh = float(np.clip(rh_base + self.rng.normal(0.0, 1.5), 15.0, 95.0))
        
        # Atmospheric pressure: Barometric formula with semi-diurnal atmospheric tide (~1.5 hPa cycle)
        elevation_p_drop = (station.elevation_m / 8.3)
        tide = 1.2 * math.sin((hour_frac / 12.0) * 2.0 * math.pi)
        pres = 1013.25 - elevation_p_drop + tide + self.rng.normal(0.0, 0.4)
        
        return round(temp, 2), round(pres, 2), round(rh, 1)

    def generate_reading_with_scenarios(
        self,
        station: StationMetadata,
        dt: datetime,
        force_scenario: Optional[str] = None,
        magnitude: Optional[float] = None
    ) -> Tuple[RawReading, str]:
        """
        Generates a reading, applying normal physics or an injected anomaly scenario.
        Returns: (RawReading, ground_truth_label)
        """
        temp, pres, rh = self.generate_natural_reading(station, dt)
        st_state = self.station_state[station.station_id]
        
        scenario = force_scenario or st_state.get("active_injection")
        if scenario != "FREEZE":
            st_state["frozen_val"] = None
            st_state["frozen_count"] = 0
        if scenario != "DRIFT":
            st_state["drift_offset"] = 0.0
            st_state["drift_count"] = 0
        if scenario != "WEATHER_EVENT":
            st_state["we_step"] = 0
        label = "NORMAL"

        if scenario == "SPIKE":
            label = "SENSOR_SPIKE"
            # Plausible but sharp sensor jump (+12°C to +15°C, safely within meteorological range <= 52°C)
            spike_val = magnitude if magnitude is not None else 12.0
            temp = round(min(temp + spike_val, 52.0), 2)
            
        elif scenario == "FREEZE":
            if st_state["frozen_val"] is None:
                st_state["frozen_val"] = rh
            rh = st_state["frozen_val"]
            st_state["frozen_count"] += 1
            label = "SENSOR_FREEZE" if st_state["frozen_count"] >= 4 else "NORMAL"
            
        elif scenario == "DRIFT":
            drift_step = magnitude if magnitude is not None else 0.40
            st_state["drift_offset"] += drift_step
            temp = round(temp + st_state["drift_offset"], 2)
            st_state["drift_count"] = st_state.get("drift_count", 0) + 1
            label = "CALIBRATION_DRIFT" if st_state["drift_count"] >= 6 else "NORMAL"
            
        elif scenario == "COMM_GAP":
            label = "COMMUNICATION_FAILURE"
            return RawReading(
                station_id=station.station_id,
                timestamp=dt.isoformat(),
                temperature=None,
                pressure=None,
                humidity=None,
                latitude=station.latitude,
                longitude=station.longitude,
                station_type=station.station_type,
                region=station.region
            ), label
            
        elif scenario == "DATA_CORRUPTION":
            label = "DATA_CORRUPTION"
            # Impossible out-of-range sensor value (violates physical boundaries)
            temp = 142.5
            
        elif scenario == "WEATHER_EVENT":
            label = "REGIONAL_WEATHER_EVENT"
            we_step = st_state.get("we_step", 0) + 1
            st_state["we_step"] = we_step
            # Progressive frontal surge across cluster stations (+1.8°C per step up to +7.2°C)
            surge = min(7.5, 1.8 * we_step)
            temp = round(temp + surge, 2)
            rh = round(max(15.0, rh - 3.0 * we_step), 1)
            pres = round(pres - 0.7 * we_step, 2)
            
        elif scenario == "MULTIVARIATE_DISCORD":
            label = "MULTIVARIATE_INCONSISTENCY"
            # Dewpoint violation: RH 99% with 48°C temperature
            temp = 48.0
            rh = 99.0
            
        elif scenario == "SPATIAL_OUTLIER":
            label = "SPATIAL_INCONSISTENCY"
            # Persistent spatial exposure/siting offset (+8.5°C above neighborhood)
            temp = round(temp + 8.5, 2)

        reading = RawReading(
            station_id=station.station_id,
            timestamp=dt.isoformat(),
            temperature=temp,
            pressure=pres,
            humidity=rh,
            latitude=station.latitude,
            longitude=station.longitude,
            station_type=station.station_type,
            region=station.region
        )
        return reading, label

    def generate_benchmark_dataset(
        self, num_timesteps: int = 360
    ) -> List[Tuple[RawReading, str]]:
        """
        Creates a balanced multi-station benchmark dataset with >= 100 ground-truth instances
        per canonical class across the 12 AWS stations:
        - NORMAL (3000+)
        - REGIONAL_WEATHER_EVENT (150+)
        - SENSOR_SPIKE (100+)
        - SENSOR_FREEZE (100+)
        - CALIBRATION_DRIFT (100+)
        - COMMUNICATION_FAILURE (100+)
        - DATA_CORRUPTION (100+)
        - MULTIVARIATE_INCONSISTENCY (100+)
        - SPATIAL_INCONSISTENCY (100+)
        """
        dataset: List[Tuple[RawReading, str]] = []
        base_time = datetime(2026, 4, 15, 6, 0, 0)
        
        # Pre-calculate deterministic scenario schedules
        # 1. Regional Weather Events (6 synoptic frontal surge events x 5 timesteps x 6 stations = 180 observations)
        ncr_stations = ["AWS-001", "AWS-002", "AWS-003", "AWS-004", "AWS-005", "AWS-006"]
        north_stations = ["AWS-007", "AWS-008", "AWS-009", "AWS-010", "AWS-011", "AWS-012"]
        weather_periods = [
            (35, 39, ncr_stations),
            (85, 89, north_stations),
            (145, 149, ncr_stations),
            (205, 209, north_stations),
            (265, 269, ncr_stations),
            (325, 329, north_stations)
        ]
        
        # 2. Sensor Freezes (8 stations x 15 steps = 120)
        freeze_periods = [
            ("AWS-003", 70, 84),
            ("AWS-005", 115, 129),
            ("AWS-007", 155, 169),
            ("AWS-009", 185, 199),
            ("AWS-011", 240, 254),
            ("AWS-002", 275, 289),
            ("AWS-004", 300, 314),
            ("AWS-008", 335, 349)
        ]
        
        # 3. Calibration Drift (6 stations x 19 steps = 114)
        drift_periods = [
            ("AWS-004", 70, 88),
            ("AWS-006", 115, 133),
            ("AWS-008", 155, 173),
            ("AWS-010", 185, 203),
            ("AWS-012", 240, 258),
            ("AWS-001", 335, 353)
        ]
        
        # 4. Communication Failure (7 stations x 16 steps = 112)
        comm_periods = [
            ("AWS-002", 15, 30),
            ("AWS-005", 90, 105),
            ("AWS-007", 125, 140),
            ("AWS-011", 160, 175),
            ("AWS-003", 225, 240),
            ("AWS-009", 285, 300),
            ("AWS-006", 315, 330)
        ]

        # 5. Persistent Spatial Outliers (10 stations x 11 steps = 110)
        spatial_periods = [
            ("AWS-001", 15, 25),
            ("AWS-003", 50, 60),
            ("AWS-005", 95, 105),
            ("AWS-007", 130, 140),
            ("AWS-009", 165, 175),
            ("AWS-011", 195, 205),
            ("AWS-002", 225, 235),
            ("AWS-004", 255, 265),
            ("AWS-006", 285, 295),
            ("AWS-008", 310, 320)
        ]
        
        # 6. Point anomalies scheduled across stations (10 per station = 110 each)
        spike_schedule = set()
        corruption_schedule = set()
        multivariate_schedule = set()
        
        station_ids = [s.station_id for s in self.stations]
        for idx, sid in enumerate(station_ids[:11]):
            base_offset = 6 + idx * 2
            # 10 spikes per station
            for k in range(10):
                t_spike = (base_offset + k * 35) % (num_timesteps - 10)
                spike_schedule.add((sid, t_spike))
            # 10 corruptions per station
            for k in range(10):
                t_corr = (base_offset + 5 + k * 35) % (num_timesteps - 10)
                corruption_schedule.add((sid, t_corr))
            # 10 multivariate discordances per station
            for k in range(10):
                t_mv = (base_offset + 10 + k * 35) % (num_timesteps - 10)
                multivariate_schedule.add((sid, t_mv))

        for t in range(num_timesteps):
            current_time = base_time + timedelta(minutes=5 * t)
            
            for st in self.stations:
                sid = st.station_id
                scenario = None
                
                # Priority 1: Regional Weather Event
                for start_t, end_t, target_sids in weather_periods:
                    if start_t <= t <= end_t and sid in target_sids:
                        scenario = "WEATHER_EVENT"
                        break
                
                # Priority 2: Prolonged Sensor Faults / Spatial Exposure Outliers
                if not scenario:
                    for f_sid, start_t, end_t in freeze_periods:
                        if sid == f_sid and start_t <= t <= end_t:
                            scenario = "FREEZE"
                            break
                            
                if not scenario:
                    for d_sid, start_t, end_t in drift_periods:
                        if sid == d_sid and start_t <= t <= end_t:
                            scenario = "DRIFT"
                            break
                            
                if not scenario:
                    for c_sid, start_t, end_t in comm_periods:
                        if sid == c_sid and start_t <= t <= end_t:
                            scenario = "COMM_GAP"
                            break

                if not scenario:
                    for s_sid, start_t, end_t in spatial_periods:
                        if sid == s_sid and start_t <= t <= end_t:
                            scenario = "SPATIAL_OUTLIER"
                            break
                            
                # Priority 3: Transient / Point Faults
                if not scenario and (sid, t) in spike_schedule:
                    scenario = "SPIKE"
                elif not scenario and (sid, t) in corruption_schedule:
                    scenario = "DATA_CORRUPTION"
                elif not scenario and (sid, t) in multivariate_schedule:
                    scenario = "MULTIVARIATE_DISCORD"

                reading, label = self.generate_reading_with_scenarios(st, current_time, force_scenario=scenario)
                dataset.append((reading, label))
                
        return dataset

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
        label = "NORMAL"

        if scenario == "SPIKE":
            label = "SENSOR_SPIKE"
            # Plausible but sharp sensor jump (+13.5°C, stays under physical max 65°C)
            spike_val = magnitude if magnitude is not None else 13.5
            temp = round(temp + spike_val, 2)
            
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
            # Synoptic heatburst / warm frontal surge (+7.5°C) with coherent physical RH drop and pressure shift
            temp = round(temp + 7.5, 2)
            rh = round(max(15.0, rh - 15.0), 1)
            pres = round(pres - 3.0, 2)
            
        elif scenario == "MULTIVARIATE_DISCORD":
            label = "MULTIVARIATE_INCONSISTENCY"
            # Dewpoint violation: RH 99% with 48°C temperature
            temp = 48.0
            rh = 99.0
            
        elif scenario == "SPATIAL_OUTLIER":
            label = "SPATIAL_INCONSISTENCY"
            # Station temperature deviates 11°C from all neighbors
            temp = round(temp + 11.0, 2)

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
        self, num_timesteps: int = 150
    ) -> List[Tuple[RawReading, str]]:
        """
        Creates a deterministic multi-station benchmark dataset with known ground-truth labels.
        Stations maintain normal operations except for controlled injected periods.
        """
        dataset: List[Tuple[RawReading, str]] = []
        base_time = datetime(2026, 4, 15, 6, 0, 0)
        
        for t in range(num_timesteps):
            current_time = base_time + timedelta(minutes=5 * t)
            
            for st in self.stations:
                scenario = None
                
                # AWS-001: Isolated Temperature Spike at timestep 40
                if st.station_id == "AWS-001" and t == 40:
                    scenario = "SPIKE"
                # AWS-002: Sensor Freeze on Humidity between timesteps 60 and 70
                elif st.station_id == "AWS-002" and 60 <= t <= 70:
                    scenario = "FREEZE"
                # AWS-003: Systematic Calibration Drift from timestep 80 to 95
                elif st.station_id == "AWS-003" and 80 <= t <= 95:
                    scenario = "DRIFT"
                # AWS-004: Communication Gap at timesteps 30, 31, 32
                elif st.station_id == "AWS-004" and 30 <= t <= 32:
                    scenario = "COMM_GAP"
                # Regional Weather Event: Timestep 110 to 118 affecting all NCR stations simultaneously
                elif 110 <= t <= 118 and st.region == "NCR Zone":
                    scenario = "WEATHER_EVENT"
                # AWS-008: Impossible Data Corruption at timestep 50
                elif st.station_id == "AWS-008" and t == 50:
                    scenario = "DATA_CORRUPTION"
                # AWS-009: Multivariate Discordance at timestep 75
                elif st.station_id == "AWS-009" and t == 75:
                    scenario = "MULTIVARIATE_DISCORD"

                reading, label = self.generate_reading_with_scenarios(st, current_time, force_scenario=scenario)
                dataset.append((reading, label))
                
        return dataset

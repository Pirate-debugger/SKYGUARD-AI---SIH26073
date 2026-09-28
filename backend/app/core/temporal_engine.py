"""
Temporal Analysis Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Multi-timescale time-series analytics:
- LEVEL 1 (Instantaneous): Rate of change (delta per minute), extreme jump detection
- LEVEL 2 (Short-term): Rolling median, robust MAD z-score, frozen sensor detection
- LEVEL 3 (Long-term / Trend): Diurnal baseline, linear drift regression, CUSUM change-point detection

Strict Anti-Leakage Design:
Evaluates telemetry strictly against pre-current history.
Buffer update is decoupled via commit() called only after downstream analysis and imputation.
"""

from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from app.config import TEMPORAL_CONFIG, CUSUM_CONFIG, MAX_RATE_OF_CHANGE_PER_MIN
from app.models.schemas import RawReading, TemporalEvidence


class StationTemporalBuffer:
    """Maintains a rolling historical buffer of observations strictly before current timestep."""
    def __init__(self, maxlen: int = TEMPORAL_CONFIG["window_size"]):
        self.maxlen = maxlen
        self.history: deque = deque(maxlen=maxlen)
        
        # CUSUM state per parameter: param -> {"s_pos": float, "s_neg": float}
        self.cusum_state: Dict[str, Dict[str, float]] = {
            "temperature": {"s_pos": 0.0, "s_neg": 0.0},
            "pressure": {"s_pos": 0.0, "s_neg": 0.0},
            "humidity": {"s_pos": 0.0, "s_neg": 0.0}
        }

    def add(self, reading: RawReading):
        self.history.append({
            "timestamp": reading.timestamp,
            "temperature": reading.temperature,
            "pressure": reading.pressure,
            "humidity": reading.humidity
        })

    def get_parameter_series(self, param: str) -> List[float]:
        vals = []
        for item in self.history:
            v = item.get(param)
            if v is not None and not np.isnan(v):
                vals.append(float(v))
        return vals

    def get_timestamps(self) -> List[str]:
        return [item["timestamp"] for item in self.history]


class TemporalEngine:
    def __init__(self):
        self.station_buffers: Dict[str, StationTemporalBuffer] = {}

    def get_or_create_buffer(self, station_id: str) -> StationTemporalBuffer:
        if station_id not in self.station_buffers:
            self.station_buffers[station_id] = StationTemporalBuffer()
        return self.station_buffers[station_id]

    def analyze(self, reading: RawReading) -> TemporalEvidence:
        """
        Analyzes reading against PRE-CURRENT historical buffer.
        Does NOT commit reading to buffer (commit is done via commit_reading).
        """
        buffer = self.get_or_create_buffer(reading.station_id)
        
        rates_of_change: Dict[str, float] = {}
        rolling_means: Dict[str, float] = {}
        rolling_stds: Dict[str, float] = {}
        robust_z_scores: Dict[str, float] = {}
        frozen_steps: Dict[str, int] = {}
        trend_slopes: Dict[str, float] = {}
        
        spike_detected = False
        drop_detected = False
        freeze_detected = False
        drift_detected = False
        change_point_detected = False
        change_point_param: Optional[str] = None
        change_point_direction: Optional[str] = None
        change_point_magnitude: Optional[float] = None
        
        reasons: List[str] = []
        params = ["temperature", "pressure", "humidity"]
        
        for param in params:
            val = getattr(reading, param, None)
            if val is None or np.isnan(val):
                continue
                
            history = buffer.get_parameter_series(param)
            
            # --- LEVEL 1: Instantaneous Rate of Change ---
            if len(history) >= 1:
                last_val = history[-1]
                prev_ts_str = buffer.get_timestamps()[-1]
                try:
                    t_curr = datetime.fromisoformat(reading.timestamp.replace("Z", "+00:00"))
                    t_prev = datetime.fromisoformat(prev_ts_str.replace("Z", "+00:00"))
                    dt_min = max((t_curr - t_prev).total_seconds() / 60.0, 0.05)
                except Exception:
                    dt_min = 1.0
                
                delta = val - last_val
                rate_per_min = abs(delta) / dt_min
                rates_of_change[param] = round(rate_per_min, 3)
                
                max_rate = MAX_RATE_OF_CHANGE_PER_MIN.get(param, 5.0)
                if rate_per_min > max_rate:
                    if delta > 0:
                        spike_detected = True
                        reasons.append(
                            f"Abrupt {param} spike: Delta={delta:+.1f} in {dt_min*60:.0f}s ({rate_per_min:.2f}/min > limit {max_rate}/min)"
                        )
                    else:
                        drop_detected = True
                        reasons.append(
                            f"Abrupt {param} drop: Delta={delta:+.1f} in {dt_min*60:.0f}s ({rate_per_min:.2f}/min > limit {max_rate}/min)"
                        )

            # --- LEVEL 2: Short-term Rolling Robust Statistics ---
            if len(history) >= TEMPORAL_CONFIG["min_window_for_stats"]:
                arr = np.array(history, dtype=float)
                mean_val = float(np.mean(arr))
                std_val = float(np.std(arr)) if len(arr) > 1 else 0.0
                rolling_means[param] = round(mean_val, 2)
                rolling_stds[param] = round(std_val, 2)
                
                # Robust Z-score using Median Absolute Deviation (MAD)
                median_val = float(np.median(arr))
                mad = float(np.median(np.abs(arr - median_val)))
                mad_std = mad * 1.4826  # asymptotic normal consistency factor
                
                # Floor on scale to prevent micro-fluctuations in quiet air from creating massive z-scores
                min_scale_floor = 0.8 if param == "temperature" else (0.8 if param == "pressure" else 3.5)
                effective_scale = max(mad_std if mad_std > 1e-4 else std_val, min_scale_floor)
                robust_z = (val - median_val) / effective_scale
                robust_z_scores[param] = round(float(robust_z), 2)
                
                # Minimum absolute deviation requirement (meteorologically meaningful shift)
                min_abs_dev = 2.5 if param == "temperature" else (2.0 if param == "pressure" else 8.0)
                if abs(robust_z) >= TEMPORAL_CONFIG["spike_z_threshold"] and abs(val - median_val) >= min_abs_dev:
                    if robust_z > 0:
                        spike_detected = True
                    else:
                        drop_detected = True
                    reasons.append(
                        f"Statistical temporal excursion in {param}: robust Z={robust_z:+.1f} "
                        f"(Obs={val}, RollingMed={median_val:.1f}, Delta={val-median_val:+.1f})"
                    )

                # --- LEVEL 3A: CUSUM Change-Point Detection ---
                # Detects sustained mean shifts / sudden regime change
                k = CUSUM_CONFIG["drift_allowance_k"]
                h = CUSUM_CONFIG["decision_threshold_h"]
                c_state = buffer.cusum_state.get(param, {"s_pos": 0.0, "s_neg": 0.0})
                
                norm_dev = (val - median_val) / effective_scale
                s_pos = max(0.0, c_state["s_pos"] + (norm_dev - k))
                s_neg = max(0.0, c_state["s_neg"] - (norm_dev + k))
                
                if abs(val - median_val) >= min_abs_dev:
                    if s_pos > h:
                        change_point_detected = True
                        change_point_param = param
                        change_point_direction = "INCREASE"
                        change_point_magnitude = round(float(norm_dev), 2)
                        reasons.append(f"CUSUM Change-Point in {param}: Abrupt upward regime shift (S+={s_pos:.1f} > {h})")
                    elif s_neg > h:
                        change_point_detected = True
                        change_point_param = param
                        change_point_direction = "DECREASE"
                        change_point_magnitude = round(float(norm_dev), 2)
                        reasons.append(f"CUSUM Change-Point in {param}: Abrupt downward regime shift (S-={s_neg:.1f} > {h})")

            # --- LEVEL 2B: Frozen Sensor Detection ---
            consecutive_identical = 1
            for prev_v in reversed(history):
                if abs(val - prev_v) < 1e-3:
                    consecutive_identical += 1
                else:
                    break
            
            frozen_steps[param] = consecutive_identical
            if consecutive_identical >= TEMPORAL_CONFIG["freeze_min_consecutive"]:
                freeze_detected = True
                reasons.append(
                    f"Suspiciously frozen {param}: identical value {val} across {consecutive_identical} consecutive steps"
                )

            # --- LEVEL 3B: Calibration Drift (Monotonic Linear Trend) ---
            if len(history) >= TEMPORAL_CONFIG["drift_min_steps"]:
                combined = list(history) + [val]
                # Evaluate drift over recent trend window (up to 12 points) to avoid ancient baseline
                w_slice = combined[-12:] if len(combined) > 12 else combined
                x = np.arange(len(w_slice))
                y = np.array(w_slice, dtype=float)
                slope, _ = np.polyfit(x, y, 1)
                trend_slopes[param] = round(float(slope), 4)
                
                y_pred = slope * x + np.mean(y) - slope * np.mean(x)
                residuals_std = np.std(y - y_pred)
                
                nominal_scale = 30.0 if param == "temperature" else (50.0 if param == "humidity" else 20.0)
                norm_slope = abs(slope) / nominal_scale
                if norm_slope >= TEMPORAL_CONFIG["drift_slope_threshold"] and residuals_std < 1.2:
                    drift_detected = True
                    reasons.append(
                        f"Calibration drift pattern in {param}: monotonic slope={slope:+.3f}/step over {len(w_slice)} points"
                    )

        # Monotonic calibration drift overrides statistical excursion spike when instant rate-of-change is normal
        if drift_detected and not any(r > MAX_RATE_OF_CHANGE_PER_MIN.get(p, 5.0) for p, r in rates_of_change.items()):
            spike_detected = False
            drop_detected = False

        explanation = "; ".join(reasons) if reasons else "Temporal parameters within expected variance envelope"
        
        return TemporalEvidence(
            spike_detected=spike_detected,
            drop_detected=drop_detected,
            freeze_detected=freeze_detected,
            drift_detected=drift_detected,
            change_point_detected=change_point_detected,
            change_point_param=change_point_param,
            change_point_direction=change_point_direction,
            change_point_magnitude=change_point_magnitude,
            rates_of_change=rates_of_change,
            rolling_means=rolling_means,
            rolling_stds=rolling_stds,
            robust_z_scores=robust_z_scores,
            frozen_duration_steps=frozen_steps,
            trend_slopes=trend_slopes,
            explanation=explanation
        )

    def commit_reading(self, reading: RawReading):
        """
        Commits reading to the historical rolling buffer and updates CUSUM state.
        STRICT ANTI-LEAKAGE: MUST ONLY BE CALLED AFTER downstream analysis & imputation!
        """
        buffer = self.get_or_create_buffer(reading.station_id)
        
        # Update CUSUM running state if we have stats
        for param in ["temperature", "pressure", "humidity"]:
            val = getattr(reading, param, None)
            if val is None or np.isnan(val):
                continue
            history = buffer.get_parameter_series(param)
            if len(history) >= TEMPORAL_CONFIG["min_window_for_stats"]:
                arr = np.array(history, dtype=float)
                median_val = float(np.median(arr))
                mad = float(np.median(np.abs(arr - median_val)))
                scale = (mad * 1.4826) if (mad * 1.4826) > 1e-4 else (np.std(arr) if np.std(arr) > 1e-4 else 1.0)
                norm_dev = (val - median_val) / scale
                
                k = CUSUM_CONFIG["drift_allowance_k"]
                c_state = buffer.cusum_state[param]
                c_state["s_pos"] = max(0.0, c_state["s_pos"] + (norm_dev - k))
                c_state["s_neg"] = max(0.0, c_state["s_neg"] - (norm_dev + k))
                # Reset if boundary breached
                if c_state["s_pos"] > CUSUM_CONFIG["decision_threshold_h"]:
                    c_state["s_pos"] = 0.0
                if c_state["s_neg"] > CUSUM_CONFIG["decision_threshold_h"]:
                    c_state["s_neg"] = 0.0
        
        buffer.add(reading)

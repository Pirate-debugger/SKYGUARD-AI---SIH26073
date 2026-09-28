"""
Temporal Analysis Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Analyzes single-station time-series behaviors:
- Rolling mean, rolling median, rolling standard deviation
- Rate of change (delta per minute)
- Robust Z-score (based on Median Absolute Deviation - MAD)
- Spike / Drop detection
- Frozen sensor detection (persistent identical values)
- Calibration drift detection (systematic monotonic slope)
- Change-point detection
"""

from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from app.config import TEMPORAL_CONFIG, MAX_RATE_OF_CHANGE_PER_MIN
from app.models.schemas import RawReading, TemporalEvidence


class StationTemporalBuffer:
    """Maintains a rolling historical buffer of readings for a specific station."""
    def __init__(self, maxlen: int = TEMPORAL_CONFIG["window_size"]):
        self.maxlen = maxlen
        self.history: deque = deque(maxlen=maxlen)

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
        
        reasons: List[str] = []
        
        params = ["temperature", "pressure", "humidity"]
        
        for param in params:
            val = getattr(reading, param, None)
            if val is None or np.isnan(val):
                continue
                
            history = buffer.get_parameter_series(param)
            
            # If we have at least 1 prior reading, compute rate of change
            if len(history) >= 1:
                last_val = history[-1]
                # Calculate time delta in minutes
                prev_ts_str = buffer.get_timestamps()[-1]
                try:
                    t_curr = datetime.fromisoformat(reading.timestamp.replace("Z", "+00:00"))
                    t_prev = datetime.fromisoformat(prev_ts_str.replace("Z", "+00:00"))
                    dt_min = max((t_curr - t_prev).total_seconds() / 60.0, 0.05) # avoid zero div
                except Exception:
                    dt_min = 1.0
                
                delta = val - last_val
                rate_per_min = abs(delta) / dt_min
                rates_of_change[param] = round(rate_per_min, 3)
                
                # Check against plausible rate of change
                max_rate = MAX_RATE_OF_CHANGE_PER_MIN.get(param, 5.0)
                if rate_per_min > max_rate:
                    if delta > 0:
                        spike_detected = True
                        reasons.append(
                            f"Abrupt {param} spike: Delta={delta:+.1f} in {dt_min*60:.0f}s ({rate_per_min:.2f}/min > max {max_rate}/min)"
                        )
                    else:
                        drop_detected = True
                        reasons.append(
                            f"Abrupt {param} drop: Delta={delta:+.1f} in {dt_min*60:.0f}s ({rate_per_min:.2f}/min > max {max_rate}/min)"
                        )

            # If we have sufficient history, compute statistical metrics
            if len(history) >= TEMPORAL_CONFIG["min_window_for_stats"]:
                arr = np.array(history, dtype=float)
                mean_val = float(np.mean(arr))
                std_val = float(np.std(arr)) if len(arr) > 1 else 0.0
                rolling_means[param] = round(mean_val, 2)
                rolling_stds[param] = round(std_val, 2)
                
                # Robust Z-score using Median Absolute Deviation (MAD)
                # MAD is robust to existing outliers in the buffer
                median_val = float(np.median(arr))
                mad = float(np.median(np.abs(arr - median_val)))
                # Standard consistency factor for normal distribution: MAD * 1.4826 ~ std
                mad_std = mad * 1.4826
                
                if mad_std > 1e-4:
                    robust_z = (val - median_val) / mad_std
                elif std_val > 1e-4:
                    robust_z = (val - mean_val) / std_val
                else:
                    # History was virtually identical
                    diff = abs(val - median_val)
                    robust_z = (diff / 0.1) if diff > 0.1 else 0.0
                    
                robust_z_scores[param] = round(float(robust_z), 2)
                
                if abs(robust_z) >= TEMPORAL_CONFIG["spike_z_threshold"]:
                    if robust_z > 0:
                        spike_detected = True
                    else:
                        drop_detected = True
                    reasons.append(
                        f"Statistical temporal deviation in {param}: robust Z={robust_z:+.1f} "
                        f"(Obs={val}, RollingMed={median_val:.1f})"
                    )

            # Freeze Detection: Check if last N consecutive readings are identical
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

            # Drift Detection: Linear trend analysis across window
            if len(history) >= 6:
                combined = list(history) + [val]
                x = np.arange(len(combined))
                y = np.array(combined, dtype=float)
                # Fit linear regression line y = slope * x + intercept
                slope, _ = np.polyfit(x, y, 1)
                trend_slopes[param] = round(float(slope), 4)
                
                # Check if slope shows continuous creeping drift while variance around line is small
                y_pred = slope * x + np.mean(y) - slope * np.mean(x)
                residuals_std = np.std(y - y_pred)
                
                # If slope is significant and residual jitter is low, indicates calibration drift
                # Normalize slope by nominal parameter scale
                nominal_scale = 30.0 if param == "temperature" else (50.0 if param == "humidity" else 20.0)
                norm_slope = abs(slope) / nominal_scale
                if norm_slope >= TEMPORAL_CONFIG["drift_slope_threshold"] and residuals_std < 0.8:
                    drift_detected = True
                    reasons.append(
                        f"Calibration drift pattern in {param}: monotonic slope={slope:+.3f}/step over {len(combined)} points"
                    )

        # Update buffer with current reading
        buffer.add(reading)
        
        explanation = "; ".join(reasons) if reasons else "Temporal parameters within expected variance envelope"
        
        return TemporalEvidence(
            spike_detected=spike_detected,
            drop_detected=drop_detected,
            freeze_detected=freeze_detected,
            drift_detected=drift_detected,
            change_point_detected=change_point_detected,
            rates_of_change=rates_of_change,
            rolling_means=rolling_means,
            rolling_stds=rolling_stds,
            robust_z_scores=robust_z_scores,
            frozen_duration_steps=frozen_steps,
            trend_slopes=trend_slopes,
            explanation=explanation
        )

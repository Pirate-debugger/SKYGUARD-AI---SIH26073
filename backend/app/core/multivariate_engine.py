"""
Multivariate Consistency Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Analyzes joint relationships between Temperature (°C), Pressure (hPa), and Humidity (%):
- Thermodynamic relationships (Magnus-Tetens dewpoint consistency)
- Diurnal coupling (inverse T-RH relationship under clear/radiative conditions)
- Multivariate statistical distance (Mahalanobis / robust covariance)
- Inconsistent combinations (e.g. rapid isolated T jump without expected thermodynamic response)
"""

import math
from typing import Dict, List, Optional, Tuple
import numpy as np
from app.models.schemas import RawReading, MultivariateEvidence


class MultivariateConsistencyEngine:
    def __init__(self):
        # Baseline empirical mean and covariance for surface meteorological variables
        # Based on standard synoptic observations: T around ~28°C, P around ~1008 hPa, RH around ~65%
        self.mean_vector = np.array([28.0, 1008.0, 65.0])
        # Covariance matrix reflecting natural standard deviations (~8°C, ~12 hPa, ~20%)
        # and negative correlation between T and RH (-0.65)
        cov = np.array([
            [64.0,   -15.0,  -104.0],  # var(T), cov(T, P), cov(T, RH)
            [-15.0,  144.0,   25.0],   # cov(P, T), var(P), cov(P, RH)
            [-104.0,  25.0,  400.0]    # cov(RH, T), cov(RH, P), var(RH)
        ])
        self.cov_matrix = cov
        try:
            self.inv_cov = np.linalg.pinv(cov)
        except Exception:
            self.inv_cov = np.eye(3)

    def calculate_dewpoint(self, temp_c: float, rh_pct: float) -> Optional[float]:
        """Calculates dewpoint (°C) using Magnus-Tetens approximation."""
        if rh_pct <= 0 or rh_pct > 100 or temp_c < -60 or temp_c > 70:
            return None
        a = 17.27
        b = 237.7
        try:
            alpha = ((a * temp_c) / (b + temp_c)) + math.log(rh_pct / 100.0)
            dewpoint = (b * alpha) / (a - alpha)
            return round(dewpoint, 2)
        except Exception:
            return None

    def analyze(self, reading: RawReading, prev_reading: Optional[RawReading] = None) -> MultivariateEvidence:
        t = reading.temperature
        p = reading.pressure
        rh = reading.humidity

        discordant_params: List[str] = []
        reasons: List[str] = []
        is_consistent = True
        
        # Check if all 3 parameters are present
        if t is None or p is None or rh is None:
            return MultivariateEvidence(
                is_consistent=True,
                consistency_score=0.8,
                mahalanobis_distance=0.0,
                discordant_parameters=[],
                explanation="Partial parameters available; multivariate check deferred"
            )

        # 1. Thermodynamic Consistency: Dewpoint cannot exceed air temperature
        dewpoint = self.calculate_dewpoint(t, rh)
        if dewpoint is not None:
            if dewpoint > t + 0.5:  # 0.5°C tolerance for instrument calibration
                is_consistent = False
                discordant_params.extend(["temperature", "humidity"])
                reasons.append(
                    f"Thermodynamic violation: Computed Dewpoint ({dewpoint:.1f}°C) exceeds Air Temperature ({t:.1f}°C)"
                )

        # 2. Multivariate Dynamic Coupling check (if previous reading is available)
        # In natural atmosphere, a massive abrupt rise in temperature (e.g. > +15°C)
        # without any decrease in relative humidity or pressure adjustment indicates an isolated sensor fault.
        if prev_reading is not None and prev_reading.temperature is not None and prev_reading.humidity is not None:
            delta_t = t - prev_reading.temperature
            delta_rh = rh - prev_reading.humidity
            delta_p = (p - prev_reading.pressure) if prev_reading.pressure is not None else 0.0

            # Extreme isolated temperature spike: e.g. T jumps > 15°C while RH and P stay almost identical
            if delta_t > 15.0 and abs(delta_rh) < 2.0 and abs(delta_p) < 1.0:
                is_consistent = False
                discordant_params.append("temperature")
                reasons.append(
                    f"Multivariate decoupling: Temperature leaped by {delta_t:+.1f}°C while Humidity (Delta={delta_rh:+.1f}%) and Pressure (Delta={delta_p:+.1f} hPa) remained static"
                )
            
            # Massive isolated RH jump: e.g. RH jumps > 40% while temperature is > 40°C without rain/pressure drop
            if delta_rh > 40.0 and t > 40.0 and abs(delta_p) < 0.5:
                is_consistent = False
                discordant_params.append("humidity")
                reasons.append(
                    f"Suspicious humidity jump: RH surged {delta_rh:+.1f}% at extreme ambient temperature {t:.1f}°C without synoptic pressure change"
                )

        # 3. Multivariate Mahalanobis Distance
        obs_vec = np.array([t, p, rh])
        diff = obs_vec - self.mean_vector
        try:
            m_dist_sq = float(diff.T @ self.inv_cov @ diff)
            m_dist = math.sqrt(max(0.0, m_dist_sq))
        except Exception:
            m_dist = 0.0

        # Mahalanobis threshold for 3 degrees of freedom:
        # Chi-square critical value at p=0.005 is ~12.84 (distance ~3.58)
        # Outliers have distance > 4.5
        if m_dist > 4.5:
            is_consistent = False
            reasons.append(
                f"Statistical multivariate discordance: Mahalanobis distance = {m_dist:.2f} (Threshold 4.5)"
            )
            # Identify which component contributes most to the distance
            comp_contributions = np.abs(diff) / np.sqrt(np.diag(self.cov_matrix))
            top_param_idx = int(np.argmax(comp_contributions))
            param_names = ["temperature", "pressure", "humidity"]
            if param_names[top_param_idx] not in discordant_params:
                discordant_params.append(param_names[top_param_idx])

        # Compute continuous consistency score between 0.0 and 1.0
        # Mahalanobis of 0 gives 1.0, 5.5 gives ~0.5, >10 gives <0.1
        consistency_score = round(max(0.0, min(1.0, 1.0 / (1.0 + 0.15 * max(0.0, m_dist - 2.0)))), 3)
        if not is_consistent:
            consistency_score = min(consistency_score, 0.45)

        explanation = "; ".join(reasons) if reasons else "Temperature, Pressure, and Humidity exhibit mutually consistent physical coupling"

        return MultivariateEvidence(
            is_consistent=is_consistent,
            consistency_score=consistency_score,
            mahalanobis_distance=round(m_dist, 2),
            discordant_parameters=list(set(discordant_params)),
            explanation=explanation
        )

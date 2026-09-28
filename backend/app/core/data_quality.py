"""
Data Quality Engine for SkyGuard AI
SIH26073: Automatic Weather Station Anomaly Detection System

Validates:
- Missing values (None, NaN, nulls)
- Impossible physical ranges based on WMO ground station bounds
- Timestamp formats and validity
- Impossible instantaneous physical values
Does NOT silently repair raw data. Flags with VALID, INVALID, MISSING, or SUSPICIOUS.
"""

import math
from datetime import datetime
from typing import Optional, Tuple, List, Dict
from app.config import PHYSICAL_LIMITS
from app.models.schemas import DataQualityStatus, DataQualityResult, RawReading


class DataQualityEngine:
    def __init__(self):
        self.seen_timestamps: Dict[str, set] = {} # station_id -> set of seen timestamps

    def validate_reading(self, reading: RawReading) -> DataQualityResult:
        issues: List[str] = []
        flagged_params: List[str] = []
        is_invalid = False
        is_missing = False
        is_suspicious = False

        # 1. Timestamp validation
        try:
            # support ISO 8601 strings
            ts_str = reading.timestamp.replace("Z", "+00:00")
            parsed_ts = datetime.fromisoformat(ts_str)
        except Exception as e:
            issues.append(f"Malformed timestamp: '{reading.timestamp}' ({str(e)})")
            is_invalid = True

        # Check for duplicates if station has tracking
        if reading.station_id not in self.seen_timestamps:
            self.seen_timestamps[reading.station_id] = set()
        
        if reading.timestamp in self.seen_timestamps[reading.station_id]:
            issues.append(f"Duplicate timestamp received: {reading.timestamp}")
            is_suspicious = True
        else:
            self.seen_timestamps[reading.station_id].add(reading.timestamp)

        # 2. Check each core meteorological parameter
        # Parameter: Temperature
        temp_status, temp_issues = self._check_parameter(
            "temperature", reading.temperature, PHYSICAL_LIMITS["temperature"]
        )
        issues.extend(temp_issues)
        if temp_status == "INVALID":
            is_invalid = True
            flagged_params.append("temperature")
        elif temp_status == "MISSING":
            is_missing = True
            flagged_params.append("temperature")
        elif temp_status == "SUSPICIOUS":
            is_suspicious = True
            flagged_params.append("temperature")

        # Parameter: Pressure
        pres_status, pres_issues = self._check_parameter(
            "pressure", reading.pressure, PHYSICAL_LIMITS["pressure"]
        )
        issues.extend(pres_issues)
        if pres_status == "INVALID":
            is_invalid = True
            flagged_params.append("pressure")
        elif pres_status == "MISSING":
            is_missing = True
            flagged_params.append("pressure")
        elif pres_status == "SUSPICIOUS":
            is_suspicious = True
            flagged_params.append("pressure")

        # Parameter: Humidity
        hum_status, hum_issues = self._check_parameter(
            "humidity", reading.humidity, PHYSICAL_LIMITS["humidity"]
        )
        issues.extend(hum_issues)
        if hum_status == "INVALID":
            is_invalid = True
            flagged_params.append("humidity")
        elif hum_status == "MISSING":
            is_missing = True
            flagged_params.append("humidity")
        elif hum_status == "SUSPICIOUS":
            is_suspicious = True
            flagged_params.append("humidity")

        # Final quality categorization
        if is_invalid:
            status = DataQualityStatus.INVALID
        elif is_missing:
            status = DataQualityStatus.MISSING
        elif is_suspicious:
            status = DataQualityStatus.SUSPICIOUS
        else:
            status = DataQualityStatus.VALID

        return DataQualityResult(
            status=status,
            flagged_parameters=flagged_params,
            issues=issues,
            is_valid=(status == DataQualityStatus.VALID)
        )

    def _check_parameter(
        self, param_name: str, value: Optional[float], limits: dict
    ) -> Tuple[str, List[str]]:
        issues = []
        if value is None or (isinstance(value, float) and math.isnan(value)):
            issues.append(f"Missing {param_name} reading (null/NaN)")
            return "MISSING", issues

        if not isinstance(value, (int, float)):
            issues.append(f"Invalid non-numeric type for {param_name}: {type(value)}")
            return "INVALID", issues

        # Physical limit checks
        min_val, max_val = limits["min"], limits["max"]
        if value < min_val or value > max_val:
            issues.append(
                f"Physically impossible {param_name}: {value}{limits['unit']} "
                f"(Valid WMO envelope: [{min_val}, {max_val}]{limits['unit']})"
            )
            return "INVALID", issues

        # Specific suspicious edge cases (e.g. exactly 0.00% humidity or exactly 100.000% continuously)
        if param_name == "humidity" and (value <= 0.0 or value >= 100.0):
            # 0% is meteorologically almost impossible on surface stations, 100% can happen in fog but is notable
            if value <= 0.0:
                issues.append("Suspicious dry limit: Humidity recorded as exactly 0.0%")
                return "SUSPICIOUS", issues

        return "VALID", issues

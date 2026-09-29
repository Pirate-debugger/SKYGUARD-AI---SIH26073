/**
 * Geodetic & Haversine Utilities for SkyGuard AI
 * SIH26073: Automatic Weather Station Anomaly Detection System
 * 
 * Enforces identical great-circle Haversine geodetic distance calculations
 * across frontend and backend (WGS84 Earth radius = 6371.0 km).
 */

const EARTH_RADIUS_KM = 6371.0;

/**
 * Calculates great-circle Haversine distance between two latitude/longitude points in kilometers.
 * Formula:
 *   a = sin²(Δφ/2) + cos(φ1) * cos(φ2) * sin²(Δλ/2)
 *   c = 2 * atan2(√a, √(1-a))
 *   d = R * c
 */
export function haversineDistanceKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180.0;

  const phi1 = toRad(lat1);
  const phi2 = toRad(lat2);
  const deltaPhi = toRad(lat2 - lat1);
  const deltaLambda = toRad(lon2 - lon1);

  const sinHalfDeltaPhi = Math.sin(deltaPhi / 2.0);
  const sinHalfDeltaLambda = Math.sin(deltaLambda / 2.0);

  const a =
    sinHalfDeltaPhi * sinHalfDeltaPhi +
    Math.cos(phi1) * Math.cos(phi2) * sinHalfDeltaLambda * sinHalfDeltaLambda;

  const c = 2.0 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1.0 - a)));

  return EARTH_RADIUS_KM * c;
}

/**
 * Computes bounding box enclosing all stations with proportional padding.
 */
export function calculateGeoBounds(
  points: Array<{ latitude: number; longitude: number }>,
  paddingRatio: number = 0.12
) {
  if (points.length === 0) {
    return {
      minLat: 26.5,
      maxLat: 31.2,
      minLon: 75.3,
      maxLon: 80.0
    };
  }

  const lats = points.map(p => p.latitude);
  const lons = points.map(p => p.longitude);

  const rawMinLat = Math.min(...lats);
  const rawMaxLat = Math.max(...lats);
  const rawMinLon = Math.min(...lons);
  const rawMaxLon = Math.max(...lons);

  const latSpan = Math.max(rawMaxLat - rawMinLat, 0.5);
  const lonSpan = Math.max(rawMaxLon - rawMinLon, 0.5);

  const latPadding = Math.max(latSpan * paddingRatio, 0.35);
  const lonPadding = Math.max(lonSpan * paddingRatio, 0.45);

  return {
    minLat: rawMinLat - latPadding,
    maxLat: rawMaxLat + latPadding,
    minLon: rawMinLon - lonPadding,
    maxLon: rawMaxLon + lonPadding
  };
}

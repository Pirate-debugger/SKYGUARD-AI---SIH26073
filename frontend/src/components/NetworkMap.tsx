import React, { useState } from 'react';
import { StationData } from '../types';
import { MapPin, Navigation, Compass, Layers } from 'lucide-react';

interface NetworkMapProps {
  stations: StationData[];
  onSelectStation: (stationId: string) => void;
}

export const NetworkMap: React.FC<NetworkMapProps> = ({ stations, onSelectStation }) => {
  const [hoveredStation, setHoveredStation] = useState<StationData | null>(null);

  // Normalize lat/lon bounds for SVG viewbox
  // Network spans: Lat 26.9 to 30.8, Lon 75.7 to 79.5
  const minLat = 26.8, maxLat = 31.0;
  const minLon = 75.5, maxLon = 79.8;
  const width = 800;
  const height = 450;

  const project = (lat: number, lon: number) => {
    const x = ((lon - minLon) / (maxLon - minLon)) * (width - 120) + 60;
    // Invert Y axis for latitude
    const y = ((maxLat - lat) / (maxLat - minLat)) * (height - 100) + 50;
    return { x, y };
  };

  const getStatusColor = (st: StationData) => {
    const reading = st.latest_reading;
    if (reading) {
      if (reading.decision === 'WEATHER_EVENT') return 'var(--status-weather-event)';
      if (reading.decision === 'SENSOR_ANOMALY') return 'var(--status-critical)';
      if (reading.decision === 'SENSOR_DEGRADATION') return 'var(--status-degraded)';
      if (reading.decision === 'COMMUNICATION_ERROR') return 'var(--status-offline)';
    }
    const status = st.health?.status || st.metadata.status;
    switch (status) {
      case 'HEALTHY': return 'var(--status-healthy)';
      case 'WATCH': return 'var(--status-watch)';
      case 'DEGRADED': return 'var(--status-degraded)';
      case 'CRITICAL': return 'var(--status-critical)';
      case 'OFFLINE': return 'var(--status-offline)';
      default: return 'var(--accent-cyan)';
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Compass style={{ width: '18px', height: '18px', color: 'var(--accent-cyan)' }} />
          <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>
            REGIONAL AWS GEOSPATIAL MESH
          </h2>
          <span className="badge" style={{ background: 'rgba(255, 255, 255, 0.05)', color: 'var(--text-muted)' }}>
            12 Stations &bull; 150km Radius
          </span>
        </div>

        {/* Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11px', color: 'var(--text-muted)' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--status-healthy)' }} /> Healthy
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--status-watch)' }} /> Watch
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--status-degraded)' }} /> Degraded
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--status-critical)' }} /> Anomaly
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--status-weather-event)' }} /> Weather Event
          </span>
        </div>
      </div>

      {/* SVG Canvas Map */}
      <div style={{ flex: 1, position: 'relative', background: 'radial-gradient(ellipse at center, rgba(14, 25, 45, 0.6) 0%, rgba(8, 12, 20, 0.95) 100%)', borderRadius: '10px', overflow: 'hidden', border: '1px solid var(--border-subtle)' }}>
        
        {/* Subtle Map Grid Lines */}
        <svg width="100%" height="100%" viewBox={`0 0 ${width} ${height}`} style={{ position: 'absolute', inset: 0 }}>
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255, 255, 255, 0.03)" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Spatial Neighborhood Mesh Interconnections */}
          {stations.map((st, i) => {
            const pos1 = project(st.metadata.latitude, st.metadata.longitude);
            return stations.slice(i + 1).map((st2) => {
              // Connect if distance is within ~150km (roughly < 1.3 degrees)
              const dLat = st.metadata.latitude - st2.metadata.latitude;
              const dLon = st.metadata.longitude - st2.metadata.longitude;
              const degDist = Math.sqrt(dLat * dLat + dLon * dLon);
              if (degDist < 1.4) {
                const pos2 = project(st2.metadata.latitude, st2.metadata.longitude);
                return (
                  <line
                    key={`${st.metadata.station_id}-${st2.metadata.station_id}`}
                    x1={pos1.x}
                    y1={pos1.y}
                    x2={pos2.x}
                    y2={pos2.y}
                    stroke="rgba(56, 189, 248, 0.12)"
                    strokeWidth="1.5"
                    strokeDasharray="3 3"
                  />
                );
              }
              return null;
            });
          })}

          {/* Station Nodes */}
          {stations.map((st) => {
            const { x, y } = project(st.metadata.latitude, st.metadata.longitude);
            const color = getStatusColor(st);
            const isAlert = st.latest_reading?.decision === 'SENSOR_ANOMALY';
            const isWeather = st.latest_reading?.decision === 'WEATHER_EVENT';

            return (
              <g
                key={st.metadata.station_id}
                style={{ cursor: 'pointer' }}
                onClick={() => onSelectStation(st.metadata.station_id)}
                onMouseEnter={() => setHoveredStation(st)}
                onMouseLeave={() => setHoveredStation(null)}
              >
                {/* Pulsing ring for alerts/weather */}
                {(isAlert || isWeather) && (
                  <circle
                    cx={x}
                    cy={y}
                    r={18}
                    fill="none"
                    stroke={color}
                    strokeWidth="2"
                    opacity="0.8"
                    className="alert-pulse"
                  />
                )}

                {/* Outer halo */}
                <circle
                  cx={x}
                  cy={y}
                  r={10}
                  fill={color}
                  fillOpacity="0.2"
                  stroke={color}
                  strokeWidth="1.5"
                />

                {/* Core node */}
                <circle
                  cx={x}
                  cy={y}
                  r={5}
                  fill={color}
                />

                {/* Station Label */}
                <text
                  x={x}
                  y={y - 12}
                  textAnchor="middle"
                  fill="#f1f5f9"
                  fontSize="10"
                  fontFamily="JetBrains Mono"
                  fontWeight="600"
                  style={{ textShadow: '0 1px 4px rgba(0,0,0,0.8)' }}
                >
                  {st.metadata.station_id}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Hover Tooltip Card */}
        {hoveredStation && (
          <div
            className="glass-panel"
            style={{
              position: 'absolute',
              bottom: '16px',
              left: '16px',
              padding: '12px 16px',
              pointerEvents: 'none',
              minWidth: '240px',
              border: '1px solid var(--border-glow)',
              boxShadow: '0 8px 25px rgba(0,0,0,0.6)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#fff' }}>
                {hoveredStation.metadata.station_id} &bull; {hoveredStation.metadata.station_name}
              </span>
              <span className={`badge badge-${hoveredStation.health?.status.toLowerCase() || 'healthy'}`}>
                {hoveredStation.health?.status || 'HEALTHY'}
              </span>
            </div>

            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px' }}>
              {hoveredStation.metadata.region} &bull; {hoveredStation.metadata.elevation_m}m ASL
            </div>

            {hoveredStation.latest_reading ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', fontSize: '11px' }} className="mono">
                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block' }}>TEMP</span>
                  <span style={{ fontWeight: 700, color: '#fff' }}>{hoveredStation.latest_reading.temperature ?? 'N/A'}°C</span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block' }}>PRES</span>
                  <span style={{ fontWeight: 700, color: '#fff' }}>{hoveredStation.latest_reading.pressure ?? 'N/A'} hPa</span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block' }}>HUM</span>
                  <span style={{ fontWeight: 700, color: '#fff' }}>{hoveredStation.latest_reading.humidity ?? 'N/A'}%</span>
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Awaiting telemetry stream...</div>
            )}

            <div style={{ fontSize: '10px', color: 'var(--accent-cyan)', marginTop: '8px', textAlign: 'right' }}>
              Click node to open inspector &rarr;
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

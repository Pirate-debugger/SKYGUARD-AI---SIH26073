import React, { useState } from 'react';
import { StationData } from '../types';
import { Search, Filter, Activity, ChevronRight, AlertTriangle, CheckCircle, Wrench } from 'lucide-react';

interface StationTableProps {
  stations: StationData[];
  onSelectStation: (stationId: string) => void;
}

export const StationTable: React.FC<StationTableProps> = ({ stations, onSelectStation }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('ALL');

  const filteredStations = stations.filter(st => {
    const matchesSearch = 
      st.metadata.station_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      st.metadata.station_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      st.metadata.region.toLowerCase().includes(searchTerm.toLowerCase());

    const status = st.health?.status || st.metadata.status;
    const matchesStatus = statusFilter === 'ALL' || status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'HEALTHY':
        return <span className="badge badge-healthy">HEALTHY</span>;
      case 'WATCH':
        return <span className="badge badge-watch">WATCH</span>;
      case 'DEGRADED':
        return <span className="badge badge-degraded">DEGRADED</span>;
      case 'CRITICAL':
        return <span className="badge badge-critical">CRITICAL</span>;
      case 'OFFLINE':
        return <span className="badge badge-offline">OFFLINE</span>;
      default:
        return <span className="badge">{status}</span>;
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '20px' }}>
      
      {/* Table Header & Controls */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '14px', marginBottom: '16px' }}>
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>
            AWS SENSOR FLEET TELEMETRY
          </h2>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Real-time multi-sensor status and degradation scores across monitored network
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Search Box */}
          <div style={{ position: 'relative' }}>
            <Search style={{ width: '14px', height: '14px', position: 'absolute', left: '10px', top: '10px', color: 'var(--text-dim)' }} />
            <input
              type="text"
              placeholder="Search station or region..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{
                background: 'var(--bg-tertiary)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '7px 12px 7px 32px',
                fontSize: '12px',
                outline: 'none',
                width: '210px'
              }}
            />
          </div>

          {/* Filter Dropdown */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{
              background: 'var(--bg-tertiary)',
              color: 'var(--text-main)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '7px 10px',
              fontSize: '12px',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            <option value="ALL">All Statuses</option>
            <option value="HEALTHY">Healthy</option>
            <option value="WATCH">Watch</option>
            <option value="DEGRADED">Degraded</option>
            <option value="CRITICAL">Critical</option>
            <option value="OFFLINE">Offline</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-dim)' }}>
              <th style={{ padding: '10px 12px', fontWeight: 600 }}>STATION ID</th>
              <th style={{ padding: '10px 12px', fontWeight: 600 }}>LOCATION / REGION</th>
              <th style={{ padding: '10px 12px', fontWeight: 600 }}>TEMPERATURE</th>
              <th style={{ padding: '10px 12px', fontWeight: 600 }}>PRESSURE</th>
              <th style={{ padding: '10px 12px', fontWeight: 600 }}>HUMIDITY</th>
              <th style={{ padding: '10px 12px', fontWeight: 600 }}>HEALTH SCORE</th>
              <th style={{ padding: '10px 12px', fontWeight: 600 }}>STATUS</th>
              <th style={{ padding: '10px 12px', fontWeight: 600 }}>MAINTENANCE ACTION</th>
              <th style={{ padding: '10px 12px', fontWeight: 600, textAlign: 'right' }}>ACTION</th>
            </tr>
          </thead>
          <tbody>
            {filteredStations.map((st) => {
              const r = st.latest_reading;
              const h = st.health;
              const score = h ? h.health_score : 100;
              const hasAnomaly = r && r.decision === 'SENSOR_ANOMALY';
              const isWeather = r && r.decision === 'WEATHER_EVENT';

              return (
                <tr
                  key={st.metadata.station_id}
                  onClick={() => onSelectStation(st.metadata.station_id)}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    cursor: 'pointer',
                    transition: 'background 0.15s ease',
                    background: hasAnomaly ? 'rgba(239, 68, 68, 0.06)' : (isWeather ? 'rgba(139, 92, 246, 0.06)' : 'transparent')
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bg-card-hover)'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = hasAnomaly ? 'rgba(239, 68, 68, 0.06)' : (isWeather ? 'rgba(139, 92, 246, 0.06)' : 'transparent')}
                >
                  {/* Station ID */}
                  <td style={{ padding: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span className="mono" style={{ fontWeight: 700, color: 'var(--accent-cyan)' }}>
                        {st.metadata.station_id}
                      </span>
                    </div>
                  </td>

                  {/* Location & Region */}
                  <td style={{ padding: '12px' }}>
                    <div style={{ fontWeight: 600, color: '#fff' }}>{st.metadata.station_name}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                      {st.metadata.region} &bull; {st.metadata.elevation_m}m
                    </div>
                  </td>

                  {/* Temperature */}
                  <td style={{ padding: '12px' }} className="mono">
                    {r && r.temperature !== null ? (
                      <div>
                        <span style={{ fontSize: '13px', fontWeight: 700, color: '#fff' }}>
                          {r.temperature.toFixed(1)}°C
                        </span>
                        {r.spatial_evidence?.relative_deviations?.temperature !== undefined && (
                          <span style={{
                            fontSize: '10px',
                            marginLeft: '6px',
                            color: Math.abs(r.spatial_evidence.relative_deviations.temperature) > 3.0 ? 'var(--status-critical)' : 'var(--text-dim)'
                          }}>
                            {r.spatial_evidence.relative_deviations.temperature > 0 ? '+' : ''}
                            {r.spatial_evidence.relative_deviations.temperature.toFixed(1)}
                          </span>
                        )}
                      </div>
                    ) : (
                      <span style={{ color: 'var(--text-dim)' }}>N/A</span>
                    )}
                  </td>

                  {/* Pressure */}
                  <td style={{ padding: '12px' }} className="mono">
                    {r && r.pressure !== null ? (
                      <span style={{ color: '#e2e8f0' }}>{r.pressure.toFixed(1)} hPa</span>
                    ) : (
                      <span style={{ color: 'var(--text-dim)' }}>N/A</span>
                    )}
                  </td>

                  {/* Humidity */}
                  <td style={{ padding: '12px' }} className="mono">
                    {r && r.humidity !== null ? (
                      <span style={{ color: '#e2e8f0' }}>{r.humidity.toFixed(0)}%</span>
                    ) : (
                      <span style={{ color: 'var(--text-dim)' }}>N/A</span>
                    )}
                  </td>

                  {/* Health Score Gauge Bar */}
                  <td style={{ padding: '12px' }}>
                    <div style={{ width: '110px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginBottom: '3px' }}>
                        <span className="mono" style={{ fontWeight: 700 }}>{score.toFixed(0)}%</span>
                        <span style={{ fontSize: '10px', color: 'var(--text-dim)' }}>{h?.degradation_signal || 'LOW'}</span>
                      </div>
                      <div style={{ height: '4px', background: 'var(--bg-tertiary)', borderRadius: '2px', overflow: 'hidden' }}>
                        <div
                          style={{
                            height: '100%',
                            width: `${score}%`,
                            background: score > 85 ? 'var(--status-healthy)' : (score > 60 ? 'var(--status-watch)' : 'var(--status-critical)'),
                            borderRadius: '2px',
                            transition: 'width 0.4s ease'
                          }}
                        />
                      </div>
                    </div>
                  </td>

                  {/* Status Badge */}
                  <td style={{ padding: '12px' }}>
                    {getStatusBadge(h ? h.status : st.metadata.status)}
                  </td>

                  {/* Maintenance Recommendation */}
                  <td style={{ padding: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '11px' }}>
                      <Wrench style={{ width: '12px', height: '12px', color: 'var(--text-dim)' }} />
                      <span style={{ color: h?.maintenance_recommendation !== 'NO_ACTION' ? 'var(--status-watch)' : 'var(--text-dim)' }}>
                        {h?.maintenance_recommendation || 'NO_ACTION'}
                      </span>
                    </div>
                  </td>

                  {/* Action */}
                  <td style={{ padding: '12px', textAlign: 'right' }}>
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '4px 8px', fontSize: '11px' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelectStation(st.metadata.station_id);
                      }}
                    >
                      Inspect <ChevronRight style={{ width: '12px', height: '12px' }} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

    </div>
  );
};

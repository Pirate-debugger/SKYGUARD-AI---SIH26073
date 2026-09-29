import React from 'react';
import { StationData, ProcessedReading } from '../types';
import { X, Activity, Wrench, Shield, Thermometer, Gauge, Droplets, MapPin, AlertTriangle, CheckCircle, RefreshCw } from 'lucide-react';

interface StationDetailModalProps {
  station: StationData | null;
  historyReadings: ProcessedReading[];
  neighbors: Array<{ station_id: string; distance_km: number }>;
  onClose: () => void;
}

export const StationDetailModal: React.FC<StationDetailModalProps> = ({
  station,
  historyReadings,
  neighbors,
  onClose
}) => {
  if (!station) return null;

  const m = station.metadata;
  const h = station.health;
  const r = station.latest_reading;
  const healthScore = h ? h.health_score : 100;

  // Simple SVG Line Chart generator
  const renderSparkline = (
    data: (number | null)[],
    color: string,
    unit: string,
    minVal?: number,
    maxVal?: number
  ) => {
    const valid = data.filter((v): v is number => v !== null && !isNaN(v));
    if (valid.length < 2) return <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>Insufficient historical buffer</div>;

    const min = minVal ?? Math.min(...valid) - 1;
    const max = maxVal ?? Math.max(...valid) + 1;
    const range = max - min || 1;
    const w = 240;
    const h = 50;

    const points = valid.map((v, i) => {
      const x = (i / (valid.length - 1)) * w;
      const y = h - ((v - min) / range) * (h - 10) - 5;
      return `${x},${y}`;
    }).join(' ');

    return (
      <div>
        <svg width="100%" height={h} viewBox={`0 0 ${w} ${h}`} style={{ overflow: 'visible' }}>
          <polyline
            fill="none"
            stroke={color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={points}
          />
          {valid.length > 0 && (
            <circle
              cx={w}
              cy={h - ((valid[valid.length - 1] - min) / range) * (h - 10) - 5}
              r="3.5"
              fill={color}
            />
          )}
        </svg>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: 'var(--text-dim)', marginTop: '4px' }} className="mono">
          <span>Min: {Math.min(...valid).toFixed(1)}{unit}</span>
          <span>Latest: {valid[valid.length - 1].toFixed(1)}{unit}</span>
          <span>Max: {Math.max(...valid).toFixed(1)}{unit}</span>
        </div>
      </div>
    );
  };

  const tempHistory = historyReadings.map(d => d.temperature);
  const presHistory = historyReadings.map(d => d.pressure);
  const humHistory = historyReadings.map(d => d.humidity);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '960px' }}>
        
        {/* Modal Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              background: 'rgba(56, 189, 248, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--accent-cyan)'
            }}>
              <MapPin style={{ width: '22px', height: '22px' }} />
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#fff' }}>
                  {m.station_name}
                </h2>
                <span className="badge mono" style={{ background: 'rgba(56, 189, 248, 0.2)', color: 'var(--accent-cyan)' }}>
                  {m.station_id}
                </span>
                <span className={`badge badge-${h?.status.toLowerCase() || 'healthy'}`}>
                  {h?.status || 'HEALTHY'}
                </span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                {m.region} &bull; Lat: {m.latitude.toFixed(4)}°, Lon: {m.longitude.toFixed(4)}° &bull; Elevation: {m.elevation_m}m ASL
              </div>
            </div>
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '6px'
            }}
          >
            <X style={{ width: '20px', height: '20px' }} />
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Top Row: Current Telemetry & Sensor Health */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
            
            {/* Live Parameter Cards */}
            <div className="glass-panel" style={{ padding: '16px' }}>
              <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Activity style={{ width: '15px', height: '15px', color: 'var(--accent-cyan)' }} />
                LIVE PARAMETER TELEMETRY
              </h3>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }} className="mono">
                {/* Temp */}
                <div style={{ background: 'var(--bg-tertiary)', padding: '10px', borderRadius: '8px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Thermometer style={{ width: '12px', height: '12px', color: '#f87171' }} /> TEMP
                  </div>
                  <div style={{ fontSize: '18px', fontWeight: 800, color: '#fff', marginTop: '4px' }}>
                    {r?.temperature !== null && r?.temperature !== undefined ? `${r.temperature.toFixed(1)}°C` : 'N/A'}
                  </div>
                  {r?.spatial_evidence?.relative_deviations?.temperature !== undefined && (
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      Dev: {r.spatial_evidence.relative_deviations.temperature > 0 ? '+' : ''}
                      {r.spatial_evidence.relative_deviations.temperature.toFixed(1)}°C
                    </div>
                  )}
                </div>

                {/* Pressure */}
                <div style={{ background: 'var(--bg-tertiary)', padding: '10px', borderRadius: '8px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Gauge style={{ width: '12px', height: '12px', color: '#38bdf8' }} /> PRES
                  </div>
                  <div style={{ fontSize: '18px', fontWeight: 800, color: '#fff', marginTop: '4px' }}>
                    {r?.pressure !== null && r?.pressure !== undefined ? `${r.pressure.toFixed(1)}` : 'N/A'}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>hPa</div>
                </div>

                {/* Humidity */}
                <div style={{ background: 'var(--bg-tertiary)', padding: '10px', borderRadius: '8px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <Droplets style={{ width: '12px', height: '12px', color: '#34d399' }} /> HUM
                  </div>
                  <div style={{ fontSize: '18px', fontWeight: 800, color: '#fff', marginTop: '4px' }}>
                    {r?.humidity !== null && r?.humidity !== undefined ? `${r.humidity.toFixed(0)}%` : 'N/A'}
                  </div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '2px' }}>RH</div>
                </div>
              </div>

              {/* Status explanation */}
              {r && (
                <div style={{ marginTop: '12px', fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.4 }}>
                  <strong style={{ color: '#fff' }}>Latest Finding: </strong>
                  {r.explanation}
                </div>
              )}
            </div>

            {/* Sensor Health & Degradation Tracker */}
            <div className="glass-panel" style={{ padding: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Shield style={{ width: '15px', height: '15px', color: 'var(--status-healthy)' }} />
                  SENSOR HEALTH & DEGRADATION
                </h3>
                <span className="mono" style={{ fontSize: '18px', fontWeight: 800, color: healthScore > 80 ? 'var(--status-healthy)' : 'var(--status-watch)' }}>
                  {healthScore.toFixed(0)} / 100
                </span>
              </div>

              {/* Metric bar */}
              <div style={{ height: '6px', background: 'var(--bg-tertiary)', borderRadius: '3px', overflow: 'hidden', marginBottom: '14px' }}>
                <div style={{
                  height: '100%',
                  width: `${healthScore}%`,
                  background: healthScore > 85 ? 'var(--status-healthy)' : (healthScore > 60 ? 'var(--status-watch)' : 'var(--status-critical)'),
                  transition: 'width 0.4s ease'
                }} />
              </div>

              {/* Degradation stats */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', fontSize: '11px', textAlign: 'center' }} className="mono">
                <div style={{ background: 'var(--bg-tertiary)', padding: '6px', borderRadius: '6px' }}>
                  <div style={{ color: 'var(--text-dim)' }}>SPIKES</div>
                  <div style={{ fontWeight: 700, color: h?.recent_spikes_count ? 'var(--status-critical)' : '#fff' }}>
                    {h?.recent_spikes_count || 0}
                  </div>
                </div>
                <div style={{ background: 'var(--bg-tertiary)', padding: '6px', borderRadius: '6px' }}>
                  <div style={{ color: 'var(--text-dim)' }}>FREEZES</div>
                  <div style={{ fontWeight: 700, color: h?.recent_frozen_intervals ? 'var(--status-watch)' : '#fff' }}>
                    {h?.recent_frozen_intervals || 0}
                  </div>
                </div>
                <div style={{ background: 'var(--bg-tertiary)', padding: '6px', borderRadius: '6px' }}>
                  <div style={{ color: 'var(--text-dim)' }}>DROPS</div>
                  <div style={{ fontWeight: 700, color: h?.recent_comm_gaps ? 'var(--status-offline)' : '#fff' }}>
                    {h?.recent_comm_gaps || 0}
                  </div>
                </div>
                <div style={{ background: 'var(--bg-tertiary)', padding: '6px', borderRadius: '6px' }}>
                  <div style={{ color: 'var(--text-dim)' }}>DRIFT</div>
                  <div style={{ fontWeight: 700, color: h?.drift_trend_detected ? 'var(--status-degraded)' : '#fff' }}>
                    {h?.drift_trend_detected ? 'YES' : 'NO'}
                  </div>
                </div>
              </div>

              {/* Maintenance recommendation */}
              <div style={{ marginTop: '12px', padding: '10px', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--status-watch)', fontWeight: 700 }}>
                  <Wrench style={{ width: '13px', height: '13px' }} />
                  RECOMMENDED ACTION: {h?.maintenance_recommendation || 'NO_ACTION'}
                </div>
                <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                  {h?.summary_text || 'Sensor operating normally without significant physical wear signatures.'}
                </p>
              </div>

            </div>

          </div>

          {/* Historical Parameter Sparkline Charts */}
          <div className="glass-panel" style={{ padding: '16px' }}>
            <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '14px' }}>
              TIME-SERIES PARAMETER EVOLUTION (Last {tempHistory.length} timesteps)
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '16px' }}>
              <div>
                <div style={{ fontSize: '11px', fontWeight: 600, color: '#f87171', marginBottom: '6px' }}>
                  Temperature (°C) Trend
                </div>
                {renderSparkline(tempHistory, '#f87171', '°C')}
              </div>
              <div>
                <div style={{ fontSize: '11px', fontWeight: 600, color: '#38bdf8', marginBottom: '6px' }}>
                  Atmospheric Pressure (hPa) Trend
                </div>
                {renderSparkline(presHistory, '#38bdf8', ' hPa')}
              </div>
              <div>
                <div style={{ fontSize: '11px', fontWeight: 600, color: '#34d399', marginBottom: '6px' }}>
                  Relative Humidity (%) Trend
                </div>
                {renderSparkline(humHistory, '#34d399', '%', 0, 100)}
              </div>
            </div>
          </div>

          {/* Nearby Station Spatial Neighborhood Comparison & Evidence */}
          <div className="glass-panel" style={{ padding: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
              <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)' }}>
                SPATIAL NEIGHBORHOOD CROSS-VALIDATION
              </h3>
              <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.1)', color: 'var(--accent-cyan)', fontSize: '11px' }}>
                150 km Analysis Radius
              </span>
            </div>

            {/* Spatial Evidence Summary Grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
              gap: '8px',
              padding: '10px',
              background: 'rgba(0, 0, 0, 0.25)',
              borderRadius: '8px',
              border: '1px solid var(--border-subtle)',
              marginBottom: '14px',
              fontSize: '11px'
            }} className="mono">
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '10px' }}>NEIGHBORS</span>
                <span style={{ fontWeight: 700, color: '#fff' }}>{r?.spatial_evidence?.neighbor_count ?? neighbors.length}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '10px' }}>VALID NEIGHBORS</span>
                <span style={{ fontWeight: 700, color: '#fff' }}>{r?.spatial_evidence?.valid_neighbor_count ?? neighbors.length}</span>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '10px' }}>CORROBORATION</span>
                <span style={{ fontWeight: 700, color: (r?.spatial_evidence?.corroborating_stations_count || 0) > 0 ? '#c084fc' : '#fff' }}>
                  {r?.spatial_evidence?.corroborating_stations_count ?? 0} / {r?.spatial_evidence?.valid_neighbor_count ?? neighbors.length}
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '10px' }}>AGREEMENT RATIO</span>
                <span style={{ fontWeight: 700, color: '#fff' }}>
                  {(r?.spatial_evidence?.agreement_ratio ?? 0.0).toFixed(2)}
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '10px' }}>DIRECTIONAL</span>
                <span style={{ fontWeight: 700, color: r?.spatial_evidence?.directional_agreement ? '#c084fc' : '#94a3b8' }}>
                  {r?.spatial_evidence?.directional_agreement ? 'YES' : 'NO'}
                </span>
              </div>
              <div>
                <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '10px' }}>REGIONAL EVENT</span>
                <span style={{ fontWeight: 700, color: r?.spatial_evidence?.regional_event_detected ? '#c084fc' : '#94a3b8' }}>
                  {r?.spatial_evidence?.regional_event_detected ? 'CONFIRMED' : 'NO'}
                </span>
              </div>
            </div>

            {neighbors.length === 0 ? (
              <div style={{
                padding: '16px',
                borderRadius: '8px',
                background: 'rgba(245, 158, 11, 0.06)',
                border: '1px solid rgba(245, 158, 11, 0.25)',
                color: '#f59e0b'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, fontSize: '12px' }}>
                  <AlertTriangle style={{ width: '16px', height: '16px' }} />
                  NO VALID NEIGHBORS WITHIN 150 KM RADIUS
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px', lineHeight: 1.5 }}>
                  <strong>SPATIAL ANALYSIS: INSUFFICIENT SPATIAL EVIDENCE</strong>
                  <br />
                  This station is geographically isolated (&gt;150 km from closest operational AWS).
                  No artificial edges are drawn. Observations cannot be spatially corroborated;
                  quality control relies deterministically on temporal persistence, data quality limits, and multivariate thermodynamic coupling.
                </div>
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', fontSize: '11px', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ color: 'var(--text-dim)', borderBottom: '1px solid var(--border-subtle)', textAlign: 'left' }}>
                      <th style={{ padding: '6px 8px' }}>NEIGHBOR STATION</th>
                      <th style={{ padding: '6px 8px' }}>DISTANCE</th>
                      <th style={{ padding: '6px 8px' }}>MEDIAN TEMP</th>
                      <th style={{ padding: '6px 8px' }}>RELATIVE DEV</th>
                      <th style={{ padding: '6px 8px' }}>SPATIAL CONSENSUS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {neighbors.map((nb) => {
                      const dev = r?.spatial_evidence?.relative_deviations?.temperature;
                      return (
                        <tr key={nb.station_id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                          <td className="mono" style={{ padding: '8px', fontWeight: 600, color: '#fff' }}>
                            {nb.station_id}
                          </td>
                          <td style={{ padding: '8px' }} className="mono">
                            {nb.distance_km} km
                          </td>
                          <td style={{ padding: '8px' }} className="mono">
                            {r?.spatial_evidence?.neighbor_medians?.temperature?.toFixed(1) ?? 'N/A'}°C
                          </td>
                          <td style={{ padding: '8px' }} className="mono">
                            {dev !== undefined ? `${dev > 0 ? '+' : ''}${dev.toFixed(1)}°C` : 'N/A'}
                          </td>
                          <td style={{ padding: '8px' }}>
                            {r?.spatial_evidence?.is_consistent ? (
                              <span style={{ color: 'var(--status-healthy)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                <CheckCircle style={{ width: '12px', height: '12px' }} /> Consistent
                              </span>
                            ) : (
                              <span style={{ color: 'var(--status-critical)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                <AlertTriangle style={{ width: '12px', height: '12px' }} /> Isolated Outlier
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Optional Imputed / Corrected Values */}
          {r?.imputed_values && Object.keys(r.imputed_values).length > 0 && (
            <div className="glass-panel" style={{ padding: '16px', borderLeft: '3px solid var(--accent-cyan)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                <RefreshCw style={{ width: '16px', height: '16px', color: 'var(--accent-cyan)' }} />
                <h3 style={{ fontSize: '13px', fontWeight: 700, color: '#fff' }}>
                  ESTIMATED / IMPUTED VALUE CANDIDATES (Non-Destructive)
                </h3>
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '10px' }}>
                Estimated replacement candidates calculated via spatial inverse distance weighting and persistence. Raw observations are preserved intact.
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
                {Object.entries(r.imputed_values).map(([param, imp]) => (
                  <div key={param} style={{ background: 'var(--bg-tertiary)', padding: '10px', borderRadius: '8px' }} className="mono">
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase' }}>{param}</div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '4px' }}>
                      <span style={{ textDecoration: 'line-through', color: 'var(--status-critical)', fontSize: '13px' }}>
                        {imp.original_value !== null ? `${imp.original_value}°` : 'None'}
                      </span>
                      <span style={{ color: 'var(--status-healthy)', fontSize: '16px', fontWeight: 800 }}>
                        &rarr; {imp.estimated_value}°
                      </span>
                    </div>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      Method: {imp.method} ({Math.round(imp.confidence * 100)}% Conf)
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

        </div>

      </div>
    </div>
  );
};

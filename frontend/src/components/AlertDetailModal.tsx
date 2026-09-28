import React from 'react';
import { AlertRecord } from '../types';
import { X, AlertTriangle, CloudRain, CheckCircle, ShieldAlert, Cpu, Layers, Activity, Wrench } from 'lucide-react';

interface AlertDetailModalProps {
  alert: AlertRecord | null;
  onAcknowledge: (alertId: string) => void;
  onClose: () => void;
}

export const AlertDetailModal: React.FC<AlertDetailModalProps> = ({
  alert,
  onAcknowledge,
  onClose
}) => {
  if (!alert) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '800px' }}>
        
        {/* Modal Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '8px',
              background: alert.decision === 'WEATHER_EVENT' ? 'rgba(139, 92, 246, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: alert.decision === 'WEATHER_EVENT' ? 'var(--status-weather-event)' : 'var(--status-critical)'
            }}>
              {alert.decision === 'WEATHER_EVENT' ? (
                <CloudRain style={{ width: '22px', height: '22px' }} />
              ) : (
                <ShieldAlert style={{ width: '22px', height: '22px' }} />
              )}
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#fff' }}>
                  {alert.probable_cause.replace(/_/g, ' ')}
                </h2>
                <span className="badge mono" style={{ background: 'rgba(56, 189, 248, 0.2)', color: 'var(--accent-cyan)' }}>
                  {alert.station_id}
                </span>
                <span className={`badge badge-${alert.severity.toLowerCase()}`}>
                  {alert.severity} SEVERITY
                </span>
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Alert ID: <span className="mono">{alert.alert_id}</span> &bull; Timestamp: <span className="mono">{alert.timestamp}</span>
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
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px' }}>
          
          {/* Detailed Explanation Alert Box */}
          <div style={{
            padding: '14px 16px',
            borderRadius: '10px',
            background: alert.decision === 'WEATHER_EVENT' ? 'rgba(139, 92, 246, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: alert.decision === 'WEATHER_EVENT' ? '1px solid rgba(139, 92, 246, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)'
          }}>
            <div style={{ fontSize: '12px', fontWeight: 700, color: alert.decision === 'WEATHER_EVENT' ? 'var(--status-weather-event)' : 'var(--status-critical)', marginBottom: '4px' }}>
              EXPLAINABLE INCIDENT REASONING
            </div>
            <p style={{ fontSize: '13px', color: '#f1f5f9', lineHeight: 1.5 }}>
              {alert.explanation}
            </p>
          </div>

          {/* Metric Comparison Table: Observed vs Expected vs Deviation */}
          <div className="glass-panel" style={{ padding: '16px' }}>
            <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '10px' }}>
              PARAMETER DEVIATION MATRIX
            </h3>
            <table style={{ width: '100%', fontSize: '12px', borderCollapse: 'collapse' }} className="mono">
              <thead>
                <tr style={{ color: 'var(--text-dim)', borderBottom: '1px solid var(--border-subtle)', textAlign: 'left' }}>
                  <th style={{ padding: '8px' }}>PARAMETER</th>
                  <th style={{ padding: '8px' }}>OBSERVED VALUE</th>
                  <th style={{ padding: '8px' }}>EXPECTED BASELINE</th>
                  <th style={{ padding: '8px' }}>MEASURED DEVIATION</th>
                  <th style={{ padding: '8px' }}>STATUS</th>
                </tr>
              </thead>
              <tbody>
                {['temperature', 'pressure', 'humidity'].map((param) => {
                  const obs = alert.observed_values[param];
                  const exp = alert.expected_values[param];
                  const dev = alert.deviations[param];
                  const isFlagged = alert.flagged_parameters.includes(param);
                  const unit = param === 'temperature' ? '°C' : (param === 'pressure' ? ' hPa' : '%');

                  return (
                    <tr key={param} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '8px', textTransform: 'uppercase', fontWeight: 700, color: '#fff' }}>
                        {param}
                      </td>
                      <td style={{ padding: '8px', color: isFlagged ? 'var(--status-critical)' : '#fff', fontWeight: isFlagged ? 800 : 500 }}>
                        {obs !== null && obs !== undefined ? `${obs.toFixed(1)}${unit}` : 'Missing / Corrupted'}
                      </td>
                      <td style={{ padding: '8px', color: 'var(--text-muted)' }}>
                        {exp !== null && exp !== undefined ? `${exp.toFixed(1)}${unit}` : 'N/A'}
                      </td>
                      <td style={{ padding: '8px', color: dev && Math.abs(dev) > 3 ? 'var(--status-critical)' : 'var(--text-muted)' }}>
                        {dev !== null && dev !== undefined ? `${dev > 0 ? '+' : ''}${dev.toFixed(1)}${unit}` : 'N/A'}
                      </td>
                      <td style={{ padding: '8px' }}>
                        {isFlagged ? (
                          <span className="badge badge-critical">FLAGGED</span>
                        ) : (
                          <span className="badge badge-healthy">NOMINAL</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Evidence Contributors Breakdown */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
            {/* Temporal Signal */}
            <div className="glass-panel" style={{ padding: '12px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Activity style={{ width: '13px', height: '13px', color: 'var(--accent-cyan)' }} />
                TEMPORAL EVIDENCE
              </div>
              <div style={{ fontSize: '12px', color: '#fff', marginTop: '4px' }}>
                {alert.decision === 'SENSOR_ANOMALY' ? 'High robust Z-score / step leap' : 'Expected rate of change'}
              </div>
            </div>

            {/* Spatial Signal */}
            <div className="glass-panel" style={{ padding: '12px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Layers style={{ width: '13px', height: '13px', color: 'var(--accent-purple)' }} />
                SPATIAL EVIDENCE
              </div>
              <div style={{ fontSize: '12px', color: '#fff', marginTop: '4px' }}>
                {alert.decision === 'WEATHER_EVENT' ? 'Multi-station consensus verified' : 'Isolated spatial outlier from neighbors'}
              </div>
            </div>

            {/* Machine Learning Signal */}
            <div className="glass-panel" style={{ padding: '12px' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Cpu style={{ width: '13px', height: '13px', color: 'var(--status-healthy)' }} />
                DECISION CONFIDENCE
              </div>
              <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--accent-cyan)', marginTop: '2px' }} className="mono">
                {Math.round(alert.confidence * 100)}% Evidence Score
              </div>
            </div>
          </div>

          {/* Maintenance Action & Acknowledge Footer */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Wrench style={{ width: '16px', height: '16px', color: 'var(--status-watch)' }} />
              <div>
                <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>RECOMMENDED PROTOCOL</div>
                <div style={{ fontSize: '13px', fontWeight: 700, color: '#fff' }}>
                  {alert.recommended_action}
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '10px' }}>
              <button className="btn btn-secondary" onClick={onClose}>
                Close
              </button>
              {!alert.acknowledged ? (
                <button
                  className="btn btn-success"
                  onClick={() => {
                    onAcknowledge(alert.alert_id);
                    onClose();
                  }}
                >
                  <CheckCircle style={{ width: '15px', height: '15px' }} />
                  Acknowledge Alert
                </button>
              ) : (
                <span className="badge badge-healthy" style={{ padding: '8px 12px' }}>
                  <CheckCircle style={{ width: '14px', height: '14px' }} /> Already Acknowledged
                </span>
              )}
            </div>
          </div>

        </div>

      </div>
    </div>
  );
};

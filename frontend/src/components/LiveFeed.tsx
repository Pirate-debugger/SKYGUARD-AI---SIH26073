import React, { useState } from 'react';
import { AlertRecord } from '../types';
import { Activity, AlertTriangle, CloudRain, Cpu, Radio, ChevronRight, Check } from 'lucide-react';

interface LiveFeedProps {
  alerts: AlertRecord[];
  onSelectAlert: (alert: AlertRecord) => void;
  onAcknowledgeAlert: (alertId: string) => void;
}

export const LiveFeed: React.FC<LiveFeedProps> = ({ alerts, onSelectAlert, onAcknowledgeAlert }) => {
  const [filter, setFilter] = useState<string>('ALL');

  const filteredAlerts = alerts.filter(a => {
    if (filter === 'ALL') return true;
    if (filter === 'SENSOR_ANOMALY') return a.decision === 'SENSOR_ANOMALY';
    if (filter === 'WEATHER_EVENT') return a.decision === 'WEATHER_EVENT';
    if (filter === 'DEGRADATION') return a.decision === 'SENSOR_DEGRADATION';
    if (filter === 'UNACKNOWLEDGED') return !a.acknowledged;
    return true;
  });

  const getDecisionBadge = (decision: string) => {
    switch (decision) {
      case 'WEATHER_EVENT':
        return <span className="badge badge-weather"><CloudRain style={{ width: '10px', height: '10px' }} /> WEATHER EVENT</span>;
      case 'SENSOR_ANOMALY':
        return <span className="badge badge-critical"><AlertTriangle style={{ width: '10px', height: '10px' }} /> SENSOR ANOMALY</span>;
      case 'SENSOR_DEGRADATION':
        return <span className="badge badge-degraded"><Activity style={{ width: '10px', height: '10px' }} /> DEGRADATION</span>;
      case 'COMMUNICATION_ERROR':
        return <span className="badge badge-offline"><Radio style={{ width: '10px', height: '10px' }} /> COMM ERROR</span>;
      default:
        return <span className="badge badge-watch">{decision}</span>;
    }
  };

  const getSeverityBadge = (severity: string) => {
    const s = severity.toLowerCase();
    return <span className={`badge badge-${s === 'critical' ? 'critical' : (s === 'high' ? 'critical' : (s === 'medium' ? 'watch' : 'healthy'))}`}>{severity}</span>;
  };

  return (
    <div className="glass-panel" style={{ padding: '20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Activity style={{ width: '18px', height: '18px', color: 'var(--accent-cyan)' }} />
          <h2 style={{ fontSize: '16px', fontWeight: 700, color: '#fff' }}>
            LIVE INCIDENT STREAM
          </h2>
          <span className="live-indicator" />
        </div>

        {/* Filter Pills */}
        <div style={{ display: 'flex', gap: '6px', fontSize: '11px' }}>
          {['ALL', 'SENSOR_ANOMALY', 'WEATHER_EVENT', 'DEGRADATION', 'UNACKNOWLEDGED'].map((tab) => (
            <button
              key={tab}
              onClick={() => setFilter(tab)}
              style={{
                background: filter === tab ? 'var(--accent-cyan)' : 'var(--bg-tertiary)',
                color: filter === tab ? '#080c14' : 'var(--text-muted)',
                fontWeight: filter === tab ? 700 : 500,
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
                padding: '4px 8px',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              {tab.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {/* Feed List */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px', paddingRight: '4px' }}>
        {filteredAlerts.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-dim)' }}>
            <Activity style={{ width: '32px', height: '32px', margin: '0 auto 10px', opacity: 0.4 }} />
            <p style={{ fontSize: '13px', fontWeight: 500 }}>No incidents matching active filter.</p>
            <p style={{ fontSize: '11px', marginTop: '4px' }}>All station channels reporting normal operational telemetry.</p>
          </div>
        ) : (
          filteredAlerts.map((alert) => (
            <div
              key={alert.alert_id}
              onClick={() => onSelectAlert(alert)}
              className="glass-panel"
              style={{
                padding: '12px 14px',
                cursor: 'pointer',
                background: alert.acknowledged ? 'rgba(14, 21, 36, 0.4)' : 'rgba(20, 30, 51, 0.7)',
                borderLeft: alert.decision === 'WEATHER_EVENT' 
                  ? '3px solid var(--status-weather-event)' 
                  : (alert.decision === 'SENSOR_DEGRADATION' ? '3px solid var(--status-degraded)' : '3px solid var(--status-critical)'),
                transition: 'all 0.2s ease'
              }}
            >
              {/* Top row */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="mono" style={{ fontWeight: 800, color: '#fff', fontSize: '13px' }}>
                    {alert.station_id}
                  </span>
                  {getDecisionBadge(alert.decision)}
                  {getSeverityBadge(alert.severity)}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span className="mono" style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                    {alert.timestamp.slice(11, 19)}
                  </span>
                  <span className="mono badge" style={{ background: 'rgba(56, 189, 248, 0.1)', color: 'var(--accent-cyan)' }}>
                    {Math.round(alert.confidence * 100)}% Conf
                  </span>
                </div>
              </div>

              {/* Middle Row: Cause & Explanation */}
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#e2e8f0', marginBottom: '4px' }}>
                {alert.probable_cause.replace(/_/g, ' ')}
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.4, marginBottom: '8px' }}>
                {alert.explanation}
              </p>

              {/* Bottom Row: Values & Acknowledge */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '6px', fontSize: '11px' }}>
                <div style={{ display: 'flex', gap: '12px' }} className="mono">
                  {alert.observed_values.temperature !== null && (
                    <span>
                      <span style={{ color: 'var(--text-dim)' }}>Obs: </span>
                      <strong style={{ color: '#fff' }}>{alert.observed_values.temperature?.toFixed(1)}°C</strong>
                    </span>
                  )}
                  {alert.expected_values.temperature !== null && alert.expected_values.temperature !== undefined && (
                    <span>
                      <span style={{ color: 'var(--text-dim)' }}>Exp: </span>
                      <span style={{ color: 'var(--text-muted)' }}>{alert.expected_values.temperature?.toFixed(1)}°C</span>
                    </span>
                  )}
                  {alert.deviations.temperature !== null && alert.deviations.temperature !== undefined && (
                    <span style={{ color: Math.abs(alert.deviations.temperature) > 3 ? 'var(--status-critical)' : 'var(--text-muted)' }}>
                      Δ={alert.deviations.temperature > 0 ? '+' : ''}{alert.deviations.temperature?.toFixed(1)}
                    </span>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  {alert.acknowledged ? (
                    <span style={{ fontSize: '10px', color: 'var(--status-healthy)', display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                      <Check style={{ width: '12px', height: '12px' }} /> Acknowledged
                    </span>
                  ) : (
                    <button
                      className="btn btn-secondary"
                      style={{ padding: '3px 8px', fontSize: '10px' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        onAcknowledgeAlert(alert.alert_id);
                      }}
                    >
                      Acknowledge
                    </button>
                  )}
                  <ChevronRight style={{ width: '14px', height: '14px', color: 'var(--text-dim)' }} />
                </div>
              </div>

            </div>
          ))
        )}
      </div>

    </div>
  );
};

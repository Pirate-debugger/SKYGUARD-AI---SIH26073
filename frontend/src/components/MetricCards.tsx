import React from 'react';
import { NetworkOverview } from '../types';
import { Radio, CheckCircle, AlertTriangle, AlertOctagon, CloudRain, Bell, Activity } from 'lucide-react';

interface MetricCardsProps {
  overview: NetworkOverview | null;
}

export const MetricCards: React.FC<MetricCardsProps> = ({ overview }) => {
  if (!overview) return null;

  const healthyPct = Math.round((overview.healthy_count / (overview.total_stations || 1)) * 100);

  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
      gap: '14px',
      marginBottom: '20px'
    }}>
      
      {/* 1. Total Stations */}
      <div className="glass-panel" style={{ padding: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
          <span style={{ fontSize: '12px', fontWeight: 600 }}>TOTAL STATIONS</span>
          <Radio style={{ width: '18px', height: '18px', color: 'var(--accent-cyan)' }} />
        </div>
        <div style={{ fontSize: '28px', fontWeight: 800, marginTop: '8px', color: '#fff' }} className="mono">
          {overview.total_stations}
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
          Standard Synoptic AWS Network
        </div>
      </div>

      {/* 2. Healthy Stations */}
      <div className="glass-panel" style={{ padding: '16px', borderLeft: '3px solid var(--status-healthy)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
          <span style={{ fontSize: '12px', fontWeight: 600 }}>HEALTHY</span>
          <CheckCircle style={{ width: '18px', height: '18px', color: 'var(--status-healthy)' }} />
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '8px' }}>
          <span style={{ fontSize: '28px', fontWeight: 800, color: 'var(--status-healthy)' }} className="mono">
            {overview.healthy_count}
          </span>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>({healthyPct}%)</span>
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
          Operating Within Tolerances
        </div>
      </div>

      {/* 3. Watch & Degraded */}
      <div className="glass-panel" style={{ padding: '16px', borderLeft: '3px solid var(--status-watch)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
          <span style={{ fontSize: '12px', fontWeight: 600 }}>WATCH / DEGRADED</span>
          <AlertTriangle style={{ width: '18px', height: '18px', color: 'var(--status-watch)' }} />
        </div>
        <div style={{ fontSize: '28px', fontWeight: 800, marginTop: '8px', color: 'var(--status-watch)' }} className="mono">
          {overview.watch_count + overview.degraded_count}
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
          {overview.watch_count} Watch &bull; {overview.degraded_count} Degraded Drift
        </div>
      </div>

      {/* 4. Critical & Offline */}
      <div className="glass-panel" style={{ padding: '16px', borderLeft: '3px solid var(--status-critical)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
          <span style={{ fontSize: '12px', fontWeight: 600 }}>CRITICAL / FAULT</span>
          <AlertOctagon style={{ width: '18px', height: '18px', color: 'var(--status-critical)' }} />
        </div>
        <div style={{ fontSize: '28px', fontWeight: 800, marginTop: '8px', color: 'var(--status-critical)' }} className="mono">
          {overview.critical_count + overview.offline_count}
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
          {overview.critical_count} Critical &bull; {overview.offline_count} Offline Drops
        </div>
      </div>

      {/* 5. Active Anomalies */}
      <div className={`glass-panel ${overview.active_anomalies_count > 0 ? 'glass-panel-glow' : ''}`} style={{ padding: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
          <span style={{ fontSize: '12px', fontWeight: 600 }}>ACTIVE ANOMALIES</span>
          <Activity style={{ width: '18px', height: '18px', color: 'var(--accent-cyan)' }} />
        </div>
        <div style={{ fontSize: '28px', fontWeight: 800, marginTop: '8px', color: overview.active_anomalies_count > 0 ? '#38bdf8' : '#fff' }} className="mono">
          {overview.active_anomalies_count}
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
          Unacknowledged Incidents
        </div>
      </div>

      {/* 6. Weather Events (False Alarm Reductions) */}
      <div className="glass-panel" style={{ padding: '16px', borderLeft: '3px solid var(--status-weather-event)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
          <span style={{ fontSize: '12px', fontWeight: 600 }}>WEATHER EVENTS</span>
          <CloudRain style={{ width: '18px', height: '18px', color: 'var(--status-weather-event)' }} />
        </div>
        <div style={{ fontSize: '28px', fontWeight: 800, marginTop: '8px', color: 'var(--status-weather-event)' }} className="mono">
          {overview.weather_events_count}
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
          Spatial Consensus Corroborated
        </div>
      </div>

    </div>
  );
};

import React, { useState } from 'react';
import { Play, Square, FastForward, Zap, CloudLightning, Snowflake, TrendingUp, WifiOff, AlertOctagon, Globe } from 'lucide-react';
import { StationData } from '../types';

interface LiveStreamControlsProps {
  isStreaming: boolean;
  stations: StationData[];
  onStartStream: () => void;
  onStopStream: () => void;
  onManualTick: () => void;
  onInject: (stationId: string, anomalyType: string, param?: string, steps?: number, magnitude?: number) => void;
}

export const LiveStreamControls: React.FC<LiveStreamControlsProps> = ({
  isStreaming,
  stations,
  onStartStream,
  onStopStream,
  onManualTick,
  onInject
}) => {
  const [selectedStation, setSelectedStation] = useState<string>('AWS-001');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleInject = async (type: string, param: string = 'temperature', steps: number = 5, mag?: number) => {
    setIsSubmitting(true);
    try {
      await onInject(selectedStation, type, param, steps, mag);
      setFeedback(`Queued: ${type} on ${selectedStation}`);
      setTimeout(() => setFeedback(null), 3000);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="glass-panel" style={{ padding: '16px 20px', marginBottom: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        
        {/* Playback Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isStreaming ? (
            <button className="btn btn-danger" onClick={onStopStream}>
              <Square style={{ width: '15px', height: '15px' }} />
              STOP STREAM
            </button>
          ) : (
            <button className="btn btn-success" onClick={onStartStream}>
              <Play style={{ width: '15px', height: '15px' }} />
              START STREAM
            </button>
          )}

          <button className="btn btn-secondary" onClick={onManualTick} title="Advance 1 step manually (5 minutes simulated telemetry)">
            <FastForward style={{ width: '15px', height: '15px' }} />
            STEP TICK (+5m)
          </button>

          {/* Station Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: '12px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Target:</span>
            <select
              value={selectedStation}
              onChange={(e) => setSelectedStation(e.target.value)}
              style={{
                background: 'var(--bg-tertiary)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-medium)',
                borderRadius: '6px',
                padding: '6px 10px',
                fontSize: '12px',
                fontFamily: 'var(--font-mono)',
                outline: 'none',
                cursor: 'pointer'
              }}
            >
              {stations.map(st => (
                <option key={st.metadata.station_id} value={st.metadata.station_id}>
                  {st.metadata.station_id} — {st.metadata.station_name}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Feedback message */}
        {feedback && (
          <div style={{
            fontSize: '12px',
            color: 'var(--accent-cyan)',
            fontWeight: 600,
            background: 'rgba(56, 189, 248, 0.1)',
            padding: '4px 10px',
            borderRadius: '6px',
            border: '1px solid rgba(56, 189, 248, 0.3)'
          }}>
            {feedback}
          </div>
        )}

        {/* Anomaly Injections Toolbar */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.05em' }}>
            INJECT DEMO SCENARIO:
          </span>

          {/* Spike */}
          <button
            className="btn btn-danger"
            style={{ fontSize: '11px', padding: '6px 10px' }}
            disabled={isSubmitting}
            onClick={() => handleInject('SPIKE', 'temperature', 1, 12.0)}
            title="Inject realistic +12°C jump in temperature (Isolated Sensor Spike)"
          >
            <Zap style={{ width: '13px', height: '13px' }} />
            Temp Spike (+12°C)
          </button>

          {/* Regional Weather Event */}
          <button
            className="btn btn-purple"
            style={{ fontSize: '11px', padding: '6px 10px' }}
            disabled={isSubmitting}
            onClick={() => handleInject('WEATHER_EVENT', 'temperature', 4)}
            title="Simulate heatburst/frontal surge simultaneously across nearby stations (Regional Weather Event)"
          >
            <CloudLightning style={{ width: '13px', height: '13px' }} />
            Regional Weather Event
          </button>

          {/* Sensor Freeze */}
          <button
            className="btn btn-amber"
            style={{ fontSize: '11px', padding: '6px 10px' }}
            disabled={isSubmitting}
            onClick={() => handleInject('FREEZE', 'humidity', 7)}
            title="Sensor output flatlines with zero variance across consecutive reporting cycles"
          >
            <Snowflake style={{ width: '13px', height: '13px' }} />
            Sensor Freeze (RH)
          </button>

          {/* Calibration Drift */}
          <button
            className="btn btn-secondary"
            style={{ fontSize: '11px', padding: '6px 10px', color: 'var(--status-degraded)' }}
            disabled={isSubmitting}
            onClick={() => handleInject('DRIFT', 'temperature', 12, 0.45)}
            title="Systematic creeping temperature drift indicating calibration degradation"
          >
            <TrendingUp style={{ width: '13px', height: '13px' }} />
            Creeping Drift
          </button>

          {/* Comm Drop */}
          <button
            className="btn btn-secondary"
            style={{ fontSize: '11px', padding: '6px 10px', color: 'var(--text-muted)' }}
            disabled={isSubmitting}
            onClick={() => handleInject('COMM_GAP', 'all', 3)}
            title="Simulate missing telemetry packets (Communication Gap)"
          >
            <WifiOff style={{ width: '13px', height: '13px' }} />
            Comm Drop
          </button>

          {/* Data Corruption */}
          <button
            className="btn btn-secondary"
            style={{ fontSize: '11px', padding: '6px 10px', color: '#f87171' }}
            disabled={isSubmitting}
            onClick={() => handleInject('DATA_CORRUPTION', 'temperature', 1)}
            title="Inject impossible value (142.5°C) to trigger Data Quality boundary reject"
          >
            <AlertOctagon style={{ width: '13px', height: '13px' }} />
            Data Corruption
          </button>
        </div>

      </div>
    </div>
  );
};

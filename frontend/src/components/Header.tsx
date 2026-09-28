import React from 'react';
import { Shield, Radio, FileText, Upload, Activity, Cpu } from 'lucide-react';

interface HeaderProps {
  isConnected: boolean;
  isStreaming: boolean;
  tickCount: number;
  onOpenReport: () => void;
  onOpenUpload: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  isConnected,
  isStreaming,
  tickCount,
  onOpenReport,
  onOpenUpload
}) => {
  return (
    <header className="glass-panel" style={{ padding: '16px 24px', marginBottom: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
        
        {/* Brand & Problem Statement */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div style={{
            width: '44px',
            height: '44px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.2) 0%, rgba(59, 130, 246, 0.3) 100%)',
            border: '1px solid var(--border-glow)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 15px rgba(56, 189, 248, 0.25)'
          }}>
            <Shield style={{ width: '24px', height: '24px', color: 'var(--accent-cyan)' }} />
          </div>

          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h1 style={{ fontSize: '22px', fontWeight: 800, letterSpacing: '-0.02em', color: '#fff' }}>
                SKYGUARD <span style={{ color: 'var(--accent-cyan)' }}>AI</span>
              </h1>
              <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.12)', color: 'var(--accent-cyan)', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
                SIH26073
              </span>
              <span className="badge" style={{ background: 'rgba(168, 85, 247, 0.12)', color: 'var(--accent-purple)', border: '1px solid rgba(168, 85, 247, 0.3)' }}>
                <Cpu style={{ width: '12px', height: '12px' }} /> Hybrid ML + Edge
              </span>
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Intelligent AWS Anomaly Detection &bull; Weather Event vs Sensor Fault Discrimination &bull; Sensor Health
            </p>
          </div>
        </div>

        {/* Live Stream & Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          
          {/* Status Indicator */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 12px',
            borderRadius: '8px',
            background: 'var(--bg-tertiary)',
            border: '1px solid var(--border-subtle)',
            fontSize: '12px'
          }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                backgroundColor: isConnected ? (isStreaming ? 'var(--status-healthy)' : 'var(--status-watch)') : 'var(--status-critical)',
                boxShadow: isConnected ? '0 0 8px var(--status-healthy)' : 'none'
              }}
            />
            <span style={{ color: 'var(--text-muted)' }}>
              {isConnected ? (isStreaming ? `STREAMING (Tick #${tickCount})` : 'CONNECTED (Paused)') : 'DISCONNECTED'}
            </span>
          </div>

          {/* Upload CSV */}
          <button className="btn btn-secondary" onClick={onOpenUpload} title="Upload historical AWS CSV dataset">
            <Upload style={{ width: '15px', height: '15px' }} />
            Ingest CSV
          </button>

          {/* Audit Report */}
          <button className="btn btn-primary" onClick={onOpenReport} title="Export full SIH audit report">
            <FileText style={{ width: '15px', height: '15px' }} />
            Audit Report
          </button>
        </div>

      </div>
    </header>
  );
};

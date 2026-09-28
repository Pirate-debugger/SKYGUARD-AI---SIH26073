import React, { useState } from 'react';
import { X, Download, Copy, Check, FileText } from 'lucide-react';

interface AnomalyReportModalProps {
  reportText: string;
  onClose: () => void;
}

export const AnomalyReportModal: React.FC<AnomalyReportModalProps> = ({ reportText, onClose }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(reportText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const handleDownload = () => {
    const blob = new Blob([reportText], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `skyguard_ai_audit_report_${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '850px' }}>
        
        {/* Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <FileText style={{ width: '22px', height: '22px', color: 'var(--accent-cyan)' }} />
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#fff' }}>
                SKYGUARD AI AUDIT & SENSOR HEALTH REPORT
              </h2>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Smart India Hackathon 2026 &bull; Problem Statement SIH26073 Compliance Audit
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button className="btn btn-secondary" onClick={handleCopy} style={{ padding: '6px 12px', fontSize: '12px' }}>
              {copied ? <Check style={{ width: '14px', height: '14px', color: 'var(--status-healthy)' }} /> : <Copy style={{ width: '14px', height: '14px' }} />}
              {copied ? 'Copied!' : 'Copy'}
            </button>
            <button className="btn btn-primary" onClick={handleDownload} style={{ padding: '6px 12px', fontSize: '12px' }}>
              <Download style={{ width: '14px', height: '14px' }} />
              Download .md
            </button>
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
        </div>

        {/* Content Box */}
        <div style={{ padding: '24px' }}>
          <pre style={{
            background: 'var(--bg-tertiary)',
            color: '#e2e8f0',
            fontFamily: 'var(--font-mono)',
            fontSize: '12px',
            lineHeight: 1.6,
            padding: '16px',
            borderRadius: '10px',
            overflowX: 'auto',
            maxHeight: '60vh',
            whiteSpace: 'pre-wrap',
            border: '1px solid var(--border-subtle)'
          }}>
            {reportText}
          </pre>
        </div>

      </div>
    </div>
  );
};

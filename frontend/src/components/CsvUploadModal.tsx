import React, { useState } from 'react';
import { X, Upload, CheckCircle, AlertTriangle, FileSpreadsheet } from 'lucide-react';
import { api } from '../services/api';

interface CsvUploadModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export const CsvUploadModal: React.FC<CsvUploadModalProps> = ({ onClose, onSuccess }) => {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    setError(null);
    try {
      const res = await api.uploadCsv(file);
      setResult(res);
      onSuccess();
    } catch (err: any) {
      setError(err.message || 'Failed to upload CSV file');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '640px' }}>
        
        {/* Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <FileSpreadsheet style={{ width: '22px', height: '22px', color: 'var(--accent-cyan)' }} />
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#fff' }}>
                INGEST AWS CSV DATASET
              </h2>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Upload historical surface weather observations (CSV format)
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
              padding: '6px'
            }}
          >
            <X style={{ width: '20px', height: '20px' }} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          <div style={{
            border: '2px dashed var(--border-medium)',
            borderRadius: '12px',
            padding: '30px 20px',
            textAlign: 'center',
            background: 'rgba(56, 189, 248, 0.03)'
          }}>
            <Upload style={{ width: '36px', height: '36px', color: 'var(--accent-cyan)', margin: '0 auto 10px' }} />
            <p style={{ fontSize: '14px', fontWeight: 600, color: '#fff' }}>
              Select CSV File with AWS Telemetry
            </p>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Requires columns: <code className="mono">station_id, timestamp, temperature, pressure, humidity</code>
            </p>

            <input
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              style={{ marginTop: '16px', fontSize: '12px' }}
            />
          </div>

          {error && (
            <div style={{ padding: '10px 14px', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.15)', color: 'var(--status-critical)', fontSize: '12px' }}>
              {error}
            </div>
          )}

          {result && (
            <div style={{ padding: '14px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--status-healthy)', fontWeight: 700, fontSize: '13px' }}>
                <CheckCircle style={{ width: '16px', height: '16px' }} />
                Batch Ingest Complete: {result.records_processed} Records Processed
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '6px' }}>
                Processed through Quality, Spatial-Temporal, and Isolation Forest pipeline layers.
              </div>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
            <button className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              disabled={!file || isUploading}
              onClick={handleUpload}
            >
              {isUploading ? 'Processing Pipeline...' : 'Process Telemetry Batch'}
            </button>
          </div>

        </div>

      </div>
    </div>
  );
};

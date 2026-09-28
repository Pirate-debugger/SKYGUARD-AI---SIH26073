import React, { useEffect, useState, useRef, useCallback } from 'react';
import { api } from './services/api';
import { NetworkOverview, StationData, AlertRecord, ProcessedReading } from './types';
import { Header } from './components/Header';
import { MetricCards } from './components/MetricCards';
import { LiveStreamControls } from './components/LiveStreamControls';
import { NetworkMap } from './components/NetworkMap';
import { StationTable } from './components/StationTable';
import { LiveFeed } from './components/LiveFeed';
import { StationDetailModal } from './components/StationDetailModal';
import { AlertDetailModal } from './components/AlertDetailModal';
import { AnomalyReportModal } from './components/AnomalyReportModal';
import { CsvUploadModal } from './components/CsvUploadModal';

export const App: React.FC = () => {
  const [overview, setOverview] = useState<NetworkOverview | null>(null);
  const [stations, setStations] = useState<StationData[]>([]);
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [tickCount, setTickCount] = useState<number>(0);
  const [isConnected, setIsConnected] = useState<boolean>(false);

  // Modals
  const [selectedStationId, setSelectedStationId] = useState<string | null>(null);
  const [selectedStationDetail, setSelectedStationDetail] = useState<{
    station: StationData | null;
    history: ProcessedReading[];
    neighbors: Array<{ station_id: string; distance_km: number }>;
  } | null>(null);

  const [selectedAlert, setSelectedAlert] = useState<AlertRecord | null>(null);
  const [showReportModal, setShowReportModal] = useState<boolean>(false);
  const [reportMarkdown, setReportMarkdown] = useState<string>('');
  const [showUploadModal, setShowUploadModal] = useState<boolean>(false);

  const wsRef = useRef<WebSocket | null>(null);

  // Initial Data Fetch
  const loadData = useCallback(async () => {
    try {
      const [ov, st, al, sim] = await Promise.all([
        api.getNetworkOverview(),
        api.getStations(),
        api.getAlerts(30),
        api.getSimulatorStatus()
      ]);
      setOverview(ov);
      setStations(st);
      setAlerts(al);
      setIsStreaming(sim.is_running);
      setTickCount(sim.tick_count);
    } catch (err) {
      console.error('Error loading initial data:', err);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 4000);
    return () => clearInterval(interval);
  }, [loadData]);

  // WebSocket Connection
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/stream`;

    const connectWs = () => {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const packet = JSON.parse(event.data);
          if (packet.type === 'STREAM_TICK') {
            setTickCount(packet.tick);
            setIsStreaming(true);

            // Update readings in stations list
            if (packet.readings && Array.isArray(packet.readings)) {
              setStations(prev => prev.map(st => {
                const updated = packet.readings.find((r: ProcessedReading) => r.station_id === st.metadata.station_id);
                if (updated) {
                  return { ...st, latest_reading: updated };
                }
                return st;
              }));
            }

            // Append new alerts
            if (packet.alerts && packet.alerts.length > 0) {
              setAlerts(prev => [...packet.alerts, ...prev].slice(0, 50));
            }

            // Refresh overview counts
            api.getNetworkOverview().then(setOverview).catch(() => {});
          } else if (packet.type === 'INIT_STATE') {
            setIsStreaming(packet.is_running);
            setTickCount(packet.tick);
          }
        } catch (e) {
          console.error('WebSocket parse error:', e);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        // Reconnect after 3s
        setTimeout(connectWs, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connectWs();

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  // Station Detail Fetcher
  const handleSelectStation = async (stationId: string) => {
    setSelectedStationId(stationId);
    try {
      const detail = await api.getStationDetail(stationId);
      const matched = stations.find(s => s.metadata.station_id === stationId) || null;
      setSelectedStationDetail({
        station: {
          metadata: detail.metadata,
          health: detail.health,
          latest_reading: matched?.latest_reading || null
        },
        history: detail.readings_history || [],
        neighbors: detail.neighbors || []
      });
    } catch (err) {
      console.error('Failed to load station detail:', err);
    }
  };

  // Stream controls
  const handleStartStream = async () => {
    await api.startStream();
    setIsStreaming(true);
  };

  const handleStopStream = async () => {
    await api.stopStream();
    setIsStreaming(false);
  };

  const handleManualTick = async () => {
    await api.manualTick();
    loadData();
  };

  const handleInject = async (
    stationId: string,
    anomalyType: string,
    param: string = 'temperature',
    steps: number = 5,
    magnitude?: number
  ) => {
    await api.injectAnomaly(stationId, anomalyType, param, steps, magnitude);
  };

  const handleAcknowledgeAlert = async (alertId: string) => {
    await api.acknowledgeAlert(alertId, 'Lead Operator');
    setAlerts(prev => prev.map(a => a.alert_id === alertId ? { ...a, acknowledged: true } : a));
    loadData();
  };

  const handleOpenReport = async () => {
    try {
      const md = await api.getReport('markdown');
      setReportMarkdown(md);
      setShowReportModal(true);
    } catch (err) {
      console.error('Failed to fetch report:', err);
    }
  };

  return (
    <div style={{ maxWidth: '1600px', margin: '0 auto', padding: '20px' }}>
      
      {/* 1. Header */}
      <Header
        isConnected={isConnected}
        isStreaming={isStreaming}
        tickCount={tickCount}
        onOpenReport={handleOpenReport}
        onOpenUpload={() => setShowUploadModal(true)}
      />

      {/* 2. Top Metric Cards */}
      <MetricCards overview={overview} />

      {/* 3. Live Stream Simulator Controls & Injection Toolbar */}
      <LiveStreamControls
        isStreaming={isStreaming}
        stations={stations}
        onStartStream={handleStartStream}
        onStopStream={handleStopStream}
        onManualTick={handleManualTick}
        onInject={handleInject}
      />

      {/* 4. Main Two-Column View: Regional Geospatial Map & Live Incident Stream */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1.25fr) minmax(0, 1fr)',
        gap: '20px',
        marginBottom: '20px',
        minHeight: '480px'
      }}>
        {/* Left: Interactive Geospatial Network Map */}
        <NetworkMap
          stations={stations}
          onSelectStation={handleSelectStation}
        />

        {/* Right: Live Real-Time Incident Stream */}
        <LiveFeed
          alerts={alerts}
          onSelectAlert={(alert) => setSelectedAlert(alert)}
          onAcknowledgeAlert={handleAcknowledgeAlert}
        />
      </div>

      {/* 5. Monitored AWS Fleet Telemetry Table */}
      <StationTable
        stations={stations}
        onSelectStation={handleSelectStation}
      />

      {/* --- MODALS --- */}

      {/* Station Detail Modal */}
      {selectedStationDetail && (
        <StationDetailModal
          station={selectedStationDetail.station}
          historyReadings={selectedStationDetail.history}
          neighbors={selectedStationDetail.neighbors}
          onClose={() => {
            setSelectedStationId(null);
            setSelectedStationDetail(null);
          }}
        />
      )}

      {/* Alert Detail Modal */}
      {selectedAlert && (
        <AlertDetailModal
          alert={selectedAlert}
          onAcknowledge={handleAcknowledgeAlert}
          onClose={() => setSelectedAlert(null)}
        />
      )}

      {/* Full Audit Report Modal */}
      {showReportModal && (
        <AnomalyReportModal
          reportText={reportMarkdown}
          onClose={() => setShowReportModal(false)}
        />
      )}

      {/* CSV Telemetry Upload Modal */}
      {showUploadModal && (
        <CsvUploadModal
          onClose={() => setShowUploadModal(false)}
          onSuccess={() => {
            loadData();
            setShowUploadModal(false);
          }}
        />
      )}

    </div>
  );
};

/**
 * API Service for SkyGuard AI
 * SIH26073: Automatic Weather Station Anomaly Detection System
 */

import { NetworkOverview, StationData, AlertRecord, ProcessedReading } from '../types';

const BASE_URL = '/api';

export const api = {
  async getHealth() {
    const res = await fetch(`${BASE_URL}/health`);
    if (!res.ok) throw new Error('Failed to fetch system health');
    return res.json();
  },

  async getNetworkOverview(): Promise<NetworkOverview> {
    const res = await fetch(`${BASE_URL}/network/overview`);
    if (!res.ok) throw new Error('Failed to fetch network overview');
    return res.json();
  },

  async getStations(): Promise<StationData[]> {
    const res = await fetch(`${BASE_URL}/stations`);
    if (!res.ok) throw new Error('Failed to fetch stations');
    return res.json();
  },

  async getStationDetail(stationId: string) {
    const res = await fetch(`${BASE_URL}/stations/${stationId}`);
    if (!res.ok) throw new Error(`Failed to fetch station ${stationId}`);
    return res.json();
  },

  async getAlerts(limit: number = 50, acknowledged?: boolean): Promise<AlertRecord[]> {
    let url = `${BASE_URL}/alerts?limit=${limit}`;
    if (acknowledged !== undefined) {
      url += `&acknowledged=${acknowledged}`;
    }
    const res = await fetch(url);
    if (!res.ok) throw new Error('Failed to fetch alerts');
    return res.json();
  },

  async acknowledgeAlert(alertId: string, operatorName: string = 'Operator') {
    const res = await fetch(`${BASE_URL}/alerts/${alertId}/acknowledge?operator_name=${encodeURIComponent(operatorName)}`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Failed to acknowledge alert');
    return res.json();
  },

  async getSimulatorStatus() {
    const res = await fetch(`${BASE_URL}/simulator/status`);
    if (!res.ok) throw new Error('Failed to fetch simulator status');
    return res.json();
  },

  async startStream() {
    const res = await fetch(`${BASE_URL}/simulator/start`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to start stream');
    return res.json();
  },

  async stopStream() {
    const res = await fetch(`${BASE_URL}/simulator/stop`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to stop stream');
    return res.json();
  },

  async manualTick() {
    const res = await fetch(`${BASE_URL}/simulator/tick`, { method: 'POST' });
    if (!res.ok) throw new Error('Failed to trigger tick');
    return res.json();
  },

  async injectAnomaly(
    stationId: string,
    anomalyType: string,
    targetParameter: string = 'temperature',
    durationSteps: number = 5,
    magnitude?: number
  ) {
    const res = await fetch(`${BASE_URL}/simulator/inject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        station_id: stationId,
        anomaly_type: anomalyType,
        target_parameter: targetParameter,
        duration_steps: durationSteps,
        magnitude: magnitude
      })
    });
    if (!res.ok) throw new Error('Failed to inject anomaly');
    return res.json();
  },

  async getReport(format: 'json' | 'markdown' = 'markdown'): Promise<string> {
    const res = await fetch(`${BASE_URL}/report?format=${format}`);
    if (!res.ok) throw new Error('Failed to fetch report');
    return res.text();
  },

  async uploadCsv(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(`${BASE_URL}/ingest/csv`, {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error('Failed to upload CSV');
    return res.json();
  }
};

import React, { useState, useEffect, useMemo } from 'react';
import { StationData, SpatialTopologyResponse, SensorHealthStatus } from '../types';
import { api } from '../services/api';
import { haversineDistanceKm, calculateGeoBounds } from '../utils/geo';
import { Compass, Radio, ShieldAlert, CloudRain, CheckCircle2, AlertTriangle, XCircle, WifiOff } from 'lucide-react';

interface NetworkMapProps {
  stations: StationData[];
  selectedStationId?: string | null;
  onSelectStation: (stationId: string) => void;
}

export const NetworkMap: React.FC<NetworkMapProps> = ({
  stations,
  selectedStationId,
  onSelectStation
}) => {
  const [topology, setTopology] = useState<SpatialTopologyResponse | null>(null);
  const [radiusKm, setRadiusKm] = useState<number>(150);
  const [kNearest, setKNearest] = useState<number>(4);
  const [hoveredStationId, setHoveredStationId] = useState<string | null>(null);

  // Load authoritative Haversine topology from backend
  const fetchTopology = async (r: number, k: number) => {
    try {
      const data = await api.getSpatialTopology(r, k);
      setTopology(data);
    } catch (err) {
      console.error('Failed to fetch spatial topology:', err);
    }
  };

  useEffect(() => {
    fetchTopology(radiusKm, kNearest);
  }, [radiusKm, kNearest]);

  // Combine authoritative topology station data with live WebSocket stations feed
  const mergedStations = useMemo(() => {
    if (!topology) {
      return stations.map(s => {
        const comm = s.health?.communication_state || 'ONLINE';
        const decision = s.latest_reading?.decision || 'NORMAL';
        const spev = s.latest_reading?.spatial_evidence;
        return {
          station_id: s.metadata.station_id,
          name: s.metadata.station_name,
          latitude: s.metadata.latitude,
          longitude: s.metadata.longitude,
          elevation_m: s.metadata.elevation_m,
          region: s.metadata.region,
          station_type: s.metadata.station_type,
          radius_km: radiusKm,
          neighbor_count: 0,
          neighbors_within_radius: 0,
          neighbors: [] as Array<{ station_id: string; distance_km: number }>,
          spatial_status: 'NORMAL' as const,
          health_status: s.health?.status || s.metadata.status || 'HEALTHY',
          communication_state: comm,
          health_score: s.health?.health_score ?? 100,
          missed_intervals: s.health?.missed_intervals ?? 0,
          time_since_last_min: s.health?.time_since_last_reading_min ?? 0,
          latest_decision: decision,
          latest_reading: s.latest_reading ? {
            temperature: s.latest_reading.temperature,
            pressure: s.latest_reading.pressure,
            humidity: s.latest_reading.humidity,
            timestamp: s.latest_reading.timestamp
          } : null,
          spatial_evidence: spev ? {
            is_consistent: spev.is_consistent,
            neighbor_count: spev.neighbor_count,
            valid_neighbor_count: spev.valid_neighbor_count ?? spev.neighbor_count,
            corroborating_stations_count: spev.corroborating_stations_count ?? 0,
            agreement_ratio: spev.agreement_ratio ?? 0.0,
            directional_agreement: spev.directional_agreement ?? false,
            regional_event_detected: spev.regional_event_detected,
            explanation: spev.explanation
          } : null
        };
      });
    }

    return topology.stations.map(topoSt => {
      // Find live state from WebSocket updates
      const live = stations.find(s => s.metadata.station_id === topoSt.station_id);
      
      const healthStatus = live?.health?.status || topoSt.health_status || 'HEALTHY';
      const commState = live?.health?.communication_state || topoSt.communication_state || 'ONLINE';
      const healthScore = live?.health?.health_score ?? topoSt.health_score ?? 100;
      const missedIntervals = live?.health?.missed_intervals ?? 0;
      const timeSinceLastMin = live?.health?.time_since_last_reading_min ?? 0;
      const latestDecision = live?.latest_reading?.decision || topoSt.latest_decision || 'NORMAL';
      
      const latestReading = live?.latest_reading ? {
        temperature: live.latest_reading.temperature,
        pressure: live.latest_reading.pressure,
        humidity: live.latest_reading.humidity,
        timestamp: live.latest_reading.timestamp
      } : topoSt.latest_reading;

      // Extract REAL spatial evidence from backend - never fake 100% agreement
      let spev = topoSt.spatial_evidence;
      if (live?.latest_reading?.spatial_evidence) {
        const liveSpev = live.latest_reading.spatial_evidence;
        spev = {
          is_consistent: liveSpev.is_consistent,
          neighbor_count: liveSpev.neighbor_count,
          valid_neighbor_count: liveSpev.valid_neighbor_count ?? topoSt.neighbor_count,
          corroborating_stations_count: liveSpev.corroborating_stations_count ?? (latestDecision === 'WEATHER_EVENT' ? topoSt.neighbor_count : 0),
          agreement_ratio: liveSpev.agreement_ratio ?? (latestDecision === 'WEATHER_EVENT' ? 1.0 : 0.0),
          directional_agreement: liveSpev.directional_agreement ?? (latestDecision === 'WEATHER_EVENT'),
          regional_event_detected: liveSpev.regional_event_detected,
          explanation: liveSpev.explanation
        };
      }

      return {
        ...topoSt,
        name: topoSt.station_name,
        health_status: healthStatus,
        communication_state: commState,
        health_score: healthScore,
        missed_intervals: missedIntervals,
        time_since_last_min: timeSinceLastMin,
        latest_decision: latestDecision,
        latest_reading: latestReading,
        spatial_evidence: spev
      };
    });
  }, [topology, stations, radiusKm]);

  // Dynamic Viewport Bounds calculation with proportional padding
  const { boundMinLat, boundMaxLat, boundMinLon, boundMaxLon } = useMemo(() => {
    const bounds = calculateGeoBounds(
      mergedStations.map(s => ({ latitude: s.latitude, longitude: s.longitude })),
      0.14
    );
    return {
      boundMinLat: bounds.minLat,
      boundMaxLat: bounds.maxLat,
      boundMinLon: bounds.minLon,
      boundMaxLon: bounds.maxLon
    };
  }, [mergedStations]);

  const svgWidth = 860;
  const svgHeight = 490;

  // Project lat/lon into SVG canvas coordinates
  const project = (lat: number, lon: number) => {
    const x = ((lon - boundMinLon) / (boundMaxLon - boundMinLon)) * (svgWidth - 140) + 70;
    const y = ((boundMaxLat - lat) / (boundMaxLat - boundMinLat)) * (svgHeight - 110) + 55;
    return { x, y };
  };

  // SENSOR HEALTH Base Node Color (Hardware Condition)
  const getHealthColor = (status: SensorHealthStatus | string) => {
    switch (status) {
      case 'HEALTHY': return 'var(--status-healthy)';
      case 'WATCH': return 'var(--status-watch)';
      case 'DEGRADED': return 'var(--status-degraded)';
      case 'CRITICAL': return 'var(--status-critical)';
      case 'OFFLINE': return 'var(--status-offline)';
      default: return 'var(--status-healthy)';
    }
  };

  // Find active inspected station (hovered or selected)
  const activeStation = useMemo(() => {
    const targetId = hoveredStationId || selectedStationId;
    if (!targetId) return null;
    return mergedStations.find(s => s.station_id === targetId) || null;
  }, [hoveredStationId, selectedStationId, mergedStations]);

  // Edges directly from authoritative backend topology
  const authoritativeEdges = useMemo(() => {
    if (!topology || !topology.edges) return [];
    
    // Station coordinate lookup map
    const coordMap = new Map<string, { x: number; y: number; lat: number; lon: number; decision: string }>();
    mergedStations.forEach(s => {
      coordMap.set(s.station_id, {
        ...project(s.latitude, s.longitude),
        lat: s.latitude,
        lon: s.longitude,
        decision: s.latest_decision || 'NORMAL'
      });
    });

    return topology.edges.map(edge => {
      const p1 = coordMap.get(edge.source);
      const p2 = coordMap.get(edge.target);
      if (!p1 || !p2) return null;

      // Corroborating if flagged by engine OR both stations are currently experiencing a weather event
      const isCorroborating = edge.is_corroborating || (p1.decision === 'WEATHER_EVENT' && p2.decision === 'WEATHER_EVENT');

      return {
        source: edge.source,
        target: edge.target,
        distance_km: edge.distance_km,
        x1: p1.x,
        y1: p1.y,
        x2: p2.x,
        y2: p2.y,
        isCorroborating
      };
    }).filter(Boolean);
  }, [topology, mergedStations, boundMinLat, boundMaxLat, boundMinLon, boundMaxLon]);

  // Geographic 150 km Radius Circle Scaling for Active Station
  const radiusOverlay = useMemo(() => {
    if (!activeStation) return null;
    const { x, y } = project(activeStation.latitude, activeStation.longitude);
    const pixelsPerLat = (svgHeight - 110) / (boundMaxLat - boundMinLat);
    const pixelsPerLon = (svgWidth - 140) / (boundMaxLon - boundMinLon);
    
    const rLatDeg = radiusKm / 111.32;
    const rLonDeg = radiusKm / (111.32 * Math.cos((activeStation.latitude * Math.PI) / 180.0));
    
    const rx = rLonDeg * pixelsPerLon;
    const ry = rLatDeg * pixelsPerLat;

    return { x, y, rx, ry };
  }, [activeStation, radiusKm, boundMinLat, boundMaxLat, boundMinLon, boundMaxLon]);

  return (
    <div className="glass-panel" style={{ padding: '18px 20px', height: '100%', display: 'flex', flexDirection: 'column' }}>
      
      {/* 1. Header with Dynamic Metadata & Interactive Radius Switcher */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px', flexWrap: 'wrap', gap: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Compass style={{ width: '20px', height: '20px', color: 'var(--accent-cyan)' }} />
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h2 style={{ fontSize: '15px', fontWeight: 700, color: '#fff', letterSpacing: '0.03em' }}>
                REGIONAL AWS GEOSPATIAL MESH
              </h2>
              <span className="badge" style={{ background: 'rgba(56, 189, 248, 0.12)', color: 'var(--accent-cyan)', border: '1px solid rgba(56, 189, 248, 0.25)', fontSize: '11px', fontWeight: 600 }}>
                {mergedStations.length} Stations &bull; {topology?.radius_km || radiusKm} km Spatial Radius
              </span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>
              Authoritative Haversine graph &bull; k_nearest={topology?.k_nearest_neighbors || kNearest} &bull; WGS84 Geodetic
            </div>
          </div>
        </div>

        {/* Dynamic Radius & K Selector Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Radius:</span>
          {[100, 150, 200].map(r => (
            <button
              key={r}
              onClick={() => setRadiusKm(r)}
              style={{
                background: radiusKm === r ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                color: radiusKm === r ? 'var(--accent-cyan)' : 'var(--text-muted)',
                border: `1px solid ${radiusKm === r ? 'var(--accent-cyan)' : 'var(--border-subtle)'}`,
                borderRadius: '6px',
                padding: '3px 8px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              title={`Switch spatial analysis radius to ${r} km`}
            >
              {r} km
            </button>
          ))}

          <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '6px' }}>k:</span>
          {[2, 4].map(k => (
            <button
              key={k}
              onClick={() => setKNearest(k)}
              style={{
                background: kNearest === k ? 'rgba(168, 85, 247, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                color: kNearest === k ? '#c084fc' : 'var(--text-muted)',
                border: `1px solid ${kNearest === k ? '#c084fc' : 'var(--border-subtle)'}`,
                borderRadius: '6px',
                padding: '3px 7px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              title={`Consider top-${k} nearest neighbors within radius`}
            >
              k={k}
            </button>
          ))}
        </div>
      </div>

      {/* 2. Split Responsive Legend: SENSOR HEALTH vs EVENT STATE */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '16px',
        padding: '8px 12px',
        background: 'rgba(0, 0, 0, 0.28)',
        borderRadius: '8px',
        border: '1px solid var(--border-subtle)',
        marginBottom: '10px',
        fontSize: '11px',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        {/* Row A: Sensor Health Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '10px' }}>
            SENSOR HEALTH:
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: '#e2e8f0' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--status-healthy)', boxShadow: '0 0 6px var(--status-healthy)' }} /> Healthy
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: '#e2e8f0' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--status-watch)' }} /> Watch
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: '#e2e8f0' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--status-degraded)' }} /> Degraded
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: '#e2e8f0' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--status-critical)' }} /> Critical
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: '#e2e8f0' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--status-offline)' }} /> Offline
          </span>
        </div>

        {/* Row B: Event State Legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
          <span style={{ fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '10px' }}>
            EVENT:
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#c084fc' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', border: '2px solid #a855f7', background: 'rgba(168, 85, 247, 0.2)' }} /> Weather Event
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#f87171' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', border: '2px solid #ef4444', background: 'rgba(239, 68, 68, 0.2)' }} /> Sensor Anomaly
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: '#38bdf8' }}>
            <span style={{ width: '12px', height: '12px', borderRadius: '50%', border: '2px dashed #38bdf8', background: 'transparent' }} /> Comm Fault
          </span>
        </div>
      </div>

      {/* 3. SVG Canvas Map */}
      <div style={{
        flex: 1,
        position: 'relative',
        background: 'radial-gradient(ellipse at center, rgba(14, 25, 45, 0.7) 0%, rgba(8, 12, 20, 0.98) 100%)',
        borderRadius: '10px',
        overflow: 'hidden',
        border: '1px solid var(--border-subtle)',
        minHeight: '350px'
      }}>
        
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          style={{ position: 'absolute', inset: 0 }}
        >
          <defs>
            {/* Background Grid Pattern */}
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255, 255, 255, 0.025)" strokeWidth="1" />
            </pattern>

            {/* Glowing filters for active events and corroborating edges */}
            <filter id="glow-purple" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            <filter id="glow-red" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>

            <filter id="glow-cyan" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="2.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Grid Background */}
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Geographical 150 km Radius Circle around inspected station */}
          {radiusOverlay && (
            <g>
              <ellipse
                cx={radiusOverlay.x}
                cy={radiusOverlay.y}
                rx={radiusOverlay.rx}
                ry={radiusOverlay.ry}
                fill="rgba(56, 189, 248, 0.04)"
                stroke="rgba(56, 189, 248, 0.35)"
                strokeWidth="1.5"
                strokeDasharray="6 4"
              />
              <text
                x={radiusOverlay.x}
                y={radiusOverlay.y + radiusOverlay.ry + 14}
                textAnchor="middle"
                fill="rgba(56, 189, 248, 0.8)"
                fontSize="10"
                fontFamily="JetBrains Mono"
                fontWeight="500"
              >
                Analysis radius: {radiusKm} km
              </text>
            </g>
          )}

          {/* North Compass Indicator (Top Right) */}
          <g transform={`translate(${svgWidth - 45}, 40)`} opacity="0.85">
            <circle cx="0" cy="0" r="16" fill="rgba(14, 21, 36, 0.7)" stroke="rgba(255, 255, 255, 0.15)" strokeWidth="1" />
            <polygon points="0,-12 4,2 0,0 -4,2" fill="#38bdf8" />
            <polygon points="0,12 4,0 0,0 -4,0" fill="rgba(255, 255, 255, 0.3)" />
            <text x="0" y="-14" textAnchor="middle" fill="#38bdf8" fontSize="10" fontWeight="700" fontFamily="JetBrains Mono">
              N
            </text>
          </g>

          {/* Authoritative Spatial Topology Edges (Haversine Distance) */}
          {authoritativeEdges.map((edge) => {
            if (!edge) return null;
            return (
              <g key={`${edge.source}-${edge.target}`}>
                <line
                  x1={edge.x1}
                  y1={edge.y1}
                  x2={edge.x2}
                  y2={edge.y2}
                  stroke={edge.isCorroborating ? '#c084fc' : 'rgba(56, 189, 248, 0.22)'}
                  strokeWidth={edge.isCorroborating ? '2.5' : '1.2'}
                  strokeDasharray={edge.isCorroborating ? 'none' : '4 4'}
                  className={edge.isCorroborating ? 'edge-corroborating' : undefined}
                  filter={edge.isCorroborating ? 'url(#glow-purple)' : undefined}
                />
                {/* Distance Indicator on Corroborating or Selected Edges */}
                {(edge.isCorroborating || activeStation?.station_id === edge.source || activeStation?.station_id === edge.target) && (
                  <text
                    x={(edge.x1 + edge.x2) / 2}
                    y={(edge.y1 + edge.y2) / 2 - 4}
                    textAnchor="middle"
                    fill={edge.isCorroborating ? '#e9d5ff' : 'rgba(148, 163, 184, 0.7)'}
                    fontSize="9"
                    fontFamily="JetBrains Mono"
                    style={{ textShadow: '0 1px 3px rgba(0,0,0,0.9)' }}
                  >
                    {edge.distance_km} km
                  </text>
                )}
              </g>
            );
          })}

          {/* Station Nodes: TWO-LAYER STATUS SYSTEM */}
          {mergedStations.map((st) => {
            const { x, y } = project(st.latitude, st.longitude);
            const healthColor = getHealthColor(st.health_status);
            
            const isSelected = selectedStationId === st.station_id;
            const isHovered = hoveredStationId === st.station_id;
            
            // Event states (independent from physical sensor health!)
            const isWeatherEvent = st.latest_decision === 'WEATHER_EVENT';
            const isSensorAnomaly = st.latest_decision === 'SENSOR_ANOMALY';
            const isCommFault = st.latest_decision === 'COMMUNICATION_ERROR' || st.communication_state === 'OFFLINE' || st.health_status === 'OFFLINE';
            const isZeroNeighbors = st.neighbor_count === 0;
            const isLowEvidence = st.neighbor_count === 1;

            const accessibleLabel = `${st.station_id}, ${st.name}, Sensor Health ${st.health_status}, Event ${st.latest_decision || 'NORMAL'}, ${st.neighbor_count} valid neighbors within ${radiusKm}km`;

            return (
              <g
                key={st.station_id}
                role="button"
                tabIndex={0}
                aria-label={accessibleLabel}
                style={{ cursor: 'pointer' }}
                onClick={() => onSelectStation(st.station_id)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelectStation(st.station_id); }}
                onMouseEnter={() => setHoveredStationId(st.station_id)}
                onMouseLeave={() => setHoveredStationId(null)}
              >
                {/* 1. SELECTION HIGHLIGHT CIRCLE */}
                {isSelected && (
                  <circle
                    cx={x}
                    cy={y}
                    r={24}
                    fill="none"
                    stroke="var(--accent-cyan)"
                    strokeWidth="1.5"
                    strokeDasharray="4 2"
                    opacity="0.9"
                  />
                )}

                {/* 2. LAYER B: EVENT MARKER / OUTER RING */}
                {isWeatherEvent && (
                  <circle
                    cx={x}
                    cy={y}
                    r={16}
                    fill="none"
                    stroke="#c084fc"
                    strokeWidth="2.2"
                    className="event-ring-weather"
                    filter="url(#glow-purple)"
                  />
                )}

                {isSensorAnomaly && (
                  <circle
                    cx={x}
                    cy={y}
                    r={16}
                    fill="none"
                    stroke="#ef4444"
                    strokeWidth="2.2"
                    className="alert-pulse"
                    filter="url(#glow-red)"
                  />
                )}

                {isCommFault && !isSensorAnomaly && (
                  <circle
                    cx={x}
                    cy={y}
                    r={15}
                    fill="none"
                    stroke="#38bdf8"
                    strokeWidth="1.8"
                    strokeDasharray="3 2"
                    className="alert-pulse"
                  />
                )}

                {/* 3. LAYER A: SENSOR HEALTH BASE NODE */}
                {/* Soft Health Halo */}
                <circle
                  cx={x}
                  cy={y}
                  r={isHovered ? 12 : 9}
                  fill={healthColor}
                  fillOpacity={isHovered ? 0.35 : 0.18}
                  stroke={healthColor}
                  strokeWidth={isHovered ? 2 : 1.2}
                  style={{ transition: 'all 0.15s ease' }}
                />

                {/* Core Health Node */}
                <circle
                  cx={x}
                  cy={y}
                  r={5}
                  fill={healthColor}
                  stroke="#080c14"
                  strokeWidth="1.5"
                />

                {/* Station ID Label */}
                <text
                  x={x}
                  y={y - 12}
                  textAnchor="middle"
                  fill={st.health_status === 'OFFLINE' ? '#94a3b8' : '#f1f5f9'}
                  fontSize="10"
                  fontFamily="JetBrains Mono"
                  fontWeight={isSelected || isHovered ? '700' : '600'}
                  style={{ textShadow: '0 1px 4px rgba(0,0,0,0.9)' }}
                >
                  {st.station_id}
                </text>

                {/* Zero Neighbor & Low Evidence Honest Tags */}
                {isZeroNeighbors && (
                  <text
                    x={x}
                    y={y + 16}
                    textAnchor="middle"
                    fill="#f59e0b"
                    fontSize="8.5"
                    fontFamily="JetBrains Mono"
                    fontWeight="600"
                    style={{ textShadow: '0 1px 3px rgba(0,0,0,0.9)' }}
                  >
                    [0 NBR]
                  </text>
                )}
                {isLowEvidence && (
                  <text
                    x={x}
                    y={y + 16}
                    textAnchor="middle"
                    fill="#94a3b8"
                    fontSize="8.5"
                    fontFamily="JetBrains Mono"
                    fontWeight="600"
                    style={{ textShadow: '0 1px 3px rgba(0,0,0,0.9)' }}
                  >
                    [1 NBR]
                  </text>
                )}
              </g>
            );
          })}
        </svg>

        {/* 4. Rich Real-Time Spatial & Health Tooltip Inspector */}
        {activeStation && (
          <div
            className="glass-panel"
            style={{
              position: 'absolute',
              bottom: '14px',
              left: '14px',
              padding: '12px 16px',
              maxWidth: '360px',
              border: '1px solid var(--border-glow)',
              boxShadow: '0 12px 30px rgba(0, 0, 0, 0.75)',
              background: 'rgba(10, 16, 28, 0.95)',
              borderRadius: '10px',
              pointerEvents: 'none',
              zIndex: 10
            }}
          >
            {/* Header: Station ID & Name */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ fontSize: '13px', fontWeight: 700, color: '#fff' }}>
                {activeStation.station_id} &bull; {activeStation.name}
              </span>
            </div>

            {/* Two-Layer Badges: Health vs Event vs Comm */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginBottom: '8px' }}>
              {/* Sensor Health Badge */}
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: activeStation.health_status === 'HEALTHY' ? 'rgba(16, 185, 129, 0.2)' :
                              activeStation.health_status === 'WATCH' ? 'rgba(245, 158, 11, 0.2)' :
                              activeStation.health_status === 'DEGRADED' ? 'rgba(249, 115, 22, 0.2)' :
                              activeStation.health_status === 'CRITICAL' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(100, 116, 139, 0.2)',
                  color: getHealthColor(activeStation.health_status),
                  border: `1px solid ${getHealthColor(activeStation.health_status)}`
                }}
              >
                HEALTH: {activeStation.health_status}
              </span>

              {/* Event Badge */}
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: activeStation.latest_decision === 'WEATHER_EVENT' ? 'rgba(168, 85, 247, 0.2)' :
                              activeStation.latest_decision === 'SENSOR_ANOMALY' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                  color: activeStation.latest_decision === 'WEATHER_EVENT' ? '#c084fc' :
                         activeStation.latest_decision === 'SENSOR_ANOMALY' ? '#f87171' : 'var(--text-muted)',
                  border: `1px solid ${activeStation.latest_decision === 'WEATHER_EVENT' ? '#c084fc' :
                                       activeStation.latest_decision === 'SENSOR_ANOMALY' ? '#f87171' : 'var(--border-subtle)'}`
                }}
              >
                EVENT: {activeStation.latest_decision || 'NORMAL'}
              </span>

              {/* Communication State */}
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 600,
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: activeStation.communication_state === 'OFFLINE' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 189, 248, 0.1)',
                  color: activeStation.communication_state === 'OFFLINE' ? '#f87171' : 'var(--accent-cyan)'
                }}
              >
                COMM: {activeStation.communication_state}
              </span>
            </div>

            {/* Offline Details if applicable */}
            {activeStation.communication_state === 'OFFLINE' && (
              <div style={{ fontSize: '10px', color: '#f87171', background: 'rgba(239, 68, 68, 0.08)', padding: '4px 6px', borderRadius: '4px', marginBottom: '6px' }}>
                Missed intervals: {activeStation.missed_intervals} &bull; Last seen: {activeStation.time_since_last_min}m ago
              </div>
            )}

            {/* Geographical Context & Real Spatial Status */}
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '8px', lineHeight: '1.4' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Region: <strong style={{ color: '#fff' }}>{activeStation.region}</strong> ({activeStation.elevation_m}m ASL)</span>
                <span>Radius: <strong style={{ color: 'var(--accent-cyan)' }}>{radiusKm} km</strong></span>
              </div>
              <div style={{ marginTop: '2px' }}>
                Spatial Context:{' '}
                {activeStation.neighbor_count === 0 ? (
                  <strong style={{ color: '#f59e0b' }}>NO VALID NEIGHBORS (INSUFFICIENT EVIDENCE)</strong>
                ) : activeStation.neighbor_count === 1 ? (
                  <strong style={{ color: '#94a3b8' }}>1 VALID NEIGHBOR (LOW EVIDENCE)</strong>
                ) : (
                  <strong style={{ color: '#10b981' }}>
                    {activeStation.neighbor_count} / {topology?.k_nearest_neighbors || kNearest} valid neighbors
                    {activeStation.spatial_evidence ? ` &bull; Agreement: ${Math.round((activeStation.spatial_evidence.agreement_ratio ?? 0) * 100)}%` : ''}
                  </strong>
                )}
              </div>
            </div>

            {/* Telemetry Measurements */}
            {activeStation.latest_reading ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px', fontSize: '11px', background: 'rgba(0,0,0,0.3)', padding: '6px 8px', borderRadius: '6px', marginBottom: '6px' }} className="mono">
                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '9px' }}>TEMP</span>
                  <span style={{ fontWeight: 700, color: '#fff' }}>{activeStation.latest_reading.temperature ?? 'N/A'}°C</span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '9px' }}>PRES</span>
                  <span style={{ fontWeight: 700, color: '#fff' }}>{activeStation.latest_reading.pressure ?? 'N/A'} hPa</span>
                </div>
                <div>
                  <span style={{ color: 'var(--text-dim)', display: 'block', fontSize: '9px' }}>HUM</span>
                  <span style={{ fontWeight: 700, color: '#fff' }}>{activeStation.latest_reading.humidity ?? 'N/A'}%</span>
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginBottom: '6px' }}>
                Awaiting telemetry reading...
              </div>
            )}

            {/* Spatial Evidence Details during Weather Event / Anomaly */}
            {activeStation.spatial_evidence && activeStation.neighbor_count > 0 && (
              <div style={{ fontSize: '10px', color: 'var(--text-dim)', borderTop: '1px solid var(--border-subtle)', paddingTop: '4px', display: 'flex', justifyContent: 'space-between' }}>
                <span>Corroborating: <strong style={{ color: '#c084fc' }}>{activeStation.spatial_evidence.corroborating_stations_count} / {activeStation.neighbor_count}</strong></span>
                <span>Regional Event: <strong style={{ color: activeStation.spatial_evidence.regional_event_detected ? '#c084fc' : '#94a3b8' }}>{activeStation.spatial_evidence.regional_event_detected ? 'CONFIRMED' : 'NO'}</strong></span>
              </div>
            )}

            <div style={{ fontSize: '9.5px', color: 'var(--accent-cyan)', marginTop: '4px', textAlign: 'right' }}>
              Click node to inspect full telemetry & history &rarr;
            </div>
          </div>
        )}

      </div>
    </div>
  );
};

import React, { useState, useCallback, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  applyNodeChanges,
  applyEdgeChanges,
  Handle,
  Position,
  NodeChange,
  EdgeChange,
  BackgroundVariant
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Monitor,
  Server,
  TerminalSquare,
  Database,
  Activity,
  Zap,
  Globe,
  Shield,
  Folder,
  FileText,
  Share2,
  Bell,
  Lock,
  Archive,
  Image,
  Search,
  User
} from 'lucide-react';

// --- Architecture metadata shown when a node is selected ---
const getMetricsForNode = (nodeId: string) => {
  const metricsMap: Record<string, { desc: string; stat: string }> = {
    user: { desc: 'Dashboard User', stat: 'Web Client' },
    web: { desc: 'Next.js App', stat: 'React Frontend Dashboard' },
    api: { desc: 'FastAPI Backend', stat: 'RESTful API & Auth' },
    analytics: { desc: 'Analytics Service', stat: 'Metrics & SSE Streams' },
    airflow: { desc: 'Apache Airflow', stat: 'DAG Orchestrator' },
    crawlers: { desc: 'Scrapy Crawlers', stat: 'Distributed News Spiders' },
    sources: { desc: 'External Sources', stat: 'News Sites & Social Media' },
    kafka: { desc: 'Apache Kafka', stat: 'Message Broker (Pub/Sub)' },
    spark: { desc: 'Spark Streaming', stat: 'Real-time NLP Pipeline' },
    nlp: { desc: 'PhoBERT Engine', stat: 'NER & Sentiment Analysis' },
    alerts: { desc: 'Alerting System', stat: 'Telegram Notifications' },
    clickhouse: { desc: 'ClickHouse', stat: 'OLAP Data Warehouse' },
    mongo: { desc: 'MongoDB', stat: 'Raw Data & Auth Store' },
  };
  return metricsMap[nodeId] || { desc: 'System Component', stat: 'Healthy' };
};

// --- Custom Node Component ---
const CustomNode = ({ id, data }: any) => {
  const [showMetrics, setShowMetrics] = useState(false);
  const health = data.health || 'documented';
  const isHealthy = health !== 'unhealthy';

  // Icons mapping
  const IconMap: any = {
    monitor: Monitor,
    globe: Globe,
    server: Server,
    terminal: TerminalSquare,
    database: Database,
    activity: Activity,
    zap: Zap,
    shield: Shield,
    folder: Folder,
    filetext: FileText,
    share: Share2,
    bell: Bell,
    lock: Lock,
    archive: Archive,
    image: Image,
    search: Search,
    user: User
  };
  
  const Icon = IconMap[data.icon] || Server;

  const handleClick = () => setShowMetrics(!showMetrics);

  const metrics = getMetricsForNode(id);

  return (
    <div
      onClick={handleClick}
      style={{
        padding: '12px 16px',
        borderRadius: '12px',
        background: isHealthy ? 'rgba(30, 41, 59, 0.9)' : 'rgba(127, 29, 29, 0.9)',
        border: `2px solid ${isHealthy ? data.color || '#475569' : '#ef4444'}`,
        color: '#fff',
        width: '200px',
        boxShadow: isHealthy ? '0 4px 6px -1px rgba(0, 0, 0, 0.3)' : '0 0 15px rgba(239, 68, 68, 0.7)',
        position: 'relative',
        transition: 'all 0.3s ease',
        cursor: 'pointer'
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: '#94a3b8' }} />
      
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
        <div style={{ padding: '8px', background: 'rgba(255,255,255,0.1)', borderRadius: '8px', display: 'flex' }}>
          <Icon size={20} color={isHealthy ? (data.color || '#fff') : '#fff'} />
        </div>
        <div>
          <div style={{ fontWeight: 600, fontSize: '14px' }}>{data.label}</div>
          <div style={{ fontSize: '11px', color: '#cbd5e1' }}>{data.sublabel}</div>
        </div>
      </div>

      {/* Health Status Indicator */}
      <div style={{
        position: 'absolute', top: '-6px', right: '-6px',
        width: '14px', height: '14px', borderRadius: '50%',
        background: health === 'healthy' ? '#22c55e' : health === 'unhealthy' ? '#ef4444' : '#64748b',
        border: '2px solid #0f172a',
        boxShadow: health === 'healthy' ? '0 0 8px #22c55e' : health === 'unhealthy' ? '0 0 8px #ef4444' : 'none',
        animation: health === 'unhealthy' ? 'pulse 1s infinite' : 'none'
      }} />

      {/* Metrics Tooltip */}
      {showMetrics && (
        <div style={{
          position: 'absolute', top: '105%', left: 0, width: '100%',
          background: 'rgba(15, 23, 42, 0.95)', border: '1px solid #334155',
          borderRadius: '8px', padding: '10px', fontSize: '12px', zIndex: 50,
          boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.5)'
        }}>
          <div style={{ color: '#94a3b8', marginBottom: '4px' }}>{metrics.desc}</div>
          <div style={{ fontWeight: 'bold', color: '#38bdf8' }}>{metrics.stat}</div>
        </div>
      )}

      <Handle type="source" position={Position.Bottom} style={{ background: '#94a3b8' }} />
    </div>
  );
};

const nodeTypes = {
  custom: CustomNode,
};

// --- Initial Nodes Data ---
const initialNodes: any[] = [
  // Layer 1
  { id: 'user', type: 'custom', position: { x: 750, y: 0 }, data: { label: 'Dashboard User', sublabel: 'Client', icon: 'user', color: '#3b82f6' } },
  { id: 'sources', type: 'custom', position: { x: 150, y: 0 }, data: { label: 'Data Sources', sublabel: 'News / Social Media', icon: 'globe', color: '#10b981' } },
  
  // Layer 2
  { id: 'web', type: 'custom', position: { x: 750, y: 120 }, data: { label: 'Next.js Frontend', sublabel: 'Web Dashboard', icon: 'monitor', color: '#3b82f6' } },
  { id: 'crawlers', type: 'custom', position: { x: 150, y: 120 }, data: { label: 'Scrapy Crawlers', sublabel: 'Data Collection', icon: 'terminal', color: '#3b82f6' } },

  // Layer 3
  { id: 'api', type: 'custom', position: { x: 750, y: 240 }, data: { label: 'FastAPI Backend', sublabel: 'API Gateway', icon: 'shield', color: '#f59e0b' } },
  { id: 'airflow', type: 'custom', position: { x: 450, y: 240 }, data: { label: 'Apache Airflow', sublabel: 'Orchestrator', icon: 'server', color: '#10b981' } },
  
  // Layer 4
  { id: 'analytics', type: 'custom', position: { x: 900, y: 360 }, data: { label: 'Analytics API', sublabel: 'Services & Auth', icon: 'activity', color: '#f59e0b' } },
  { id: 'alerts', type: 'custom', position: { x: 600, y: 360 }, data: { label: 'Anomaly Alerts', sublabel: 'Quality & Telegram', icon: 'bell', color: '#10b981' } },
  { id: 'kafka', type: 'custom', position: { x: 300, y: 360 }, data: { label: 'Kafka Broker', sublabel: 'Event Streaming', icon: 'zap', color: '#ef4444' } },
  
  // Layer 5
  { id: 'spark', type: 'custom', position: { x: 300, y: 480 }, data: { label: 'Spark Streaming', sublabel: 'Real-time Processing', icon: 'server', color: '#f59e0b' } },
  
  // Layer 6
  { id: 'nlp', type: 'custom', position: { x: 300, y: 600 }, data: { label: 'PhoBERT NLP', sublabel: 'Entities & Sentiment', icon: 'activity', color: '#f59e0b' } },
  
  // Layer 7 Databases
  { id: 'mongo', type: 'custom', position: { x: 150, y: 720 }, data: { label: 'MongoDB', sublabel: 'Raw Data & Users', icon: 'database', color: '#ef4444' } },
  { id: 'clickhouse', type: 'custom', position: { x: 750, y: 720 }, data: { label: 'ClickHouse', sublabel: 'OLAP Data Warehouse', icon: 'database', color: '#ef4444' } },
];

const defaultEdgeOptions = {
  animated: true,
  markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8' },
  style: { strokeWidth: 2, stroke: '#94a3b8' },
  labelStyle: { fill: '#fff', fontWeight: 600, fontSize: 11 },
  labelBgStyle: { fill: '#1e293b', fillOpacity: 0.8 },
};

const blueLine = { strokeWidth: 2, stroke: '#3b82f6' };
const amberLine = { strokeWidth: 2, stroke: '#f59e0b' };
const greenLine = { strokeWidth: 2, stroke: '#10b981' };
const redLine = { strokeWidth: 2, stroke: '#ef4444' };
const dashedLine = { strokeDasharray: '5,5' };

const initialEdges: any[] = [
  { id: 'e-user-web', source: 'user', target: 'web', label: 'HTTP', ...defaultEdgeOptions, style: blueLine },
  { id: 'e-web-api', source: 'web', target: 'api', label: 'REST requests', ...defaultEdgeOptions, style: blueLine, type: 'smoothstep' },
  { id: 'e-api-analytics', source: 'api', target: 'analytics', label: 'dispatch', ...defaultEdgeOptions, style: amberLine, type: 'smoothstep' },
  { id: 'e-analytics-clickhouse', source: 'analytics', target: 'clickhouse', label: 'SQL query', ...defaultEdgeOptions, style: amberLine, type: 'smoothstep' },
  { id: 'e-api-mongo', source: 'api', target: 'mongo', label: 'Auth state', ...defaultEdgeOptions, style: amberLine, type: 'smoothstep' },
  
  { id: 'e-sources-crawlers', source: 'sources', target: 'crawlers', label: 'scrape', ...defaultEdgeOptions, style: greenLine },
  { id: 'e-airflow-crawlers', source: 'airflow', target: 'crawlers', label: 'schedule', ...defaultEdgeOptions, style: { ...greenLine, ...dashedLine }, type: 'smoothstep' },
  { id: 'e-crawlers-mongo', source: 'crawlers', target: 'mongo', label: 'raw items', ...defaultEdgeOptions, style: greenLine, type: 'smoothstep' },
  { id: 'e-crawlers-kafka', source: 'crawlers', target: 'kafka', label: 'publish', ...defaultEdgeOptions, style: redLine, type: 'smoothstep' },
  
  { id: 'e-airflow-alerts', source: 'airflow', target: 'alerts', label: 'trigger', ...defaultEdgeOptions, style: { ...greenLine, ...dashedLine }, type: 'smoothstep' },
  { id: 'e-alerts-clickhouse', source: 'alerts', target: 'clickhouse', label: 'anomaly metrics', ...defaultEdgeOptions, style: greenLine, type: 'smoothstep' },
  
  { id: 'e-kafka-spark', source: 'kafka', target: 'spark', label: 'consume stream', ...defaultEdgeOptions, style: redLine, type: 'smoothstep' },
  { id: 'e-spark-nlp', source: 'spark', target: 'nlp', label: 'apply ML', ...defaultEdgeOptions, style: amberLine, type: 'smoothstep' },
  { id: 'e-spark-clickhouse', source: 'spark', target: 'clickhouse', label: 'sink data', ...defaultEdgeOptions, style: amberLine, type: 'smoothstep' },
  { id: 'e-nlp-clickhouse', source: 'nlp', target: 'clickhouse', label: 'sink enriched', ...defaultEdgeOptions, style: amberLine, type: 'smoothstep' },
];

import { API_BASE } from "@/lib/api";

export default function ArchitectureTab() {
  const [nodes, setNodes] = useState(initialNodes);
  const [edges, setEdges] = useState(initialEdges);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  useEffect(() => {
    const checkHealth = async () => {
      const baseUrl = API_BASE.replace("/api/v1", "");
      const targets = { api: `${baseUrl}/health/ready` };
      const results = await Promise.all(Object.entries(targets).map(async ([id, url]) => {
        try { const response = await fetch(url, { cache: 'no-store' }); return [id, response.ok ? 'healthy' : 'unhealthy']; }
        catch { return [id, 'unhealthy']; }
      }));
      setNodes((current: any[]) => current.map((node: any) => {
        const result = results.find(([id]) => id === node.id);
        return result ? { ...node, data: { ...node.data, health: result[1] } } : node;
      }));
      setLastChecked(new Date());
    };
    void checkHealth();
    const timer = window.setInterval(checkHealth, 30000);
    return () => window.clearInterval(timer);
  }, []);

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setNodes((nds: any) => applyNodeChanges(changes, nds)),
    []
  );
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setEdges((eds: any) => applyEdgeChanges(changes, eds)),
    []
  );

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '24px', margin: '0 0 8px 0', fontWeight: 'bold', color: '#f8fafc' }}>NewsPulse Live Architecture</h2>
          <p style={{ color: '#94a3b8', margin: 0 }}>
            Live topology based on <code style={{background: '#1e293b', padding: '2px 6px', borderRadius: '4px'}}>ARCHITECTURE.md</code>. <span style={{ color: '#38bdf8' }}>Click</span> a node to inspect its role.
          </p>
          <div style={{ display: 'flex', gap: '14px', marginTop: '10px', color: '#94a3b8', fontSize: '12px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{width: 8, height: 8, borderRadius: 4, background: '#22c55e'}}/> Live health</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><div style={{width: 8, height: 8, borderRadius: 4, background: '#64748b'}}/> Documented component</span>
            {lastChecked && <span>Checked {lastChecked.toLocaleTimeString()}</span>}
          </div>
        </div>
      </div>

      {/* React Flow Canvas container */}
      <div style={{ height: '700px', width: '100%', background: '#0b0f19', borderRadius: '16px', border: '1px solid #1e293b', overflow: 'hidden' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          attributionPosition="bottom-left"
          defaultEdgeOptions={defaultEdgeOptions}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#334155" />
          <Controls style={{ background: '#1e293b', color: '#fff', fill: '#fff', border: '1px solid #334155' }} />
        </ReactFlow>
      </div>
      
      {/* CSS for pulse animation */}
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes pulse {
          0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
          70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
          100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
        }
        .react-flow__attribution { background: transparent !important; }
        .react-flow__attribution a { color: #475569 !important; }
      `}} />
    </div>
  );
}

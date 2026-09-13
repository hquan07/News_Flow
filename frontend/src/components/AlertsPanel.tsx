import React, { useState, useEffect, useRef } from 'react';
import { AlertTriangle, Clock, Activity, TrendingUp, ShieldAlert, Zap, Settings, Save, X } from 'lucide-react';

interface SpikeAlert {
  hour_slot: string;
  article_count: number;
  avg_count: number;
}

interface SocialCrisisAlert {
  source: string;
  total_posts: number;
  negative_posts: number;
  negative_pct: number;
}

interface ViralPostAlert {
  post_id: string;
  source: string;
  title: string;
  interactions: number;
  sentiment_label: string;
}

interface AlertThresholds {
  crisis_negative_pct: number;
  crisis_min_posts: number;
  viral_interactions: number;
}

const API_BASE = 'http://localhost:8001/api/v1';

const AlertsPanel: React.FC = () => {
  const [spikes, setSpikes] = useState<SpikeAlert[]>([]);
  const [crisisAlerts, setCrisisAlerts] = useState<SocialCrisisAlert[]>([]);
  const [viralAlerts, setViralAlerts] = useState<ViralPostAlert[]>([]);
  const [thresholds, setThresholds] = useState<AlertThresholds>({
    crisis_negative_pct: 30.0,
    crisis_min_posts: 10,
    viral_interactions: 50
  });
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const sseRef = useRef<EventSource | null>(null);

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const [resSpikes, resSocial, resConfig] = await Promise.all([
        fetch(`${API_BASE}/alerts?threshold=1.0&limit=10`),
        fetch(`${API_BASE}/alerts/social`),
        fetch(`${API_BASE}/alerts/config`)
      ]);
      
      if (resSpikes.ok) {
        const data = await resSpikes.json();
        setSpikes(data.spikes || []);
      }
      if (resSocial.ok) {
        const data = await resSocial.json();
        setCrisisAlerts(data.crisis_alerts || []);
        setViralAlerts(data.viral_alerts || []);
      }
      if (resConfig.ok) {
        const data = await resConfig.json();
        setThresholds(data);
      }
      setError(null);
    } catch (err: any) {
      setError('Failed to fetch alerts.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();

    // Setup SSE for real-time alerts
    const es = new EventSource(`${API_BASE}/stream/`);
    sseRef.current = es;

    es.addEventListener('alert', (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'social_alerts') {
          if (data.crisis) setCrisisAlerts(data.crisis);
          if (data.viral) setViralAlerts(data.viral);
        }
      } catch (e) {}
    });

    return () => {
      es.close();
    };
  }, []);

  const handleSaveConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(thresholds)
      });
      if (res.ok) {
        setShowConfig(false);
        fetchAlerts(); // Re-fetch alerts with new config
      }
    } catch (e) {
      alert("Failed to save config");
    }
  };

  if (loading && spikes.length === 0 && crisisAlerts.length === 0 && viralAlerts.length === 0) {
    return (
      <div className="glass-panel alerts-container loading">
        <div className="pulse-loader"></div>
        <p>Scanning for anomalies & crisis...</p>
      </div>
    );
  }

  return (
    <div className="alerts-wrapper">
      <div className="alerts-header glass-panel flex justify-between items-center" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2><Activity size={24} className="icon-pulse" /> System Alerts & Anomalies</h2>
          <p>Real-time detection of unusual spikes, social crisis, and viral trends</p>
        </div>
        <button className="btn btn-secondary" onClick={() => setShowConfig(!showConfig)}>
          <Settings size={18} /> Configure
        </button>
      </div>

      {showConfig && (
        <div className="glass-panel config-panel" style={{ marginBottom: '20px', padding: '20px', background: 'rgba(255,255,255,0.05)', borderRadius: '12px' }}>
          <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '15px' }}>
            <Settings size={20} /> Alert Thresholds
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
            <div>
              <label>Crisis: Min Negative %</label>
              <input type="number" className="search-input" value={thresholds.crisis_negative_pct} onChange={e => setThresholds({...thresholds, crisis_negative_pct: parseFloat(e.target.value)})} style={{ width: '100%', marginTop: '5px' }} />
            </div>
            <div>
              <label>Crisis: Min Posts</label>
              <input type="number" className="search-input" value={thresholds.crisis_min_posts} onChange={e => setThresholds({...thresholds, crisis_min_posts: parseInt(e.target.value)})} style={{ width: '100%', marginTop: '5px' }} />
            </div>
            <div>
              <label>Viral: Min Interactions</label>
              <input type="number" className="search-input" value={thresholds.viral_interactions} onChange={e => setThresholds({...thresholds, viral_interactions: parseInt(e.target.value)})} style={{ width: '100%', marginTop: '5px' }} />
            </div>
          </div>
          <div style={{ marginTop: '20px', display: 'flex', gap: '10px' }}>
            <button className="btn btn-primary" onClick={handleSaveConfig}><Save size={16} /> Save</button>
            <button className="btn btn-secondary" onClick={() => setShowConfig(false)}><X size={16} /> Cancel</button>
          </div>
        </div>
      )}

      {/* Social Crisis Alerts */}
      {crisisAlerts.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ color: '#ef4444', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <ShieldAlert size={20} /> Active Social Crisis
          </h3>
          <div className="alerts-grid">
            {crisisAlerts.map((crisis, idx) => (
              <div key={idx} className="alert-card glass-panel severity-high" style={{ borderColor: 'rgba(239, 68, 68, 0.5)' }}>
                <div className="alert-card-header">
                  <div className="alert-time"><ShieldAlert size={16} /> {crisis.source}</div>
                  <div className="alert-badge" style={{ background: '#ef4444' }}>Crisis</div>
                </div>
                <div className="alert-stats">
                  <div className="stat-box">
                    <span className="stat-label">Total Posts</span>
                    <span className="stat-value">{crisis.total_posts}</span>
                  </div>
                  <div className="stat-box highlight">
                    <span className="stat-label" style={{ color: '#ef4444' }}>Negative</span>
                    <span className="stat-value" style={{ color: '#ef4444' }}>{crisis.negative_pct}%</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Viral Post Alerts */}
      {viralAlerts.length > 0 && (
        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ color: '#f59e0b', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <Zap size={20} /> Viral Posts Detected
          </h3>
          <div className="alerts-grid">
            {viralAlerts.map((viral, idx) => (
              <div key={idx} className="alert-card glass-panel severity-medium" style={{ borderColor: 'rgba(245, 158, 11, 0.5)' }}>
                <div className="alert-card-header">
                  <div className="alert-time"><Zap size={16} /> {viral.source}</div>
                  <div className="alert-badge" style={{ background: '#f59e0b' }}>Viral</div>
                </div>
                <p style={{ margin: '10px 0', fontSize: '14px', color: '#e2e8f0', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{viral.title}</p>
                <div className="alert-stats">
                  <div className="stat-box highlight">
                    <span className="stat-label" style={{ color: '#f59e0b' }}>Interactions</span>
                    <span className="stat-value" style={{ color: '#f59e0b' }}>{viral.interactions}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* News Volume Spikes */}
      <div>
        <h3 style={{ color: '#8b5cf6', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
          <TrendingUp size={20} /> Volume Spikes
        </h3>
        <div className="alerts-grid">
          {spikes.length === 0 ? (
            <div className="glass-panel empty-state" style={{ gridColumn: '1 / -1' }}>
              <Activity size={48} className="muted-icon" />
              <p>No volume spikes detected recently.</p>
            </div>
          ) : (
            spikes.map((spike, idx) => {
              const multiplier = spike.article_count / (spike.avg_count || 1);
              const severityClass = multiplier >= 3 ? 'severity-high' : multiplier >= 2 ? 'severity-medium' : 'severity-low';
              return (
                <div key={idx} className={`alert-card glass-panel ${severityClass}`}>
                  <div className="alert-card-header">
                    <div className="alert-time">
                      <Clock size={16} />
                      {new Date(spike.hour_slot).toLocaleString('vi-VN', {
                        day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit'
                      })}
                    </div>
                    <div className="alert-badge"><AlertTriangle size={14} /> Spike Detected</div>
                  </div>
                  <div className="alert-stats">
                    <div className="stat-box primary">
                      <span className="stat-label">Published</span>
                      <span className="stat-value">{spike.article_count}</span>
                    </div>
                    <div className="stat-box highlight">
                      <span className="stat-label">Surge</span>
                      <span className="stat-value flex-center">
                        <TrendingUp size={16} /> {multiplier.toFixed(1)}x
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
};

export default AlertsPanel;

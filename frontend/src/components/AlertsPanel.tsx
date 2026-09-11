import React, { useState, useEffect } from 'react';
import { AlertTriangle, Clock, Activity, TrendingUp } from 'lucide-react';

interface SpikeAlert {
  hour_slot: string;
  article_count: number;
  avg_count: number;
}

const API_BASE = 'http://localhost:8001/api/v1';

const AlertsPanel: React.FC = () => {
  const [spikes, setSpikes] = useState<SpikeAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        setLoading(true);
        const res = await fetch(`${API_BASE}/alerts?threshold=1.5&limit=10`);
        if (!res.ok) throw new Error('Network response was not ok');
        const data = await res.json();
        setSpikes(data.spikes || []);
        setError(null);
      } catch (err: any) {
        setError('Failed to fetch alerts. Please try again later.');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchAlerts();
    const interval = setInterval(fetchAlerts, 60000); // refresh every minute
    return () => clearInterval(interval);
  }, []);

  if (loading && spikes.length === 0) {
    return (
      <div className="glass-panel alerts-container loading">
        <div className="pulse-loader"></div>
        <p>Scanning for anomalies...</p>
      </div>
    );
  }

  if (error && spikes.length === 0) {
    return (
      <div className="glass-panel alerts-container error">
        <AlertTriangle size={32} />
        <p>{error}</p>
      </div>
    );
  }

  return (
    <div className="alerts-wrapper">
      <div className="alerts-header glass-panel">
        <h2>
          <Activity size={24} className="icon-pulse" />
          News Volume Anomalies
        </h2>
        <p>Real-time detection of unusual spikes in news publishing activity</p>
      </div>

      <div className="alerts-grid">
        {spikes.length === 0 ? (
          <div className="glass-panel empty-state">
            <Activity size={48} className="muted-icon" />
            <h3>System Normal</h3>
            <p>No significant volume spikes detected in recent history.</p>
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
                  <div className="alert-badge">
                    <AlertTriangle size={14} />
                    Spike Detected
                  </div>
                </div>
                
                <div className="alert-stats">
                  <div className="stat-box primary">
                    <span className="stat-label">Published</span>
                    <span className="stat-value">{spike.article_count}</span>
                  </div>
                  <div className="stat-box secondary">
                    <span className="stat-label">Average</span>
                    <span className="stat-value">{spike.avg_count}</span>
                  </div>
                  <div className="stat-box highlight">
                    <span className="stat-label">Surge</span>
                    <span className="stat-value flex-center">
                      <TrendingUp size={16} />
                      {multiplier.toFixed(1)}x
                    </span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default AlertsPanel;

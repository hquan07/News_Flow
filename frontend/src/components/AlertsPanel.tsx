"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  AlertTriangle,
  Clock,
  Activity,
  TrendingUp,
  ShieldAlert,
  Zap,
  Settings,
  Save,
  X,
} from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";
import AlertDetailModal from "./AlertDetailModal";
import type {
  ViralPostAlertSummary,
  ViralPostDetail,
  SocialCrisisAlert,
  SpikeAlert,
} from "@/lib/alert-types";

interface AlertThresholds {
  crisis_negative_pct: number;
  crisis_min_posts: number;
  viral_interactions: number;
}

const AlertsPanel: React.FC = () => {
  const [spikes, setSpikes] = useState<SpikeAlert[]>([]);
  const [crisisAlerts, setCrisisAlerts] = useState<SocialCrisisAlert[]>([]);
  const [viralAlerts, setViralAlerts] = useState<ViralPostAlertSummary[]>([]);
  const [thresholds, setThresholds] = useState<AlertThresholds>({
    crisis_negative_pct: 30.0,
    crisis_min_posts: 10,
    viral_interactions: 50,
  });

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showConfig, setShowConfig] = useState(false);
  const sseRef = useRef<EventSource | null>(null);

  // Drill-down state
  const [selectedAlert, setSelectedAlert] =
    useState<ViralPostAlertSummary | null>(null);
  const [alertDetail, setAlertDetail] = useState<ViralPostDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const [spikesData, socialData, configData] = await Promise.all([
        apiFetch<any>(`${API_BASE}/alerts?threshold=1.0&limit=10`),
        apiFetch<any>(`${API_BASE}/alerts/social`),
        apiFetch<AlertThresholds>(`${API_BASE}/alerts/config`),
      ]);

      setSpikes(spikesData.spikes || []);
      setCrisisAlerts(socialData.crisis_alerts || []);

      // Deduplicate by post_id
      const seen = new Set<string>();
      const deduped = (socialData.viral_alerts || []).filter(
        (v: ViralPostAlertSummary) => {
          if (seen.has(v.post_id)) return false;
          seen.add(v.post_id);
          return true;
        }
      );
      setViralAlerts(deduped);
      setThresholds(configData);
      setError(null);
    } catch {
      setError("Failed to fetch alerts.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();

    // Setup SSE for real-time alerts
    const es = new EventSource(`${API_BASE}/stream/`);
    sseRef.current = es;

    es.addEventListener("alert", (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "social_alerts") {
          if (data.crisis) setCrisisAlerts(data.crisis);
          if (data.viral) {
            const seen = new Set<string>();
            const deduped = (data.viral as ViralPostAlertSummary[]).filter(
              (v) => {
                if (seen.has(v.post_id)) return false;
                seen.add(v.post_id);
                return true;
              }
            );
            setViralAlerts(deduped);
          }
        }
      } catch {
        /* ignore parse errors from SSE */
      }
    });

    return () => {
      es.close();
    };
  }, []);

  // --- Drill-down handlers ---
  const handleOpenDetail = useCallback(
    async (alert: ViralPostAlertSummary, btnEl: HTMLButtonElement | null) => {
      // Abort any in-flight detail request
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      triggerRef.current = btnEl;
      setSelectedAlert(alert);
      setAlertDetail(null);
      setDetailLoading(true);
      setDetailError(null);

      try {
        const detail = await apiFetch<ViralPostDetail>(
          `${API_BASE}/alerts/social/posts/${encodeURIComponent(alert.post_id)}`,
          { signal: controller.signal }
        );
        if (!controller.signal.aborted) {
          setAlertDetail(detail);
        }
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        if (err?.status === 404) {
          setDetailError("This post is no longer available.");
        } else {
          setDetailError("Failed to load post details.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setDetailLoading(false);
        }
      }
    },
    []
  );

  const handleCloseDetail = useCallback(() => {
    abortRef.current?.abort();
    setSelectedAlert(null);
    setAlertDetail(null);
    setDetailLoading(false);
    setDetailError(null);
    // Return focus to the trigger card
    triggerRef.current?.focus();
  }, []);

  const handleSaveConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/alerts/config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(thresholds),
      });
      if (res.ok) {
        setShowConfig(false);
        fetchAlerts();
      }
    } catch {
      window.alert("Failed to save config");
    }
  };

  if (
    loading &&
    spikes.length === 0 &&
    crisisAlerts.length === 0 &&
    viralAlerts.length === 0
  ) {
    return (
      <div className="glass-panel alerts-container loading">
        <div className="pulse-loader"></div>
        <p>Scanning for anomalies & crisis...</p>
      </div>
    );
  }

  return (
    <div className="alerts-wrapper">
      <div
        className="alerts-header glass-panel"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h2>
            <Activity size={24} className="icon-pulse" /> System Alerts &
            Anomalies
          </h2>
          <p>
            Real-time detection of unusual spikes, social crisis, and viral
            trends
          </p>
        </div>
        <button
          className="btn btn-secondary"
          onClick={() => setShowConfig(!showConfig)}
        >
          <Settings size={18} /> Configure
        </button>
      </div>
      {error && (
        <p role="alert" className="error-toast">
          {error}
        </p>
      )}

      {showConfig && (
        <div
          className="glass-panel config-panel"
          style={{
            marginBottom: "20px",
            padding: "20px",
            background: "rgba(255,255,255,0.05)",
            borderRadius: "12px",
          }}
        >
          <h3
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginBottom: "15px",
            }}
          >
            <Settings size={20} /> Alert Thresholds
          </h3>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr 1fr",
              gap: "20px",
            }}
          >
            <div>
              <label>Crisis: Min Negative %</label>
              <input
                type="number"
                className="search-input"
                value={thresholds.crisis_negative_pct}
                onChange={(e) =>
                  setThresholds({
                    ...thresholds,
                    crisis_negative_pct: parseFloat(e.target.value),
                  })
                }
                style={{ width: "100%", marginTop: "5px" }}
              />
            </div>
            <div>
              <label>Crisis: Min Posts</label>
              <input
                type="number"
                className="search-input"
                value={thresholds.crisis_min_posts}
                onChange={(e) =>
                  setThresholds({
                    ...thresholds,
                    crisis_min_posts: parseInt(e.target.value),
                  })
                }
                style={{ width: "100%", marginTop: "5px" }}
              />
            </div>
            <div>
              <label>Viral: Min Interactions</label>
              <input
                type="number"
                className="search-input"
                value={thresholds.viral_interactions}
                onChange={(e) =>
                  setThresholds({
                    ...thresholds,
                    viral_interactions: parseInt(e.target.value),
                  })
                }
                style={{ width: "100%", marginTop: "5px" }}
              />
            </div>
          </div>
          <div style={{ marginTop: "20px", display: "flex", gap: "10px" }}>
            <button className="btn btn-primary" onClick={handleSaveConfig}>
              <Save size={16} /> Save
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => setShowConfig(false)}
            >
              <X size={16} /> Cancel
            </button>
          </div>
        </div>
      )}

      {/* Social Crisis Alerts */}
      {crisisAlerts.length > 0 && (
        <div style={{ marginBottom: "20px" }}>
          <h3
            style={{
              color: "#ef4444",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginBottom: "10px",
            }}
          >
            <ShieldAlert size={20} /> Active Social Crisis
          </h3>
          <div className="alerts-grid">
            {crisisAlerts.map((crisis, idx) => (
              <div
                key={idx}
                className="alert-card glass-panel severity-high"
                style={{ borderColor: "rgba(239, 68, 68, 0.5)" }}
              >
                <div className="alert-card-header">
                  <div className="alert-time">
                    <ShieldAlert size={16} /> {crisis.source}
                  </div>
                  <div
                    className="alert-badge"
                    style={{ background: "#ef4444" }}
                  >
                    Crisis
                  </div>
                </div>
                <div className="alert-stats">
                  <div className="stat-box">
                    <span className="stat-label">Total Posts</span>
                    <span className="stat-value">{crisis.total_posts}</span>
                  </div>
                  <div className="stat-box highlight">
                    <span className="stat-label" style={{ color: "#ef4444" }}>
                      Negative
                    </span>
                    <span className="stat-value" style={{ color: "#ef4444" }}>
                      {crisis.negative_pct}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Viral Post Alerts — now interactive */}
      {viralAlerts.length > 0 && (
        <div style={{ marginBottom: "20px" }}>
          <h3
            style={{
              color: "#f59e0b",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              marginBottom: "10px",
            }}
          >
            <Zap size={20} /> Viral Posts Detected
          </h3>
          <div className="alerts-grid">
            {viralAlerts.map((viral) => (
              <button
                key={viral.post_id}
                type="button"
                className="alert-card glass-panel severity-medium alert-card-interactive"
                style={{ borderColor: "rgba(245, 158, 11, 0.5)" }}
                aria-haspopup="dialog"
                aria-expanded={selectedAlert?.post_id === viral.post_id}
                aria-label={`Viral alert: ${viral.data_quality.title_available ? viral.title : viral.source} — ${viral.interactions} interactions`}
                onClick={(e) =>
                  handleOpenDetail(viral, e.currentTarget)
                }
              >
                <div className="alert-card-header">
                  <div className="alert-time">
                    <Zap size={16} /> {viral.source}
                  </div>
                  <div
                    className="alert-badge"
                    style={{ background: "#f59e0b" }}
                  >
                    Viral
                  </div>
                </div>
                {viral.data_quality.title_available && viral.title && (
                  <p className="alert-card-title">{viral.title}</p>
                )}
                {!viral.data_quality.title_available && (
                  <p className="alert-card-title alert-title-unavailable">
                    Trending post on {viral.source}
                  </p>
                )}
                <div className="alert-stats" style={{ display: 'flex', alignItems: 'center', gap: '15px', marginTop: '10px' }}>
                  <div className="stat-box highlight" style={{ flex: 1, padding: '10px', background: 'rgba(245, 158, 11, 0.05)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                    <span className="stat-label" style={{ color: "#f59e0b", fontSize: '10px' }}>
                      INTERACTIONS
                    </span>
                    <span className="stat-value" style={{ color: "#f59e0b", fontSize: '20px' }}>
                      {viral.interactions.toLocaleString()}
                    </span>
                  </div>
                  {viral.publish_time && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px', color: '#94a3b8', fontSize: '12px' }}>
                      <Clock size={14} />
                      {new Date(viral.publish_time).toLocaleTimeString(
                        "vi-VN",
                        { hour: "2-digit", minute: "2-digit" }
                      )}
                    </div>
                  )}
                </div>
                <div className="alert-card-hint">Click for details →</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* News Volume Spikes */}
      <div>
        <h3
          style={{
            color: "#8b5cf6",
            display: "flex",
            alignItems: "center",
            gap: "8px",
            marginBottom: "10px",
          }}
        >
          <TrendingUp size={20} /> Volume Spikes
        </h3>
        <div className="alerts-grid">
          {spikes.length === 0 ? (
            <div
              className="glass-panel empty-state"
              style={{ gridColumn: "1 / -1" }}
            >
              <Activity size={48} className="muted-icon" />
              <p>No volume spikes detected recently.</p>
            </div>
          ) : (
            spikes.map((spike, idx) => {
              const multiplier =
                spike.article_count / (spike.avg_count || 1);
              const severityClass =
                multiplier >= 3
                  ? "severity-high"
                  : multiplier >= 2
                  ? "severity-medium"
                  : "severity-low";
              return (
                <div
                  key={idx}
                  className={`alert-card glass-panel ${severityClass}`}
                >
                  <div className="alert-card-header">
                    <div className="alert-time">
                      <Clock size={16} />
                      {new Date(spike.hour_slot).toLocaleString("vi-VN", {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </div>
                    <div className="alert-badge">
                      <AlertTriangle size={14} /> Spike Detected
                    </div>
                  </div>
                  <div className="alert-stats">
                    <div className="stat-box primary">
                      <span className="stat-label">Published</span>
                      <span className="stat-value">
                        {spike.article_count}
                      </span>
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

      {/* Alert Detail Modal */}
      <AlertDetailModal
        open={!!selectedAlert}
        onClose={handleCloseDetail}
        summary={selectedAlert}
        detail={alertDetail}
        loading={detailLoading}
        error={detailError}
      />
    </div>
  );
};

export default AlertsPanel;

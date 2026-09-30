"use client";

import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from "react";
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
  Pin,
  CheckCircle2,
  Layers3,
} from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";
import AlertDetailModal from "./AlertDetailModal";
import {
  CrisisDetailModal,
  ViralClusterModal,
  VolumeSpikeDetailModal,
} from "./AlertInsightModals";
import type {
  ArticleAlertFilter,
  ViralPostAlertSummary,
  ViralPostDetail,
  SocialCrisisAlert,
  SocialCrisisDetail,
  SpikeAlert,
  VolumeSpikeDetail,
  AlertWorkflowState,
} from "@/lib/alert-types";

interface AlertThresholds {
  crisis_negative_pct: number;
  crisis_min_posts: number;
  viral_interactions: number;
}

interface AlertsPanelProps {
  canManage: boolean;
  liveAlerts?: {
    crisis: SocialCrisisAlert[];
    viral: ViralPostAlertSummary[];
    timestamp: string;
  } | null;
  onOpenArticles: (filter: ArticleAlertFilter) => void;
}

function deduplicateViralAlerts(alerts: ViralPostAlertSummary[]) {
  const seen = new Set<string>();
  return alerts.filter((alert) => {
    if (seen.has(alert.post_id)) return false;
    seen.add(alert.post_id);
    return true;
  });
}

type ViralCluster = {
  id: string;
  source: string;
  posts: ViralPostAlertSummary[];
  interactions: number;
};

function crisisAlertId(alert: SocialCrisisAlert) {
  return alert.alert_id || `crisis:${alert.source}`;
}

function spikeAlertId(alert: SpikeAlert) {
  return alert.alert_id || `volume:${alert.hour_slot}`;
}

function viralTopicKey(alert: ViralPostAlertSummary) {
  if (!alert.data_quality.title_available || !alert.title.trim()) {
    return "unlabelled";
  }
  const words = alert.title
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter((word) => word.length > 2)
    .slice(0, 4);
  return words.join("-") || "unlabelled";
}

function AlertCardActions({
  state,
  onToggle,
}: {
  state?: AlertWorkflowState;
  onToggle: (field: "pinned" | "acknowledged", value: boolean) => void;
}) {
  const pinned = state?.pinned ?? false;
  const acknowledged = state?.acknowledged ?? false;
  return (
    <div className="alert-card-actions">
      <button
        type="button"
        className={pinned ? "active" : ""}
        aria-pressed={pinned}
        onClick={() => onToggle("pinned", !pinned)}
      >
        <Pin size={14} /> {pinned ? "Pinned" : "Pin"}
      </button>
      <button
        type="button"
        className={acknowledged ? "active acknowledged" : ""}
        aria-pressed={acknowledged}
        onClick={() => onToggle("acknowledged", !acknowledged)}
      >
        <CheckCircle2 size={14} /> {acknowledged ? "Acknowledged" : "Acknowledge"}
      </button>
    </div>
  );
}

const AlertsPanel: React.FC<AlertsPanelProps> = ({
  canManage,
  liveAlerts,
  onOpenArticles,
}) => {
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
  const [workflowStates, setWorkflowStates] = useState<
    Record<string, AlertWorkflowState>
  >({});
  const [actionError, setActionError] = useState<string | null>(null);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<string | null>(null);
  const [freshnessTick, setFreshnessTick] = useState(() => Date.now());

  // Drill-down state
  const [selectedAlert, setSelectedAlert] =
    useState<ViralPostAlertSummary | null>(null);
  const [alertDetail, setAlertDetail] = useState<ViralPostDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const [selectedCrisis, setSelectedCrisis] =
    useState<SocialCrisisAlert | null>(null);
  const [crisisDetail, setCrisisDetail] =
    useState<SocialCrisisDetail | null>(null);
  const [crisisLoading, setCrisisLoading] = useState(false);
  const [crisisError, setCrisisError] = useState<string | null>(null);
  const crisisTriggerRef = useRef<HTMLButtonElement | null>(null);

  const [selectedSpike, setSelectedSpike] = useState<SpikeAlert | null>(null);
  const [spikeDetail, setSpikeDetail] = useState<VolumeSpikeDetail | null>(null);
  const [spikeLoading, setSpikeLoading] = useState(false);
  const [spikeError, setSpikeError] = useState<string | null>(null);
  const spikeTriggerRef = useRef<HTMLButtonElement | null>(null);
  const [selectedCluster, setSelectedCluster] = useState<ViralCluster | null>(null);
  const clusterTriggerRef = useRef<HTMLButtonElement | null>(null);

  const viralClusters = useMemo<ViralCluster[]>(() => {
    const grouped = new Map<
      string,
      { source: string; posts: ViralPostAlertSummary[] }
    >();
    viralAlerts.forEach((alert) => {
      const topic = viralTopicKey(alert);
      const groupKey = `${alert.source}:${topic}`;
      const group = grouped.get(groupKey) || { source: alert.source, posts: [] };
      group.posts.push(alert);
      grouped.set(groupKey, group);
    });
    return Array.from(grouped.entries()).map(([groupKey, { source, posts }]) => ({
      id: `cluster:${groupKey}`,
      source,
      posts,
      interactions: posts.reduce((total, post) => total + post.interactions, 0),
    }));
  }, [viralAlerts]);

  const alertIds = useMemo(
    () => [
      ...crisisAlerts.map(crisisAlertId),
      ...viralClusters.map((cluster) => cluster.id),
      ...spikes.map(spikeAlertId),
    ],
    [crisisAlerts, spikes, viralClusters],
  );
  const alertIdsKey = alertIds.slice().sort().join("|");

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const [spikesData, socialData, configData] = await Promise.all([
        apiFetch<any>(`${API_BASE}/alerts?threshold=0.5&limit=10`),
        apiFetch<any>(`${API_BASE}/alerts/social`),
        apiFetch<AlertThresholds>(`${API_BASE}/alerts/config`),
      ]);

      setSpikes(spikesData.spikes || []);
      setCrisisAlerts(socialData.crisis_alerts || []);

      // Deduplicate by post_id
      setViralAlerts(deduplicateViralAlerts(socialData.viral_alerts || []));
      setThresholds(configData);
      setLastUpdatedAt(socialData.generated_at || new Date().toISOString());
      setError(null);
    } catch {
      setError("Failed to fetch alerts.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  useEffect(() => {
    if (!liveAlerts) return;
    setCrisisAlerts(liveAlerts.crisis);
    setViralAlerts(deduplicateViralAlerts(liveAlerts.viral));
    setLastUpdatedAt(liveAlerts.timestamp);
  }, [liveAlerts]);

  useEffect(() => {
    const timer = window.setInterval(() => setFreshnessTick(Date.now()), 15000);
    return () => window.clearInterval(timer);
  }, []);

  const freshnessAgeSeconds = lastUpdatedAt
    ? Math.max(0, Math.floor((freshnessTick - new Date(lastUpdatedAt).getTime()) / 1000))
    : null;
  const isStale = freshnessAgeSeconds !== null && freshnessAgeSeconds > 90;
  const freshnessLabel =
    freshnessAgeSeconds === null
      ? "Freshness unavailable"
      : freshnessAgeSeconds < 60
        ? `Updated ${freshnessAgeSeconds}s ago`
        : `Updated ${Math.floor(freshnessAgeSeconds / 60)}m ago`;

  useEffect(() => {
    if (!canManage) {
      setWorkflowStates({});
      return;
    }
    if (!alertIdsKey) {
      setWorkflowStates({});
      return;
    }
    const token = localStorage.getItem("token");
    if (!token) return;
    const controller = new AbortController();
    apiFetch<AlertWorkflowState[]>(`${API_BASE}/alerts/state/query`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ alert_ids: alertIdsKey.split("|") }),
      signal: controller.signal,
    })
      .then((states) => {
        setActionError(null);
        setWorkflowStates(
          Object.fromEntries(states.map((state) => [state.alert_id, state])),
        );
      })
      .catch((requestError) => {
        if (requestError?.name !== "AbortError") {
          setActionError("Unable to load saved alert states.");
        }
      });
    return () => controller.abort();
  }, [alertIdsKey, canManage]);

  const toggleWorkflowState = useCallback(
    async (
      alertId: string,
      field: "pinned" | "acknowledged",
      value: boolean,
    ) => {
      const token = localStorage.getItem("token");
      if (!token) {
        setActionError("Please sign in again to update alerts.");
        return;
      }
      const previous = workflowStates[alertId] || {
        alert_id: alertId,
        pinned: false,
        acknowledged: false,
      };
      setActionError(null);
      setWorkflowStates((current) => ({
        ...current,
        [alertId]: { ...previous, [field]: value },
      }));
      try {
        const saved = await apiFetch<AlertWorkflowState>(
          `${API_BASE}/alerts/state/${encodeURIComponent(alertId)}`,
          {
            method: "PATCH",
            headers: {
              Authorization: `Bearer ${token}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ [field]: value }),
          },
        );
        setWorkflowStates((current) => ({ ...current, [alertId]: saved }));
      } catch {
        setWorkflowStates((current) => ({ ...current, [alertId]: previous }));
        setActionError("Failed to update alert state. Please try again.");
      }
    },
    [workflowStates],
  );

  const sortPinnedFirst = useCallback(
    <T,>(items: T[], getId: (item: T) => string) =>
      [...items].sort(
        (left, right) =>
          Number(workflowStates[getId(right)]?.pinned || false) -
          Number(workflowStates[getId(left)]?.pinned || false),
      ),
    [workflowStates],
  );

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

  const handleOpenCluster = useCallback(
    (cluster: ViralCluster, btnEl: HTMLButtonElement | null) => {
      clusterTriggerRef.current = btnEl;
      setSelectedCluster(cluster);
    },
    [],
  );

  const handleCloseCluster = useCallback(() => {
    setSelectedCluster(null);
    clusterTriggerRef.current?.focus();
  }, []);

  const handleSelectClusterPost = useCallback(
    (post: ViralPostAlertSummary) => {
      setSelectedCluster(null);
      void handleOpenDetail(post, clusterTriggerRef.current);
    },
    [handleOpenDetail],
  );

  const handleOpenCrisis = useCallback(
    async (alert: SocialCrisisAlert, btnEl: HTMLButtonElement | null) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      crisisTriggerRef.current = btnEl;
      setSelectedCrisis(alert);
      setCrisisDetail(null);
      setCrisisLoading(true);
      setCrisisError(null);

      try {
        const detail = await apiFetch<SocialCrisisDetail>(
          `${API_BASE}/alerts/social/crisis/${encodeURIComponent(alert.source)}`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted) setCrisisDetail(detail);
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        setCrisisError(
          err?.status === 404
            ? "This crisis is no longer active."
            : "Failed to load crisis details.",
        );
      } finally {
        if (!controller.signal.aborted) setCrisisLoading(false);
      }
    },
    [],
  );

  const handleCloseCrisis = useCallback(() => {
    abortRef.current?.abort();
    setSelectedCrisis(null);
    setCrisisDetail(null);
    setCrisisLoading(false);
    setCrisisError(null);
    crisisTriggerRef.current?.focus();
  }, []);

  const handleOpenSpike = useCallback(
    async (alert: SpikeAlert, btnEl: HTMLButtonElement | null) => {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      spikeTriggerRef.current = btnEl;
      setSelectedSpike(alert);
      setSpikeDetail(null);
      setSpikeLoading(true);
      setSpikeError(null);

      try {
        const detail = await apiFetch<VolumeSpikeDetail>(
          `${API_BASE}/alerts/volume/${encodeURIComponent(alert.hour_slot)}?threshold=${alert.threshold ?? 0.5}`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted) setSpikeDetail(detail);
      } catch (err: any) {
        if (err?.name === "AbortError") return;
        setSpikeError(
          err?.status === 404
            ? "This spike is no longer available."
            : "Failed to load volume spike details.",
        );
      } finally {
        if (!controller.signal.aborted) setSpikeLoading(false);
      }
    },
    [],
  );

  const handleCloseSpike = useCallback(() => {
    abortRef.current?.abort();
    setSelectedSpike(null);
    setSpikeDetail(null);
    setSpikeLoading(false);
    setSpikeError(null);
    spikeTriggerRef.current?.focus();
  }, []);

  const handleSaveConfig = async () => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`${API_BASE}/alerts/config`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
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
        <div className="alerts-header-actions">
          <span
            className={`alert-freshness ${isStale ? "stale" : ""}`}
            role="status"
            aria-live="polite"
          >
            <Clock size={15} aria-hidden="true" />
            {isStale ? `Stale data · ${freshnessLabel}` : freshnessLabel}
          </span>
          {canManage && <button
            className="btn btn-secondary"
            onClick={() => setShowConfig(!showConfig)}
            aria-expanded={showConfig}
          >
            <Settings size={18} /> Configure
          </button>}
        </div>
      </div>
      {error && (
        <p role="alert" className="error-toast">
          {error}
        </p>
      )}
      <div aria-live="polite" aria-atomic="true">
        {actionError && (
          <p role="alert" className="alert-action-error">
            {actionError}
          </p>
        )}
      </div>

      {canManage && showConfig && (
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
          <div className="alert-config-grid">
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
            {sortPinnedFirst(crisisAlerts, crisisAlertId).map((crisis) => {
              const alertId = crisisAlertId(crisis);
              const state = workflowStates[alertId];
              return (
                <div
                  key={alertId}
                  className={`alert-card-shell ${state?.acknowledged ? "acknowledged" : ""} ${state?.pinned ? "pinned" : ""}`}
                >
                  <button
                    type="button"
                    className="alert-card glass-panel severity-high alert-card-interactive alert-card-crisis"
                    style={{ borderColor: "rgba(239, 68, 68, 0.5)" }}
                    aria-haspopup="dialog"
                    aria-expanded={selectedCrisis?.source === crisis.source}
                    onClick={(event) => handleOpenCrisis(crisis, event.currentTarget)}
                  >
                    <div className="alert-card-header">
                      <div className="alert-time">
                        <ShieldAlert size={16} /> {crisis.source}
                      </div>
                      <div className="alert-badge" style={{ background: "#ef4444" }}>
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
                    <div className="alert-card-hint">Click for crisis details →</div>
                  </button>
                  {canManage && <AlertCardActions
                    state={state}
                    onToggle={(field, value) =>
                      void toggleWorkflowState(alertId, field, value)
                    }
                  />}
                </div>
              );
            })}
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
            {sortPinnedFirst(viralClusters, (cluster) => cluster.id).map((cluster) => {
              const state = workflowStates[cluster.id];
              const viral = cluster.posts[0];
              const isCluster = cluster.posts.length > 1;
              return (
                <div
                  key={cluster.id}
                  className={`alert-card-shell ${state?.acknowledged ? "acknowledged" : ""} ${state?.pinned ? "pinned" : ""}`}
                >
                  <button
                    type="button"
                    className="alert-card glass-panel severity-medium alert-card-interactive"
                    style={{ borderColor: "rgba(245, 158, 11, 0.5)" }}
                    aria-haspopup="dialog"
                    aria-expanded={
                      isCluster
                        ? selectedCluster?.id === cluster.id
                        : selectedAlert?.post_id === viral.post_id
                    }
                    aria-label={
                      isCluster
                        ? `${cluster.posts.length} viral posts from ${cluster.source}`
                        : `Viral alert: ${viral.data_quality.title_available ? viral.title : viral.source} — ${viral.interactions} interactions`
                    }
                    onClick={(event) =>
                      isCluster
                        ? handleOpenCluster(cluster, event.currentTarget)
                        : handleOpenDetail(viral, event.currentTarget)
                    }
                  >
                    <div className="alert-card-header">
                      <div className="alert-time">
                        {isCluster ? <Layers3 size={16} /> : <Zap size={16} />}
                        {cluster.source}
                      </div>
                      <div className="alert-card-badges">
                        {cluster.posts.some((post) => post.data_quality.synthetic) && (
                          <span className="synthetic-data-badge">Synthetic data</span>
                        )}
                        <div className="alert-badge" style={{ background: "#f59e0b" }}>
                          {isCluster ? `${cluster.posts.length} posts` : "Viral"}
                        </div>
                      </div>
                    </div>
                    <p className={`alert-card-title ${!viral.data_quality.title_available ? "alert-title-unavailable" : ""}`}>
                      {isCluster
                        ? `Viral activity cluster on ${cluster.source}`
                        : viral.data_quality.title_available && viral.title
                          ? viral.title
                          : `Trending post on ${viral.source}`}
                    </p>
                    <div className="alert-stats alert-cluster-stats">
                      <div className="stat-box highlight">
                        <span className="stat-label" style={{ color: "#f59e0b" }}>
                          {isCluster ? "TOTAL INTERACTIONS" : "INTERACTIONS"}
                        </span>
                        <span className="stat-value" style={{ color: "#f59e0b" }}>
                          {cluster.interactions.toLocaleString()}
                        </span>
                      </div>
                      {!isCluster && viral.publish_time && (
                        <div className="alert-publish-time">
                          <Clock size={14} />
                          {new Date(viral.publish_time).toLocaleTimeString("vi-VN", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </div>
                      )}
                    </div>
                    <div className="alert-card-hint">
                      {isCluster ? "Explore clustered posts →" : "Click for details →"}
                    </div>
                  </button>
                  {canManage && <AlertCardActions
                    state={state}
                    onToggle={(field, value) =>
                      void toggleWorkflowState(cluster.id, field, value)
                    }
                  />}
                </div>
              );
            })}
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
            sortPinnedFirst(spikes, spikeAlertId).map((spike) => {
              const alertId = spikeAlertId(spike);
              const state = workflowStates[alertId];
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
                  key={alertId}
                  className={`alert-card-shell ${state?.acknowledged ? "acknowledged" : ""} ${state?.pinned ? "pinned" : ""}`}
                >
                  <button
                    type="button"
                    className={`alert-card glass-panel ${severityClass} alert-card-interactive alert-card-spike`}
                    aria-haspopup="dialog"
                    aria-expanded={selectedSpike?.hour_slot === spike.hour_slot}
                    onClick={(event) => handleOpenSpike(spike, event.currentTarget)}
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
                        <span className="stat-value">{spike.article_count}</span>
                      </div>
                      <div className="stat-box highlight">
                        <span className="stat-label">Surge</span>
                        <span className="stat-value flex-center">
                          <TrendingUp size={16} /> {multiplier.toFixed(1)}x
                        </span>
                      </div>
                    </div>
                    <div className="alert-card-hint">Click for spike details →</div>
                  </button>
                  {canManage && <AlertCardActions
                    state={state}
                    onToggle={(field, value) =>
                      void toggleWorkflowState(alertId, field, value)
                    }
                  />}
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
      <ViralClusterModal
        open={!!selectedCluster}
        onClose={handleCloseCluster}
        source={selectedCluster?.source || ""}
        posts={selectedCluster?.posts || []}
        onSelectPost={handleSelectClusterPost}
      />
      <CrisisDetailModal
        open={!!selectedCrisis}
        onClose={handleCloseCrisis}
        summary={selectedCrisis}
        detail={crisisDetail}
        loading={crisisLoading}
        error={crisisError}
      />
      <VolumeSpikeDetailModal
        open={!!selectedSpike}
        onClose={handleCloseSpike}
        summary={selectedSpike}
        detail={spikeDetail}
        loading={spikeLoading}
        error={spikeError}
        onOpenArticles={(filter) => {
          handleCloseSpike();
          onOpenArticles(filter);
        }}
      />
    </div>
  );
};

export default AlertsPanel;

"use client";

import React, { useEffect, useMemo, useState } from "react";
import { Activity } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";
import type { InteractionTrendResponse } from "@/lib/alert-types";

interface InteractionTrendPanelProps {
  source: string;
  active: boolean;
}

export default function InteractionTrendPanel({
  source,
  active,
}: InteractionTrendPanelProps) {
  const [granularity, setGranularity] = useState<"15m" | "1h">("15m");
  const [trend, setTrend] = useState<InteractionTrendResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!active || !source) return;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    apiFetch<InteractionTrendResponse>(
      `${API_BASE}/alerts/social/trends?source=${encodeURIComponent(source)}&granularity=${granularity}`,
      { signal: controller.signal },
    )
      .then((data) => setTrend(data))
      .catch((requestError) => {
        if (requestError?.name !== "AbortError") {
          setError("Interaction trend is unavailable.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [active, granularity, source]);

  const maxInteractions = useMemo(
    () => Math.max(...(trend?.data.map((point) => point.interactions) || []), 1),
    [trend],
  );

  return (
    <section className="interaction-trend-panel">
      <div className="interaction-trend-header">
        <h4><Activity size={16} /> Interaction trend</h4>
        <div className="trend-granularity" aria-label="Trend granularity">
          <button
            type="button"
            className={granularity === "15m" ? "active" : ""}
            onClick={() => setGranularity("15m")}
          >
            15 min
          </button>
          <button
            type="button"
            className={granularity === "1h" ? "active" : ""}
            onClick={() => setGranularity("1h")}
          >
            1 hour
          </button>
        </div>
      </div>
      {loading && <p className="detail-empty-copy">Loading trend…</p>}
      {error && <p className="article-filter-error" role="alert">{error}</p>}
      {!loading && !error && trend?.data.length === 0 && (
        <p className="detail-empty-copy">No interaction data in this window.</p>
      )}
      {!loading && !error && trend && trend.data.length > 0 && (
        <div className="interaction-bars" role="img" aria-label={`Interaction trend for ${source}`}>
          {trend.data.map((point) => (
            <div className="interaction-bar-column" key={point.bucket}>
              <span className="interaction-bar-value">{point.interactions}</span>
              <div className="interaction-bar-track">
                <div
                  className="interaction-bar-fill"
                  style={{ height: `${Math.max((point.interactions / maxInteractions) * 100, 4)}%` }}
                />
              </div>
              <span className="interaction-bar-label">
                {new Date(point.bucket).toLocaleTimeString("vi-VN", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

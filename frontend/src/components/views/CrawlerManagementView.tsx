"use client";

import { useCallback, useEffect, useState } from "react";
import { DatabaseZap, Loader2, Play, RefreshCw } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

type Crawler = {
  spider_name: string;
  label: string;
  type: string;
  schedule: string;
  last_state: string;
  last_start?: string | null;
  duration_sec: number;
  total_items: number;
};

export default function CrawlerManagementView({ canRun }: { canRun: boolean }) {
  const [crawlers, setCrawlers] = useState<Crawler[]>([]);
  const [dagState, setDagState] = useState("unknown");
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<{ crawlers: Crawler[]; dag_state: string }>(
        `${API_BASE}/admin/crawlers/`,
      );
      setCrawlers(data.crawlers ?? []);
      setDagState(data.dag_state ?? "unknown");
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load crawlers");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const trigger = async (spiderName: string) => {
    setTriggering(spiderName);
    setMessage("");
    try {
      const result = await apiFetch<{ message: string }>(
        `${API_BASE}/admin/crawlers/trigger/${encodeURIComponent(spiderName)}`,
        { method: "POST" },
      );
      setMessage(result.message);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to trigger crawler");
    } finally {
      setTriggering(null);
    }
  };

  return (
    <section className="glass-panel access-panel">
      <div className="access-panel-header">
        <div>
          <h2><DatabaseZap size={21} /> Crawler Operations</h2>
          <p>Inspect collection jobs and trigger an approved crawler run.</p>
        </div>
        <div className="access-panel-actions">
          <span className={`status-pill status-${dagState}`}>DAG: {dagState}</span>
          <button type="button" className="btn btn-secondary" onClick={() => void load()} disabled={loading}>
            <RefreshCw size={15} className={loading ? "spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      {message && <p className="access-feedback" role="status">{message}</p>}
      <div className="crawler-grid" aria-busy={loading}>
        {crawlers.map((crawler) => (
          <article className="crawler-card" key={crawler.spider_name}>
            <div className="crawler-card-heading">
              <div>
                <strong>{crawler.label}</strong>
                <span>{crawler.type} · {crawler.schedule}</span>
              </div>
              <span className={`status-pill status-${crawler.last_state}`}>{crawler.last_state}</span>
            </div>
            <dl>
              <div><dt>Items</dt><dd>{crawler.total_items.toLocaleString()}</dd></div>
              <div><dt>Duration</dt><dd>{crawler.duration_sec || 0}s</dd></div>
              <div><dt>Last start</dt><dd>{crawler.last_start ? new Date(crawler.last_start).toLocaleString() : "No run"}</dd></div>
            </dl>
            {canRun && (
              <button type="button" className="btn btn-primary" onClick={() => void trigger(crawler.spider_name)} disabled={triggering !== null}>
                {triggering === crawler.spider_name ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
                Run now
              </button>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

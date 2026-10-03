"use client";

import { useCallback, useEffect, useState } from "react";
import { DatabaseZap, Loader2, Play, RefreshCw } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";
import MockDataGenerator from "@/components/views/MockDataGenerator";

type Crawler = {
  spider_name: string;
  label: string;
  type: string;
  schedule: string;
  last_state: string;
  last_start?: string | null;
  duration_sec: number;
  total_items: number;
  enabled: boolean;
  rate_limit_seconds: number;
};

export default function CrawlerManagementView({ canRun, canCreateMock }: { canRun: boolean; canCreateMock: boolean }) {
  const [crawlers, setCrawlers] = useState<Crawler[]>([]);
  const [dagState, setDagState] = useState("unknown");
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await apiFetch<{ crawlers: Crawler[]; dag_state: string }>(
        `${API_BASE}/admin/crawlers`,
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

  const updateSettings = async (crawler: Crawler, changes: Partial<Pick<Crawler, "enabled" | "rate_limit_seconds">>) => {
    setTriggering(crawler.spider_name);
    try {
      await apiFetch(`${API_BASE}/admin/crawlers/${encodeURIComponent(crawler.spider_name)}/settings`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(changes),
      });
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Failed to update source"); }
    finally { setTriggering(null); }
  };

  return <div className="crawler-management">
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
            <div className="crawler-source-settings">
              <label><input type="checkbox" checked={crawler.enabled} disabled={!canRun || triggering !== null} onChange={() => void updateSettings(crawler, { enabled: !crawler.enabled })}/> Enabled</label>
              <label>Delay<select value={crawler.rate_limit_seconds} disabled={!canRun || triggering !== null} onChange={(event) => void updateSettings(crawler, { rate_limit_seconds: Number(event.target.value) })}><option value={1}>1s</option><option value={2}>2s</option><option value={5}>5s</option><option value={10}>10s</option></select></label>
            </div>
            {canRun && (
              <button type="button" className="btn btn-primary" onClick={() => void trigger(crawler.spider_name)} disabled={triggering !== null || !crawler.enabled}>
                {triggering === crawler.spider_name ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
                Run now
              </button>
            )}
          </article>
        ))}
      </div>
    </section>
    {canCreateMock && <section className="glass-panel crawler-test-panel" aria-labelledby="crawler-test-title">
      <h2 id="crawler-test-title">Test Data</h2>
      <p>Generate sample social posts for testing. These are not collected by crawlers.</p>
      <MockDataGenerator />
    </section>}
  </div>;
}

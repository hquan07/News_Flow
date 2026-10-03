"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { BellRing, Bookmark, CalendarClock, Plus, Trash2 } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

type Item = { id: string; name: string; enabled: boolean; [key: string]: unknown };
type Section = "watchlists" | "alert-rules" | "saved-queries";

const sectionMeta: Record<Section, { title: string; icon: typeof Bookmark }> = {
  watchlists: { title: "Watchlists", icon: Bookmark },
  "alert-rules": { title: "Custom alerts", icon: BellRing },
  "saved-queries": { title: "Saved searches & reports", icon: CalendarClock },
};

export default function IntelligenceView({ onRunQuery, onAskWatchlist }: {
  onRunQuery: (item: Item) => void;
  onAskWatchlist: (item: Item) => void;
}) {
  const [data, setData] = useState<Record<Section, Item[]>>({
    watchlists: [], "alert-rules": [], "saved-queries": [],
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [watchlists, alerts, queries] = await Promise.all([
        apiFetch<Item[]>(`${API_BASE}/intelligence/watchlists`),
        apiFetch<Item[]>(`${API_BASE}/intelligence/alert-rules`),
        apiFetch<Item[]>(`${API_BASE}/intelligence/saved-queries`),
      ]);
      setData({ watchlists, "alert-rules": alerts, "saved-queries": queries });
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load intelligence settings");
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const create = async (event: FormEvent<HTMLFormElement>, section: Section) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const name = String(form.get("name") || "").trim();
    const target = String(form.get("target") || "").trim();
    if (!name || !target) return;
    const body = section === "watchlists"
      ? { name, kind: form.get("kind"), value: target, enabled: true }
      : section === "alert-rules"
        ? { name, kind: form.get("kind"), target, threshold: Number(form.get("threshold") || 10), window_minutes: 60, channels: ["dashboard"], enabled: true }
        : { name, query: target, schedule: form.get("schedule"), enabled: true };
    setBusy(true);
    try {
      await apiFetch(`${API_BASE}/intelligence/${section}`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      formElement.reset();
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create item");
    } finally { setBusy(false); }
  };

  const toggle = async (section: Section, item: Item) => {
    await apiFetch(`${API_BASE}/intelligence/${section}/${item.id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: !item.enabled }),
    });
    await load();
  };

  const remove = async (section: Section, id: string) => {
    await apiFetch(`${API_BASE}/intelligence/${section}/${id}`, { method: "DELETE" });
    await load();
  };

  return (
    <div className="intelligence-grid">
      {error && <div className="error-state intelligence-error">{error}</div>}
      {(Object.keys(sectionMeta) as Section[]).map((section) => {
        const Icon = sectionMeta[section].icon;
        return <section className="glass-panel intelligence-card" key={section}>
          <div className="panel-title"><Icon size={19} /> {sectionMeta[section].title}</div>
          <form className="intelligence-form" onSubmit={(event) => void create(event, section)}>
            <input name="name" required maxLength={100} placeholder="Name" aria-label={`${section} name`} />
            <input name="target" required maxLength={240} placeholder={section === "saved-queries" ? "Search terms" : "Target keyword or entity"} aria-label={`${section} target`} />
            {section === "watchlists" && <select name="kind" defaultValue="keyword"><option value="keyword">Keyword</option><option value="entity">Entity</option><option value="source">Source</option><option value="topic">Topic</option></select>}
            {section === "alert-rules" && <><select name="kind" defaultValue="keyword_volume"><option value="keyword_volume">Keyword volume</option><option value="negative_sentiment">Negative sentiment</option><option value="entity_mention">Entity mentions</option></select><input name="threshold" type="number" min="1" defaultValue="10" aria-label="Threshold" /></>}
            {section === "saved-queries" && <select name="schedule" defaultValue="none"><option value="none">No schedule</option><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select>}
            <button type="submit" disabled={busy}><Plus size={15} /> Add</button>
          </form>
          <div className="intelligence-list">
            {data[section].map((item) => <article key={item.id} className={!item.enabled ? "disabled" : ""}>
              <div><strong>{item.name}</strong><small>{String(item.value ?? item.target ?? item.query ?? "")}{item.schedule && item.schedule !== "none" ? ` · ${item.schedule}` : ""}</small></div>
              <div className="intelligence-actions">
                {section === "saved-queries" && <button type="button" onClick={() => onRunQuery(item)}>Run</button>}
                {section === "watchlists" && <button type="button" onClick={() => onAskWatchlist(item)}>Ask</button>}
                <button type="button" onClick={() => void toggle(section, item)}>{item.enabled ? "Pause" : "Enable"}</button>
                <button type="button" className="danger" aria-label={`Delete ${item.name}`} onClick={() => void remove(section, item.id)}><Trash2 size={15} /></button>
              </div>
            </article>)}
            {!data[section].length && <p className="detail-empty-copy">No items yet.</p>}
          </div>
        </section>;
      })}
    </div>
  );
}

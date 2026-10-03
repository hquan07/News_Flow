"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { BookOpenCheck, FileBarChart, RefreshCw, Trash2, X } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { API_BASE, apiFetch } from "@/lib/api";

type SavedQuery = { id: string; name: string; schedule: string };
type Report = { id: string; name: string; article_count: number; source_count: number; created_at: string; chart: { points: { label: string; value: number }[] }; citations: { article_id: string; title: string; url: string; source: string }[] };
type EventBriefing = {
  title: string;
  summary: string[];
  keywords: { keyword: string; article_count: number }[];
  timeline: { citation: number; title: string; source: string }[];
  citations: { article_id: string; title: string; url: string; source: string }[];
};

export default function BriefingsView({ initialEventId = "", onInitialEventHandled }: { initialEventId?: string; onInitialEventHandled?: () => void }) {
  const [queries, setQueries] = useState<SavedQuery[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [briefing, setBriefing] = useState<EventBriefing | null>(null);
  const [eventId, setEventId] = useState(initialEventId);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [briefingBusy, setBriefingBusy] = useState(false);
  const [deletingReportId, setDeletingReportId] = useState("");

  const load = useCallback(async () => {
    try {
      const [saved, generated] = await Promise.all([
        apiFetch<SavedQuery[]>(`${API_BASE}/intelligence/saved-queries`),
        apiFetch<Report[]>(`${API_BASE}/briefings/reports`),
      ]);
      setQueries(saved); setReports(generated); setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load reports"); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const generate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const id = String(new FormData(event.currentTarget).get("query_id") || "");
    if (!id) return;
    setBusy(true);
    try { await apiFetch(`${API_BASE}/briefings/reports/from-query/${id}`, { method: "POST" }); await load(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to generate report"); }
    finally { setBusy(false); }
  };

  const fetchBriefing = useCallback(async (id: string) => {
    if (!id) return;
    setBriefingBusy(true);
    try { setBriefing(await apiFetch<EventBriefing>(`${API_BASE}/briefings/events/${encodeURIComponent(id)}`)); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create briefing"); }
    finally { setBriefingBusy(false); }
  }, []);

  useEffect(() => {
    if (!initialEventId) return;
    setEventId(initialEventId);
    onInitialEventHandled?.();
    void fetchBriefing(initialEventId);
  }, [fetchBriefing, initialEventId, onInitialEventHandled]);

  const loadBriefing = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await fetchBriefing(eventId.trim());
  };

  const deleteReport = async (report: Report) => {
    if (!window.confirm(`Delete report “${report.name}”? This action cannot be undone.`)) return;

    setDeletingReportId(report.id);
    try {
      await apiFetch(`${API_BASE}/briefings/reports/${report.id}`, { method: "DELETE" });
      setReports((current) => current.filter((item) => item.id !== report.id));
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to delete report"); }
    finally { setDeletingReportId(""); }
  };

  return <div className="briefings-grid">
    {error && <div className="error-state briefings-wide">{error}</div>}
    <div className="briefing-column briefing-reports-column">
      <section className="glass-panel briefing-builder">
        <h3><FileBarChart size={18}/> Saved-query reports</h3>
        <form onSubmit={(event) => void generate(event)}><select name="query_id" required defaultValue=""><option value="" disabled>Select a saved query</option>{queries.map((query) => <option value={query.id} key={query.id}>{query.name} · {query.schedule}</option>)}</select><button disabled={busy}><RefreshCw size={15}/> Generate now</button></form>
        <p>Scheduled queries are generated hourly by Airflow when due.</p>
      </section>
      {reports.map((report) => <section className="glass-panel briefing-report" key={report.id}><div className="briefing-report-heading"><div><h3>{report.name}</h3><span>{report.article_count} articles · {report.source_count} sources</span></div><div className="briefing-report-actions"><small>{new Date(report.created_at).toLocaleString("vi-VN")}</small><button type="button" aria-label={`Delete report ${report.name}`} disabled={deletingReportId === report.id} onClick={() => void deleteReport(report)}><Trash2 size={15}/> {deletingReportId === report.id ? "Deleting…" : "Delete report"}</button></div></div><div className="briefing-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={report.chart.points}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.08)"/><XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 10 }}/><YAxis tick={{ fill: "#94a3b8", fontSize: 10 }}/><Tooltip/><Bar dataKey="value" fill="#34d399"/></BarChart></ResponsiveContainer></div><div className="briefing-citations">{report.citations.map((item, index) => <a href={item.url} target="_blank" rel="noreferrer" key={item.article_id}>[{index + 1}] {item.title} · {item.source}</a>)}</div></section>)}
      {!reports.length && <div className="glass-panel detail-empty-copy">No reports generated yet.</div>}
    </div>
    <div className="briefing-column briefing-events-column">
      <section className="glass-panel briefing-builder">
        <h3><BookOpenCheck size={18}/> Event briefing</h3>
        <form onSubmit={(event) => void loadBriefing(event)}><input name="event_id" required placeholder="Event ID" value={eventId} onChange={(event) => setEventId(event.target.value)}/><button disabled={briefingBusy}>{briefingBusy ? "Building…" : "Build briefing"}</button></form>
        <p>Build a cited timeline and sentiment snapshot for an event.</p>
      </section>
      {briefing ? <section className="glass-panel briefing-report briefing-event-report">
        <div className="briefing-event-heading"><h3>{briefing.title}</h3><button type="button" onClick={() => setBriefing(null)}><X size={15}/> Clear briefing</button></div>
        <div className="briefing-section">
          <h4>Snapshot</h4>
          <ul className="briefing-summary">{briefing.summary.map((line) => <li key={line}>{line}</li>)}</ul>
        </div>
        {briefing.keywords.length > 0 && <div className="briefing-section">
          <h4>Keywords</h4>
          <div className="briefing-tags">{briefing.keywords.map((item) => <span key={item.keyword}>{item.keyword} · {item.article_count}</span>)}</div>
        </div>}
        <div className="briefing-section">
          <h4>Timeline</h4>
          <ul className="briefing-timeline">{briefing.timeline.map((item) => <li key={`${item.citation}-${item.title}`}><span className="briefing-citation-number">[{item.citation}]</span><span>{item.title}<small>{item.source}</small></span></li>)}</ul>
        </div>
        <div className="briefing-section">
          <h4>Sources</h4>
          <div className="briefing-citations">{briefing.citations.map((item, index) => <a href={item.url} target="_blank" rel="noreferrer" key={item.article_id}>[{index + 1}] {item.title}<small>{item.source}</small></a>)}</div>
        </div>
      </section> : <div className="glass-panel detail-empty-copy">Build an event briefing to see its snapshot, timeline and sources.</div>}
    </div>
  </div>;
}

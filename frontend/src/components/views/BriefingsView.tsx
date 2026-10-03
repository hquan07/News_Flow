"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { BookOpenCheck, FileBarChart, RefreshCw } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { API_BASE, apiFetch } from "@/lib/api";

type SavedQuery = { id: string; name: string; schedule: string };
type Report = { id: string; name: string; article_count: number; source_count: number; created_at: string; chart: { points: { label: string; value: number }[] }; citations: { article_id: string; title: string; url: string; source: string }[] };

export default function BriefingsView() {
  const [queries, setQueries] = useState<SavedQuery[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [briefing, setBriefing] = useState<any>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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

  const loadBriefing = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const id = String(new FormData(event.currentTarget).get("event_id") || "").trim();
    if (!id) return;
    try { setBriefing(await apiFetch(`${API_BASE}/briefings/events/${encodeURIComponent(id)}`)); setError(""); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create briefing"); }
  };

  return <div className="briefings-grid">
    {error && <div className="error-state briefings-wide">{error}</div>}
    <section className="glass-panel briefing-builder">
      <h3><FileBarChart size={18}/> Saved-query reports</h3>
      <form onSubmit={(event) => void generate(event)}><select name="query_id" required defaultValue=""><option value="" disabled>Select a saved query</option>{queries.map((query) => <option value={query.id} key={query.id}>{query.name} · {query.schedule}</option>)}</select><button disabled={busy}><RefreshCw size={15}/> Generate now</button></form>
      <p>Scheduled queries are generated hourly by Airflow when due.</p>
    </section>
    <section className="glass-panel briefing-builder">
      <h3><BookOpenCheck size={18}/> Event briefing</h3>
      <form onSubmit={(event) => void loadBriefing(event)}><input name="event_id" required placeholder="Event ID"/><button>Build briefing</button></form>
      <p>Creates a factual timeline, sentiment distribution and cited keyword snapshot.</p>
    </section>
    {briefing && <section className="glass-panel briefing-report briefings-wide"><h3>{briefing.title}</h3><ul>{briefing.summary.map((line: string) => <li key={line}>{line}</li>)}</ul><div className="briefing-tags">{briefing.keywords.map((item: any) => <span key={item.keyword}>{item.keyword} · {item.article_count}</span>)}</div><ol>{briefing.timeline.map((item: any) => <li key={`${item.citation}-${item.title}`}>[{item.citation}] {item.title} · {item.source}</li>)}</ol><div className="briefing-citations">{briefing.citations.map((item: any, index: number) => <a href={item.url} target="_blank" rel="noreferrer" key={item.article_id}>[{index + 1}] {item.title} · {item.source}</a>)}</div></section>}
    {reports.map((report) => <section className="glass-panel briefing-report" key={report.id}><div className="briefing-report-heading"><div><h3>{report.name}</h3><span>{report.article_count} articles · {report.source_count} sources</span></div><small>{new Date(report.created_at).toLocaleString("vi-VN")}</small></div><div className="briefing-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={report.chart.points}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.08)"/><XAxis dataKey="label" tick={{ fill: "#94a3b8", fontSize: 10 }}/><YAxis tick={{ fill: "#94a3b8", fontSize: 10 }}/><Tooltip/><Bar dataKey="value" fill="#34d399"/></BarChart></ResponsiveContainer></div><div className="briefing-citations">{report.citations.map((item, index) => <a href={item.url} target="_blank" rel="noreferrer" key={item.article_id}>[{index + 1}] {item.title} · {item.source}</a>)}</div></section>)}
    {!reports.length && <div className="glass-panel detail-empty-copy briefings-wide">No reports generated yet.</div>}
  </div>;
}

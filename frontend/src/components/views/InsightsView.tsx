"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Activity, BrainCircuit, GitCompareArrows, Route } from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { API_BASE, apiFetch } from "@/lib/api";

type ForecastPoint = { bucket: string; value: number; lower: number; upper: number };
type InitialInsightLookup = { type: "divergence" | "nlp"; value: string };

export default function InsightsView({ initialLookup, onInitialLookupHandled }: { initialLookup?: InitialInsightLookup | null; onInitialLookupHandled?: () => void }) {
  const [metric, setMetric] = useState("articles");
  const [forecast, setForecast] = useState<ForecastPoint[]>([]);
  const [propagation, setPropagation] = useState<any>(null);
  const [divergence, setDivergence] = useState<any>(null);
  const [explanation, setExplanation] = useState<any>(null);
  const [divergenceEventId, setDivergenceEventId] = useState(initialLookup?.type === "divergence" ? initialLookup.value : "");
  const [articleId, setArticleId] = useState(initialLookup?.type === "nlp" ? initialLookup.value : "");
  const [busyType, setBusyType] = useState<"propagation" | "divergence" | "nlp" | "">("");
  const [error, setError] = useState("");

  useEffect(() => {
    void apiFetch<any>(`${API_BASE}/insights/forecast?metric=${metric}&horizon=12`)
      .then((result) => { setForecast(result.forecast || []); setError(""); })
      .catch((reason: Error) => setError(reason.message));
  }, [metric]);

  const runLookup = useCallback(async (value: string, type: "propagation" | "divergence" | "nlp") => {
    if (!value) return;
    setBusyType(type);
    try {
      if (type === "propagation") setPropagation(await apiFetch(`${API_BASE}/insights/propagation?keyword=${encodeURIComponent(value)}`));
      if (type === "divergence") setDivergence(await apiFetch(`${API_BASE}/insights/source-divergence/${encodeURIComponent(value)}`));
      if (type === "nlp") setExplanation(await apiFetch(`${API_BASE}/insights/nlp-explanation/${encodeURIComponent(value)}`));
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load insight"); }
    finally { setBusyType(""); }
  }, []);

  useEffect(() => {
    if (!initialLookup) return;
    if (initialLookup.type === "divergence") setDivergenceEventId(initialLookup.value);
    if (initialLookup.type === "nlp") setArticleId(initialLookup.value);
    onInitialLookupHandled?.();
    void runLookup(initialLookup.value, initialLookup.type);
  }, [initialLookup, onInitialLookupHandled, runLookup]);

  const lookup = async (event: FormEvent<HTMLFormElement>, type: "propagation" | "divergence" | "nlp") => {
    event.preventDefault();
    const formValue = String(new FormData(event.currentTarget).get("value") || "").trim();
    const value = type === "divergence" ? divergenceEventId.trim() : type === "nlp" ? articleId.trim() : formValue;
    await runLookup(value, type);
  };

  return <div className="insights-grid">
    {error && <div className="error-state insights-wide">{error}</div>}
    <section className="glass-panel insight-card insights-wide">
      <div className="insight-heading"><div><h3><Activity size={18} /> Trend forecast</h3><p>Linear trend over the latest 24 hourly points, with a residual confidence band.</p></div><select value={metric} onChange={(event) => setMetric(event.target.value)}><option value="articles">Article volume</option><option value="sentiment">Average sentiment</option></select></div>
      <div className="forecast-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={forecast}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.08)"/><XAxis dataKey="bucket" tickFormatter={(value) => new Date(value).toLocaleTimeString("vi-VN", { hour: "2-digit" })} tick={{ fill: "#94a3b8", fontSize: 11 }}/><YAxis tick={{ fill: "#94a3b8", fontSize: 11 }}/><Tooltip/><Area dataKey="upper" stroke="transparent" fill="rgba(96,165,250,.08)"/><Area dataKey="value" stroke="#60a5fa" fill="rgba(96,165,250,.2)"/><Area dataKey="lower" stroke="#64748b" fill="transparent"/></AreaChart></ResponsiveContainer></div>
    </section>
    <section className="glass-panel insight-card">
      <h3><Route size={18} /> Propagation</h3><form onSubmit={(event) => void lookup(event, "propagation")}><input name="value" placeholder="Keyword, e.g. VinFast" required/><button>Analyze</button></form>
      {propagation && <div className="insight-result">{propagation.origin ? <><strong>Origin: {propagation.origin.source}</strong><span>Peak: {propagation.peak?.article_count ?? 0} articles/hour</span>{propagation.source_delays_minutes.map((item: any) => <small key={item.source}>{item.source}: +{item.delay_minutes} min</small>)}</> : <span>No matching timeline found.</span>}</div>}
    </section>
    <section className="glass-panel insight-card">
      <h3><GitCompareArrows size={18} /> Source divergence</h3><form onSubmit={(event) => void lookup(event, "divergence")}><input name="value" placeholder="Event ID" required value={divergenceEventId} onChange={(event) => setDivergenceEventId(event.target.value)}/><button disabled={busyType === "divergence"}>{busyType === "divergence" ? "Comparing…" : "Compare"}</button></form>
      {divergence && <div className="insight-result"><strong>{divergence.title}</strong>{divergence.comparisons.map((item: any) => <small key={`${item.source_a}-${item.source_b}`}>{item.source_a} ↔ {item.source_b}: framing {item.framing_distance}, sentiment gap {item.sentiment_gap}</small>)}{divergence.sources?.length < 2 && <span>At least two news sources are required for a comparison. This event currently has {divergence.sources?.length ?? 0}.</span>}<span>{divergence.note}</span></div>}
    </section>
    <section className="glass-panel insight-card insights-wide">
      <h3><BrainCircuit size={18} /> NLP explanation</h3><form onSubmit={(event) => void lookup(event, "nlp")}><input name="value" placeholder="Article ID" required value={articleId} onChange={(event) => setArticleId(event.target.value)}/><button disabled={busyType === "nlp"}>{busyType === "nlp" ? "Explaining…" : "Explain"}</button></form>
      {explanation && <div className="insight-result"><strong>{explanation.article.title}</strong><span>Sentiment: {explanation.article.sentiment_label} ({Number(explanation.article.sentiment_score).toFixed(3)})</span><div className="insight-tags">{explanation.keywords.map((item: any) => <span key={item.keyword}>{item.keyword} · {item.score}</span>)}{explanation.entities.map((item: any) => <span key={`${item.type}-${item.name}`}>{item.name} · {item.type}</span>)}</div>{explanation.evidence.map((text: string, index: number) => <blockquote key={index}>{text}</blockquote>)}<small>{explanation.explanation}</small></div>}
    </section>
  </div>;
}

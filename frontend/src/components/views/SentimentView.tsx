"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Activity, BarChart2, ThumbsUp } from "lucide-react";
import ChartCard from "../ui/ChartCard";
import EmptyState from "../ui/EmptyState";
import ChartSkeleton from "../ui/ChartSkeleton";
import { formatCompactNumber, formatPercent, formatSourceName } from "@/lib/formatters";

const SENTIMENTS = {
  positive: { label: "+ Positive", color: "#10b981" },
  neutral: { label: "● Neutral", color: "#94a3b8" },
  negative: { label: "− Negative", color: "#f97316" },
} as const;

function getSentimentValue(row: Record<string, unknown>, key: string): number {
  const match = Object.keys(row).find((candidate) => candidate.toLowerCase() === key);
  return Number(match ? row[match] : 0) || 0;
}

export default function SentimentView({ sentimentDist, sentimentTimeline, sentimentSources, sentimentCoverage, updatedAt }: any) {
  const [sourceMode, setSourceMode] = useState<"percentage" | "count">("percentage");
  const distribution = useMemo(() => (sentimentDist ?? []).map((row: any) => {
    const key = String(row.sentiment_label ?? row.sentiment ?? "neutral").toLowerCase() as keyof typeof SENTIMENTS;
    return { key, name: SENTIMENTS[key]?.label ?? row.sentiment_label, count: Number(row.count || 0), color: SENTIMENTS[key]?.color ?? "#3b82f6" };
  }), [sentimentDist]);
  const totalSentiment = distribution.reduce((sum: number, row: any) => sum + row.count, 0);

  const sources = useMemo(() => (sentimentSources ?? []).map((row: Record<string, unknown>) => {
    const positive = getSentimentValue(row, "positive");
    const neutral = getSentimentValue(row, "neutral");
    const negative = getSentimentValue(row, "negative");
    const total = positive + neutral + negative;
    return {
      source: formatSourceName(String(row.source ?? "Unknown")), total, positive, neutral, negative,
      positivePct: total ? positive * 100 / total : 0,
      neutralPct: total ? neutral * 100 / total : 0,
      negativePct: total ? negative * 100 / total : 0,
    };
  }).sort((a: any, b: any) => b.total - a.total), [sentimentSources]);

  const timeline = useMemo(() => (sentimentTimeline ?? []).map((row: Record<string, unknown>) => ({
    ...row,
    positive: getSentimentValue(row, "positive"),
    neutral: getSentimentValue(row, "neutral"),
    negative: getSentimentValue(row, "negative"),
  })), [sentimentTimeline]);

  return <div className="charts-grid">
    <ChartCard title={<><ThumbsUp size={20} /> Overall Sentiment</>} description="What share of analyzed articles is positive, neutral or negative?" timeRange="Last 7 days" unit="Articles and share" total={totalSentiment} updatedAt={updatedAt}>
      {distribution.length > 0 ? <div style={{ position: "relative", width: "100%", height: "100%" }}>
        <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={distribution} dataKey="count" nameKey="name" cx="50%" cy="46%" innerRadius="48%" outerRadius="72%" paddingAngle={2} labelLine={false}>{distribution.map((entry: any) => <Cell key={entry.key} fill={entry.color} />)}</Pie>
          <Tooltip formatter={(value, _name, item) => [`${Number(value).toLocaleString()} (${formatPercent(totalSentiment ? Number(value) * 100 / totalSentiment : 0)})`, item.payload.name]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }} />
          <Legend verticalAlign="bottom" formatter={(value) => <span style={{ color: "#cbd5e1" }}>{value}</span>} />
        </PieChart></ResponsiveContainer>
        <div style={{ position: "absolute", inset: "40% 0 auto", textAlign: "center", pointerEvents: "none" }}><strong style={{ fontSize: "1.35rem" }}>{formatCompactNumber(totalSentiment)}</strong><div style={{ color: "var(--text-muted)", fontSize: "0.72rem" }}>analyzed</div></div>
      </div> : !sentimentDist ? <ChartSkeleton /> : <EmptyState message="No sentiment data" />}
    </ChartCard>

    <ChartCard title={<><BarChart2 size={20} /> Sentiment by Source</>} description="How does sentiment composition compare across sources?" timeRange="Last 7 days" unit={sourceMode === "percentage" ? "Share of source volume" : "Articles"} total={sources.reduce((sum: number, row: any) => sum + row.total, 0)} updatedAt={updatedAt} actions={<div className="chart-toggle" aria-label="Source chart unit"><button type="button" className={sourceMode === "percentage" ? "active" : ""} onClick={() => setSourceMode("percentage")}>Percentage</button><button type="button" className={sourceMode === "count" ? "active" : ""} onClick={() => setSourceMode("count")}>Count</button></div>}>
      {sources.length > 0 ? <ResponsiveContainer width="100%" height="100%"><BarChart data={sources} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
        <XAxis dataKey="source" stroke="#94a3b8" fontSize={11} interval="preserveStartEnd" />
        <YAxis stroke="#94a3b8" fontSize={11} domain={sourceMode === "percentage" ? [0, 100] : undefined} tickFormatter={sourceMode === "percentage" ? (value) => `${value}%` : formatCompactNumber} allowDecimals={false} />
        <Tooltip cursor={false} formatter={(value, name, item) => { const key = String(name).replace("Pct", "").toLowerCase(); const count = item.payload[key] ?? 0; const pct = item.payload[`${key}Pct`] ?? 0; return [`${Number(count).toLocaleString()} · ${formatPercent(Number(pct))}`, SENTIMENTS[key as keyof typeof SENTIMENTS]?.label ?? name]; }} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }} />
        <Legend formatter={(value) => SENTIMENTS[String(value).replace("Pct", "") as keyof typeof SENTIMENTS]?.label ?? value} />
        {(["positive", "neutral", "negative"] as const).map((key) => <Bar key={key} dataKey={sourceMode === "percentage" ? `${key}Pct` : key} name={sourceMode === "percentage" ? `${key}Pct` : key} stackId="sentiment" fill={SENTIMENTS[key].color} />)}
      </BarChart></ResponsiveContainer> : !sentimentSources ? <ChartSkeleton /> : <EmptyState message={sentimentCoverage?.unlinked ? `${sentimentCoverage.unlinked.toLocaleString()} sentiment records are not linked to current articles. Run the NLP backfill to restore source attribution.` : "No source sentiment data"} />}
    </ChartCard>

    <ChartCard wide title={<><Activity size={20} /> Sentiment Timeline</>} description="How has the volume of each sentiment changed over time?" timeRange="Last 7 days" unit="Articles per time bucket" total={timeline.reduce((sum: number, row: any) => sum + row.positive + row.neutral + row.negative, 0)} updatedAt={updatedAt}>
      {timeline.length > 0 ? <ResponsiveContainer width="100%" height="100%"><LineChart data={timeline}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
        <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} interval="preserveStartEnd" minTickGap={40} tickFormatter={(value) => new Date(value).toLocaleDateString([], { month: "short", day: "numeric" })} />
        <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} tickFormatter={formatCompactNumber} />
        <Tooltip labelFormatter={(value) => new Date(String(value)).toLocaleString()} formatter={(value, name) => [Number(value).toLocaleString(), SENTIMENTS[name as keyof typeof SENTIMENTS]?.label ?? name]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }} />
        <Legend formatter={(value) => SENTIMENTS[value as keyof typeof SENTIMENTS]?.label ?? value} />
        {(["positive", "neutral", "negative"] as const).map((key) => <Line key={key} type="linear" dataKey={key} stroke={SENTIMENTS[key].color} strokeWidth={2} dot={false} connectNulls={false} />)}
      </LineChart></ResponsiveContainer> : !sentimentTimeline ? <ChartSkeleton /> : <EmptyState message={sentimentCoverage?.unlinked ? `Timeline unavailable because sentiment coverage is ${sentimentCoverage.coverage_pct}%. Run the NLP backfill to link publication dates.` : "No timeline data"} />}
    </ChartCard>
  </div>;
}

"use client";

import { Activity, BookOpen, Server, Share2, Users } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartCard from "../ui/ChartCard";
import EmptyState from "../ui/EmptyState";
import ChartSkeleton from "../ui/ChartSkeleton";
import MetricCard from "../ui/MetricCard";
import { formatCompactNumber, formatDateTime, formatPercent, formatSourceName } from "@/lib/formatters";

interface VolumeGroup {
  sources: string[];
  volumes: number[];
  total: number;
}

interface AdminViewProps {
  adminLatency: { sources: string[]; avg_latency: number[]; overall_average: number; sla_target: number; generated_at?: string } | null;
  adminClickbait: { news: VolumeGroup; social: VolumeGroup; generated_at?: string } | null;
  adminUsers: { total_users: number; standard_users: number; admin_users: number; generated_at?: string } | null;
  adminHealth: { status: string; services: Record<string, { status: string; latency_ms?: number }>; generated_at?: string } | null;
  adminOperations: { articles_last_24h: number; total_articles: number; nlp_linked_articles: number; nlp_coverage_pct: number; latest_loaded_at?: string; freshness_minutes: number | null; generated_at?: string } | null;
  updatedAt?: string | null;
}

function rows(sources: string[] = [], values: number[] = [], key: string) {
  return sources.map((source, index) => ({ source: formatSourceName(source), [key]: Number(values[index] || 0) })).sort((a, b) => Number(b[key]) - Number(a[key]));
}

function formatFreshness(minutes: number | null | undefined) {
  if (minutes === null || minutes === undefined) return "Unknown";
  if (minutes < 2) return "Now";
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 1440) return `${(minutes / 60).toFixed(1)} h`;
  return `${(minutes / 1440).toFixed(1)} d`;
}

export default function AdminView({ adminLatency, adminClickbait, adminUsers, adminHealth, adminOperations, updatedAt }: AdminViewProps) {
  const latencyRows = rows(adminLatency?.sources, adminLatency?.avg_latency, "latency");
  const newsRows = rows(adminClickbait?.news?.sources, adminClickbait?.news?.volumes, "total");
  const socialRows = rows(adminClickbait?.social?.sources, adminClickbait?.social?.volumes, "total");
  const roleRows = adminUsers ? [{ name: "Standard users", count: Number(adminUsers.standard_users || 0), color: "#3b82f6" }, { name: "Admin users", count: Number(adminUsers.admin_users || 0), color: "#f97316" }] : [];
  const roleTotal = roleRows.reduce((sum, row) => sum + row.count, 0);
  const healthStatus = adminHealth?.status ?? "unknown";
  const healthyServices = Object.values(adminHealth?.services ?? {}).filter((service) => service.status === "healthy").length;
  const serviceCount = Object.keys(adminHealth?.services ?? {}).length;
  const healthDetails = Object.entries(adminHealth?.services ?? {}).map(([name, service]) => `${name}: ${service.status}${service.latency_ms ? ` (${service.latency_ms} ms)` : ""}`).join(" · ");
  const generatedAt = adminLatency?.generated_at ?? adminClickbait?.generated_at ?? updatedAt;
  const latency = Number(adminLatency?.overall_average ?? 0);
  const latencyTone = latency > Number(adminLatency?.sla_target ?? 5) ? "warning" : "default";
  const coverage = Number(adminOperations?.nlp_coverage_pct ?? 0);
  const coverageTone = coverage >= 95 ? "success" : coverage >= 70 ? "warning" : "danger";
  const freshness = adminOperations?.freshness_minutes;
  const freshnessTone = freshness === null || freshness === undefined ? "danger" : freshness <= 60 ? "success" : freshness <= 360 ? "warning" : "danger";
  const healthTone = healthStatus === "healthy" ? "success" : healthStatus === "degraded" ? "warning" : "danger";

  return <>
    <section className="overview-grid admin-metrics-grid" aria-label="Administrative summary metrics">
      <MetricCard label="Total users" value={formatCompactNumber(adminUsers?.total_users ?? 0)} hint={`${adminUsers?.admin_users ?? 0} administrators`} loading={adminUsers === null} />
      <MetricCard label="News articles" value={formatCompactNumber(adminClickbait?.news?.total ?? 0)} hint={`${newsRows.length} active sources`} loading={adminClickbait === null} />
      <MetricCard label="Social posts" value={formatCompactNumber(adminClickbait?.social?.total ?? 0)} hint={`${socialRows.length} active platforms`} loading={adminClickbait === null} />
      <MetricCard label="Articles ingested (24h)" value={formatCompactNumber(adminOperations?.articles_last_24h ?? 0)} hint="New warehouse records" loading={adminOperations === null} />
      <MetricCard label="Average crawl latency" value={`${latency.toFixed(1)} min`} hint={`SLA target ≤ ${adminLatency?.sla_target ?? 5} min`} loading={adminLatency === null} tone={latencyTone} />
      <MetricCard label="NLP coverage" value={formatPercent(coverage)} hint={`${formatCompactNumber(adminOperations?.nlp_linked_articles ?? 0)} of ${formatCompactNumber(adminOperations?.total_articles ?? 0)} articles`} loading={adminOperations === null} tone={coverageTone} />
      <MetricCard label="Data freshness" value={formatFreshness(freshness)} hint={adminOperations?.latest_loaded_at ? `Latest ingest ${formatDateTime(adminOperations.latest_loaded_at)}` : "No ingestion timestamp"} loading={adminOperations === null} tone={freshnessTone} />
      <MetricCard label="System health" value={healthStatus} hint={serviceCount ? `${healthyServices}/${serviceCount} dependencies available` : "Health data unavailable"} loading={adminHealth === null} tone={healthTone} title={healthDetails || undefined} />
    </section>

    <div className="charts-grid">
      <ChartCard wide title={<><Activity size={20} /> Crawl Latency by Source</>} description="Which sources exceed the crawl-latency service target?" timeRange="Current aggregate" unit="Minutes" total={latencyRows.length} updatedAt={generatedAt}>
        {adminLatency === null ? <ChartSkeleton /> : latencyRows.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={latencyRows} margin={{ top: 12, right: 12, left: 0, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.1)" /><XAxis dataKey="source" stroke="#94a3b8" fontSize={11} interval="preserveStartEnd" /><YAxis stroke="#94a3b8" fontSize={11} unit="m" allowDecimals={false} /><Tooltip formatter={(value) => [`${Number(value).toFixed(2)} minutes`, "Average latency"]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,.15)" }} /><ReferenceLine y={adminLatency.sla_target ?? 5} stroke="#f59e0b" strokeDasharray="5 5" label={{ value: `SLA ${adminLatency.sla_target ?? 5}m`, fill: "#fbbf24", fontSize: 11 }} /><Bar dataKey="latency" name="Average latency">{latencyRows.map((row) => <Cell key={row.source} fill={Number(row.latency) > (adminLatency.sla_target ?? 5) ? "#f97316" : "#3b82f6"} />)}</Bar></BarChart></ResponsiveContainer> : <EmptyState message="No latency data" />}
      </ChartCard>

      <ChartCard title={<><BookOpen size={20} /> News Volume</>} description="Which publishers contribute the most articles?" timeRange="All available data" unit="Articles" total={adminClickbait?.news?.total ?? 0} updatedAt={adminClickbait?.generated_at ?? updatedAt}>
        {adminClickbait === null ? <ChartSkeleton /> : newsRows.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={newsRows} layout="vertical" margin={{ left: 10, right: 12 }}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.1)" horizontal={false} /><XAxis type="number" tickFormatter={formatCompactNumber} allowDecimals={false} stroke="#94a3b8" fontSize={11} /><YAxis type="category" dataKey="source" width={90} stroke="#94a3b8" fontSize={11} /><Tooltip formatter={(value, _name, item) => [`${Number(value).toLocaleString()} · ${formatPercent((adminClickbait.news.total ? Number(value) / adminClickbait.news.total : 0) * 100)}`, item.payload.source]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,.15)" }} /><Bar dataKey="total" fill="#3b82f6" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer> : <EmptyState message="No news volume data" />}
      </ChartCard>

      <ChartCard title={<><Share2 size={20} /> Social Volume</>} description="Which social platforms contribute the most posts?" timeRange="All available data" unit="Posts" total={adminClickbait?.social?.total ?? 0} updatedAt={adminClickbait?.generated_at ?? updatedAt}>
        {adminClickbait === null ? <ChartSkeleton /> : socialRows.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={socialRows} layout="vertical" margin={{ left: 10, right: 12 }}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.1)" horizontal={false} /><XAxis type="number" tickFormatter={formatCompactNumber} allowDecimals={false} stroke="#94a3b8" fontSize={11} /><YAxis type="category" dataKey="source" width={90} stroke="#94a3b8" fontSize={11} /><Tooltip formatter={(value, _name, item) => [`${Number(value).toLocaleString()} · ${formatPercent((adminClickbait.social.total ? Number(value) / adminClickbait.social.total : 0) * 100)}`, item.payload.source]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,.15)" }} /><Bar dataKey="total" fill="#8b5cf6" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer> : <EmptyState message="No social volume data" />}
      </ChartCard>

      <ChartCard wide title={<><Users size={20} /> User Roles</>} description="How are registered accounts distributed by access level?" timeRange="Current snapshot" unit="Users and share" total={roleTotal} updatedAt={adminUsers?.generated_at ?? updatedAt}>
        {adminUsers === null ? <ChartSkeleton /> : roleTotal ? <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={roleRows} dataKey="count" nameKey="name" cx="50%" cy="45%" innerRadius="45%" outerRadius="72%">{roleRows.map((row) => <Cell key={row.name} fill={row.color} />)}</Pie><Tooltip formatter={(value, _name, item) => [`${Number(value).toLocaleString()} · ${formatPercent(Number(value) * 100 / roleTotal)}`, item.payload.name]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,.15)" }} /><Legend verticalAlign="bottom" /></PieChart></ResponsiveContainer> : <EmptyState message="No user data" />}
      </ChartCard>
    </div>
    <p className="chart-description admin-health-checked"><Server size={13} aria-hidden="true" /> Health checked {formatDateTime(adminHealth?.generated_at ?? updatedAt)}</p>
  </>;
}

"use client";

import { useState } from "react";
import { Activity, BellRing, BookOpen, Server, Share2, Users } from "lucide-react";
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
  adminAlertMetrics: AlertMetrics | null;
  updatedAt?: string | null;
}

interface AlertOperationMetric {
  requests: number;
  successes: number;
  not_found: number;
  errors: number;
  average_latency_ms: number;
  max_latency_ms: number;
}

interface AlertMetrics {
  scope: string;
  started_at: string;
  generated_at: string;
  uptime_seconds: number;
  totals: Pick<AlertOperationMetric, "requests" | "successes" | "not_found" | "errors">;
  operations: Record<string, AlertOperationMetric>;
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

function formatUptime(seconds: number | undefined) {
  if (!seconds) return "0 min";
  if (seconds < 60) return "<1 min";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)} h`;
  return `${(seconds / 86400).toFixed(1)} d`;
}

function formatOperationName(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function DetailList({ rows, emptyMessage = "No detail data available" }: { rows: Array<{ label: string; value: string | number }>; emptyMessage?: string }) {
  if (!rows.length) return <p className="chart-description">{emptyMessage}</p>;
  return <ul className="metric-details-list">{rows.map((row) => <li key={row.label}><span>{row.label}</span><strong>{row.value}</strong></li>)}</ul>;
}

export default function AdminView({ adminLatency, adminClickbait, adminUsers, adminHealth, adminOperations, adminAlertMetrics, updatedAt }: AdminViewProps) {
  const [activeMetric, setActiveMetric] = useState<string | null>(null);
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
  const alertTotals = adminAlertMetrics?.totals;
  const alertRequests = Number(alertTotals?.requests ?? 0);
  const alertErrors = Number(alertTotals?.errors ?? 0);
  const alertFailureRate = alertRequests ? (alertErrors * 100) / alertRequests : 0;
  const alertFailureTone = alertFailureRate >= 5 ? "danger" : alertFailureRate > 0 ? "warning" : "success";
  const alertOperationRows = Object.entries(adminAlertMetrics?.operations ?? {})
    .map(([operation, metric]) => ({
      operation: formatOperationName(operation),
      requests: Number(metric.requests || 0),
      successes: Number(metric.successes || 0),
      notFound: Number(metric.not_found || 0),
      errors: Number(metric.errors || 0),
      averageLatency: Number(metric.average_latency_ms || 0),
      maxLatency: Number(metric.max_latency_ms || 0),
    }))
    .sort((left, right) => right.requests - left.requests);
  const toggleMetric = (metric: string) => setActiveMetric((current) => current === metric ? null : metric);
  const interactiveMetric = (metric: string) => ({
    expanded: activeMetric === metric,
    onToggle: () => toggleMetric(metric),
  });
  const topRows = (data: Array<Record<string, unknown>>, labelKey: string, valueKey: string, suffix = "") => data.slice(0, 6).map((row) => ({
    label: String(row[labelKey]),
    value: `${Number(row[valueKey] || 0).toLocaleString()}${suffix}`,
  }));

  return <>
    <section className="overview-grid admin-metrics-grid" aria-label="Administrative summary metrics">
      <MetricCard {...interactiveMetric("users")} label="Total users" value={formatCompactNumber(adminUsers?.total_users ?? 0)} hint={`${adminUsers?.admin_users ?? 0} administrators`} loading={adminUsers === null} details={<DetailList rows={roleRows.map((row) => ({ label: row.name, value: row.count.toLocaleString() }))} />} />
      <MetricCard {...interactiveMetric("news")} label="News articles" value={formatCompactNumber(adminClickbait?.news?.total ?? 0)} hint={`${newsRows.length} active sources`} loading={adminClickbait === null} details={<DetailList rows={topRows(newsRows, "source", "total")} emptyMessage="No active news sources" />} />
      <MetricCard {...interactiveMetric("social")} label="Social posts" value={formatCompactNumber(adminClickbait?.social?.total ?? 0)} hint={`${socialRows.length} active platforms`} loading={adminClickbait === null} details={<DetailList rows={topRows(socialRows, "source", "total")} emptyMessage="No active social platforms" />} />
      <MetricCard {...interactiveMetric("ingested")} label="Articles ingested (24h)" value={formatCompactNumber(adminOperations?.articles_last_24h ?? 0)} hint="New warehouse records" loading={adminOperations === null} details={<DetailList rows={[
        { label: "Last 24 hours", value: Number(adminOperations?.articles_last_24h ?? 0).toLocaleString() },
        { label: "All warehouse articles", value: Number(adminOperations?.total_articles ?? 0).toLocaleString() },
        { label: "Latest ingest", value: adminOperations?.latest_loaded_at ? formatDateTime(adminOperations.latest_loaded_at) : "Unavailable" },
      ]} />} />
      <MetricCard {...interactiveMetric("latency")} label="Average crawl latency" value={`${latency.toFixed(1)} min`} hint={`SLA target ≤ ${adminLatency?.sla_target ?? 5} min`} loading={adminLatency === null} tone={latencyTone} details={<DetailList rows={topRows(latencyRows, "source", "latency", " min")} emptyMessage="No crawl latency samples" />} />
      <MetricCard {...interactiveMetric("nlp")} label="NLP coverage" value={formatPercent(coverage)} hint={`${formatCompactNumber(adminOperations?.nlp_linked_articles ?? 0)} of ${formatCompactNumber(adminOperations?.total_articles ?? 0)} articles`} loading={adminOperations === null} tone={coverageTone} details={<DetailList rows={[
        { label: "NLP enriched", value: Number(adminOperations?.nlp_linked_articles ?? 0).toLocaleString() },
        { label: "Pending NLP", value: Math.max(Number(adminOperations?.total_articles ?? 0) - Number(adminOperations?.nlp_linked_articles ?? 0), 0).toLocaleString() },
        { label: "Coverage", value: formatPercent(coverage) },
      ]} />} />
      <MetricCard {...interactiveMetric("freshness")} label="Data freshness" value={formatFreshness(freshness)} hint={adminOperations?.latest_loaded_at ? `Latest ingest ${formatDateTime(adminOperations.latest_loaded_at)}` : "No ingestion timestamp"} loading={adminOperations === null} tone={freshnessTone} details={<DetailList rows={[
        { label: "Latest warehouse ingest", value: adminOperations?.latest_loaded_at ? formatDateTime(adminOperations.latest_loaded_at) : "Unavailable" },
        { label: "Age", value: freshness === null || freshness === undefined ? "Unknown" : `${freshness.toFixed(1)} min` },
        { label: "Metrics generated", value: adminOperations?.generated_at ? formatDateTime(adminOperations.generated_at) : "Unavailable" },
      ]} />} />
      <MetricCard {...interactiveMetric("health")} label="System health" value={healthStatus} hint={serviceCount ? `${healthyServices}/${serviceCount} dependencies available` : "Health data unavailable"} loading={adminHealth === null} tone={healthTone} title={healthDetails || undefined} details={<DetailList rows={Object.entries(adminHealth?.services ?? {}).map(([name, service]) => ({ label: formatSourceName(name), value: `${service.status}${service.latency_ms !== undefined ? ` · ${service.latency_ms.toFixed(1)} ms` : ""}` }))} emptyMessage="No dependency health data" />} />
      <MetricCard {...interactiveMetric("alert-requests")} label="Alert API requests" value={formatCompactNumber(alertRequests)} hint={`${alertOperationRows.length} observed workflows`} loading={adminAlertMetrics === null} details={<DetailList rows={topRows(alertOperationRows, "operation", "requests")} emptyMessage="No alert workflows observed" />} />
      <MetricCard {...interactiveMetric("alert-failures")} label="Alert failures" value={formatPercent(alertFailureRate)} hint={`${alertErrors.toLocaleString()} failed requests`} loading={adminAlertMetrics === null} tone={alertFailureTone} details={<DetailList rows={alertOperationRows.filter((row) => row.errors > 0).slice(0, 6).map((row) => ({ label: row.operation, value: `${row.errors.toLocaleString()} failed` }))} emptyMessage="No alert failures observed" />} />
      <MetricCard {...interactiveMetric("missing-alerts")} label="Missing alert details" value={formatCompactNumber(alertTotals?.not_found ?? 0)} hint="Drill-down records no longer available" loading={adminAlertMetrics === null} tone={Number(alertTotals?.not_found ?? 0) ? "warning" : "success"} details={<DetailList rows={alertOperationRows.filter((row) => row.notFound > 0).slice(0, 6).map((row) => ({ label: row.operation, value: `${row.notFound.toLocaleString()} missing` }))} emptyMessage="No missing alert detail records" />} />
      <MetricCard {...interactiveMetric("alert-uptime")} label="Alert telemetry uptime" value={formatUptime(adminAlertMetrics?.uptime_seconds)} hint={`${adminAlertMetrics?.scope ?? "process-local"} counters`} loading={adminAlertMetrics === null} details={<DetailList rows={[
        { label: "Counter scope", value: adminAlertMetrics?.scope ?? "Unknown" },
        { label: "Started", value: adminAlertMetrics?.started_at ? formatDateTime(adminAlertMetrics.started_at) : "Unavailable" },
        { label: "Last updated", value: adminAlertMetrics?.generated_at ? formatDateTime(adminAlertMetrics.generated_at) : "Unavailable" },
      ]} />} />
    </section>

    <div className="charts-grid">
      <ChartCard wide title={<><Activity size={20} /> Crawl Latency by Source</>} description="Which sources exceed the crawl-latency service target?" timeRange="Current aggregate" unit="Minutes" total={latencyRows.length} updatedAt={generatedAt}>
        {adminLatency === null ? <ChartSkeleton /> : latencyRows.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={latencyRows} margin={{ top: 12, right: 12, left: 0, bottom: 8 }}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.1)" /><XAxis dataKey="source" stroke="#94a3b8" fontSize={11} interval="preserveStartEnd" /><YAxis stroke="#94a3b8" fontSize={11} unit="m" allowDecimals={false} /><Tooltip cursor={false} formatter={(value) => [`${Number(value).toFixed(2)} minutes`, "Average latency"]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,.15)" }} /><ReferenceLine y={adminLatency.sla_target ?? 5} stroke="#f59e0b" strokeDasharray="5 5" label={{ value: `SLA ${adminLatency.sla_target ?? 5}m`, fill: "#fbbf24", fontSize: 11 }} /><Bar dataKey="latency" name="Average latency">{latencyRows.map((row) => <Cell key={row.source} fill={Number(row.latency) > (adminLatency.sla_target ?? 5) ? "#f97316" : "#3b82f6"} />)}</Bar></BarChart></ResponsiveContainer> : <EmptyState message="No latency data" />}
      </ChartCard>

      <ChartCard title={<><BookOpen size={20} /> News Volume</>} description="Which publishers contribute the most articles?" timeRange="All available data" unit="Articles" total={adminClickbait?.news?.total ?? 0} updatedAt={adminClickbait?.generated_at ?? updatedAt}>
        {adminClickbait === null ? <ChartSkeleton /> : newsRows.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={newsRows} layout="vertical" margin={{ left: 10, right: 12 }}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.1)" horizontal={false} /><XAxis type="number" tickFormatter={formatCompactNumber} allowDecimals={false} stroke="#94a3b8" fontSize={11} /><YAxis type="category" dataKey="source" width={90} stroke="#94a3b8" fontSize={11} /><Tooltip cursor={false} formatter={(value, _name, item) => [`${Number(value).toLocaleString()} · ${formatPercent((adminClickbait.news.total ? Number(value) / adminClickbait.news.total : 0) * 100)}`, item.payload.source]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,.15)" }} /><Bar dataKey="total" fill="#3b82f6" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer> : <EmptyState message="No news volume data" />}
      </ChartCard>

      <ChartCard title={<><Share2 size={20} /> Social Volume</>} description="Which social platforms contribute the most posts?" timeRange="All available data" unit="Posts" total={adminClickbait?.social?.total ?? 0} updatedAt={adminClickbait?.generated_at ?? updatedAt}>
        {adminClickbait === null ? <ChartSkeleton /> : socialRows.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={socialRows} layout="vertical" margin={{ left: 10, right: 12 }}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.1)" horizontal={false} /><XAxis type="number" tickFormatter={formatCompactNumber} allowDecimals={false} stroke="#94a3b8" fontSize={11} /><YAxis type="category" dataKey="source" width={90} stroke="#94a3b8" fontSize={11} /><Tooltip cursor={false} formatter={(value, _name, item) => [`${Number(value).toLocaleString()} · ${formatPercent((adminClickbait.social.total ? Number(value) / adminClickbait.social.total : 0) * 100)}`, item.payload.source]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,.15)" }} /><Bar dataKey="total" fill="#8b5cf6" radius={[0, 4, 4, 0]} /></BarChart></ResponsiveContainer> : <EmptyState message="No social volume data" />}
      </ChartCard>

      <ChartCard wide title={<><Users size={20} /> User Roles</>} description="How are registered accounts distributed by access level?" timeRange="Current snapshot" unit="Users and share" total={roleTotal} updatedAt={adminUsers?.generated_at ?? updatedAt}>
        {adminUsers === null ? <ChartSkeleton /> : roleTotal ? <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={roleRows} dataKey="count" nameKey="name" cx="50%" cy="45%" innerRadius="45%" outerRadius="72%">{roleRows.map((row) => <Cell key={row.name} fill={row.color} />)}</Pie><Tooltip formatter={(value, _name, item) => [`${Number(value).toLocaleString()} · ${formatPercent(Number(value) * 100 / roleTotal)}`, item.payload.name]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,.15)" }} /><Legend verticalAlign="bottom" /></PieChart></ResponsiveContainer> : <EmptyState message="No user data" />}
      </ChartCard>

      <ChartCard wide title={<><BellRing size={20} /> Alert Workflow Outcomes</>} description="Which alert workflows are succeeding, missing data, or failing?" timeRange="Since API process start" unit="Requests" total={alertRequests} updatedAt={adminAlertMetrics?.generated_at ?? updatedAt}>
        {adminAlertMetrics === null ? <ChartSkeleton /> : alertOperationRows.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={alertOperationRows} margin={{ top: 12, right: 12, left: 0, bottom: 28 }}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.1)" /><XAxis dataKey="operation" stroke="#94a3b8" fontSize={10} angle={-12} textAnchor="end" interval={0} height={58} /><YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} /><Tooltip cursor={false} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,.15)" }} /><Legend /><Bar dataKey="successes" name="Succeeded" stackId="outcome" fill="#10b981" /><Bar dataKey="notFound" name="Not found" stackId="outcome" fill="#f59e0b" /><Bar dataKey="errors" name="Failed" stackId="outcome" fill="#ef4444" /></BarChart></ResponsiveContainer> : <EmptyState message="No alert workflow requests observed since the API started" />}
      </ChartCard>

      <ChartCard wide title={<><Activity size={20} /> Alert Workflow Latency</>} description="Where is alert investigation spending the most response time?" timeRange="Since API process start" unit="Milliseconds" total={alertOperationRows.length} updatedAt={adminAlertMetrics?.generated_at ?? updatedAt}>
        {adminAlertMetrics === null ? <ChartSkeleton /> : alertOperationRows.length ? <ResponsiveContainer width="100%" height="100%"><BarChart data={alertOperationRows} margin={{ top: 12, right: 12, left: 0, bottom: 28 }}><CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.1)" /><XAxis dataKey="operation" stroke="#94a3b8" fontSize={10} angle={-12} textAnchor="end" interval={0} height={58} /><YAxis stroke="#94a3b8" fontSize={11} unit="ms" allowDecimals={false} /><Tooltip cursor={false} formatter={(value) => [`${Number(value).toFixed(2)} ms`]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,.15)" }} /><Legend /><Bar dataKey="averageLatency" name="Average" fill="#3b82f6" radius={[4, 4, 0, 0]} /><Bar dataKey="maxLatency" name="Maximum" fill="#8b5cf6" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer> : <EmptyState message="No latency samples observed since the API started" />}
      </ChartCard>
    </div>
    <p className="chart-description admin-health-checked"><Server size={13} aria-hidden="true" /> Health checked {formatDateTime(adminHealth?.generated_at ?? updatedAt)}</p>
  </>;
}

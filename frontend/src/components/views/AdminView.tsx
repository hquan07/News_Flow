"use client";

import { Activity, BookOpen, Server, Share2, Users } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import ChartCard from "../ui/ChartCard";
import EmptyState from "../ui/EmptyState";
import ChartSkeleton from "../ui/ChartSkeleton";
import { formatCompactNumber, formatDateTime, formatPercent, formatSourceName } from "@/lib/formatters";

function rows(sources: string[] = [], values: number[] = [], key: string) {
  return sources.map((source, index) => ({ source: formatSourceName(source), [key]: Number(values[index] || 0) })).sort((a, b) => Number(b[key]) - Number(a[key]));
}

export default function AdminView({ adminLatency, adminClickbait, adminUsers, adminHealth, updatedAt }: any) {
  const latencyRows = rows(adminLatency?.sources, adminLatency?.avg_latency, "latency");
  const newsRows = rows(adminClickbait?.news?.sources, adminClickbait?.news?.volumes, "total");
  const socialRows = rows(adminClickbait?.social?.sources, adminClickbait?.social?.volumes, "total");
  const roleRows = adminUsers ? [{ name: "Standard users", count: Number(adminUsers.standard_users || 0), color: "#3b82f6" }, { name: "Admin users", count: Number(adminUsers.admin_users || 0), color: "#f97316" }] : [];
  const roleTotal = roleRows.reduce((sum, row) => sum + row.count, 0);
  const healthStatus = adminHealth?.status ?? "unknown";
  const healthColor = healthStatus === "healthy" ? "#10b981" : healthStatus === "degraded" ? "#f59e0b" : "#ef4444";
  const generatedAt = adminLatency?.generated_at ?? adminClickbait?.generated_at ?? updatedAt;

  const summary = [
    { label: "Total users", value: formatCompactNumber(adminUsers?.total_users ?? 0), hint: `${adminUsers?.admin_users ?? 0} administrators` },
    { label: "Average crawl latency", value: `${Number(adminLatency?.overall_average ?? 0).toFixed(1)} min`, hint: `SLA target ≤ ${adminLatency?.sla_target ?? 5} min` },
    { label: "News articles", value: formatCompactNumber(adminClickbait?.news?.total ?? 0), hint: `${newsRows.length} active sources` },
    { label: "Social posts", value: formatCompactNumber(adminClickbait?.social?.total ?? 0), hint: `${socialRows.length} active platforms` },
  ];

  return <>
    <div className="overview-grid">
      {summary.map((metric) => <div className="glass-panel metric-card" key={metric.label}><div className="metric-content"><div className="metric-label">{metric.label}</div><div className="metric-value">{metric.value}</div><div className="chart-description">{metric.hint}</div></div></div>)}
      <div className="glass-panel metric-card"><div className="metric-content"><div className="metric-label">System health</div><div className="metric-value" style={{ background: "none", WebkitTextFillColor: healthColor, color: healthColor, textTransform: "capitalize" }}>{healthStatus}</div><div className="chart-description">{Object.entries(adminHealth?.services ?? {}).map(([name, service]: any) => `${name}: ${service.status}${service.latency_ms ? ` (${service.latency_ms} ms)` : ""}`).join(" · ") || "Health data unavailable"}</div></div></div>
    </div>

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
    <p className="chart-description" style={{ textAlign: "right" }}><Server size={13} style={{ verticalAlign: "middle" }} /> Health checked {formatDateTime(adminHealth?.generated_at ?? updatedAt)}</p>
  </>;
}

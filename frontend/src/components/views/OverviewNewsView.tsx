"use client";

import { Area, AreaChart, Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Activity, BarChart2, FileText } from "lucide-react";
import ChartCard from "../ui/ChartCard";
import EmptyState from "../ui/EmptyState";
import ChartSkeleton from "../ui/ChartSkeleton";
import { formatCategoryName, formatCompactNumber, formatPercent, truncateLabel } from "@/lib/formatters";

interface TrendPoint { time: string; count: number }
interface CategoryPoint { name: string; count: number; percentage?: number }

export default function OverviewNewsView({ overviewData, chartData, sourceData, activeCard, setActiveCard, exportToCSV, canExportCSV, updatedAt }: any) {
  const trendData: TrendPoint[] = chartData ?? [];
  const trendTotal = trendData.reduce((sum, row) => sum + Number(row.count || 0), 0);
  const categoryTotal = (sourceData ?? []).reduce((sum: number, row: CategoryPoint) => sum + Number(row.count || 0), 0);
  const sortedCategories: CategoryPoint[] = [...(sourceData ?? [])].sort((a, b) => b.count - a.count);
  const categoryData = sortedCategories.slice(0, 8);
  const otherCount = sortedCategories.slice(8).reduce((sum, row) => sum + row.count, 0);
  if (otherCount > 0) categoryData.push({ name: "Other", count: otherCount });
  const categoryRows = categoryData.map((row) => ({
    ...row,
    label: formatCategoryName(row.name),
    percentage: categoryTotal ? (row.count / categoryTotal) * 100 : 0,
  }));

  return (
    <>
      <div className="overview-grid">
        {overviewData?.kpi_cards?.map((kpi: any, i: number) => {
          let details = null;
          if ((i === 0 || i === 1 || i === 3) && overviewData.source_speed) {
            details = <ul className="metric-details-list">{overviewData.source_speed.map((source: any) => (
              <li key={source.source}>
                <span>{source.source}</span>
                {i === 1 ? (
                  <strong className="metric-active-status"><span className="metric-active-dot" aria-hidden="true" />Active</strong>
                ) : (
                  <strong>{i === 3 ? `${Number(source.avg_latency_min).toFixed(1)} min` : formatCompactNumber(source.article_count)}</strong>
                )}
              </li>
            ))}</ul>;
          } else if (i === 2) {
            details = <ul className="metric-details-list">{categoryRows.slice(0, 5).map((category) => (
              <li key={category.name}><span>{category.label}</span><strong>{category.count} ({formatPercent(category.percentage, 0)})</strong></li>
            ))}</ul>;
          }
          return (
            <button type="button" key={kpi.label} className={`glass-panel metric-card ${activeCard === i ? "expanded" : ""}`} onClick={() => setActiveCard(activeCard === i ? null : i)}>
              {activeCard !== i ? <div className="metric-content"><div className="metric-label">{kpi.label}</div><div className="metric-value">{kpi.value}</div><div className="metric-hint">View details →</div></div> : <div className="metric-details"><div className="metric-label">{kpi.label} details</div>{details}</div>}
            </button>
          );
        })}
        {!overviewData?.kpi_cards && <div style={{ gridColumn: "1 / -1", height: 120 }}><ChartSkeleton /></div>}
      </div>

      <div className="charts-grid">
        <ChartCard title={<><BarChart2 size={20} /> Publication Trend</>} description="How many articles were published in each hourly bucket?" timeRange="All available data · hour of day" unit="Articles" total={trendTotal} updatedAt={updatedAt} actions={canExportCSV ? <button type="button" onClick={() => exportToCSV(trendData, "publication_trend.csv")} className="chart-action-button print-hide"><FileText size={14} /> CSV</button> : undefined}>
          {trendData.length > 0 ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={trendData} margin={{ top: 12, right: 10, left: 0, bottom: 4 }}>
            <defs><linearGradient id="publicationCount" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#3b82f6" stopOpacity={0.65} /><stop offset="95%" stopColor="#3b82f6" stopOpacity={0.03} /></linearGradient></defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
            <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} interval="preserveStartEnd" minTickGap={28} />
            <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} tickFormatter={formatCompactNumber} />
            <Tooltip labelFormatter={(label) => `${label}`} formatter={(value) => [`${Number(value).toLocaleString()} articles`, "Published"]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }} />
            <Area type="linear" dataKey="count" name="Articles" stroke="#60a5fa" strokeWidth={2} fill="url(#publicationCount)" connectNulls={false} />
          </AreaChart></ResponsiveContainer> : !overviewData ? <ChartSkeleton /> : <EmptyState message="No publication trend data" />}
        </ChartCard>

        <ChartCard title={<><Activity size={20} /> Category Distribution</>} description="Which categories account for the largest share of coverage?" timeRange="All available data" unit="Articles and share" total={categoryTotal} updatedAt={updatedAt}>
          {categoryRows.length > 0 ? <ResponsiveContainer width="100%" height="100%"><BarChart data={categoryRows} layout="vertical" margin={{ top: 5, right: 48, left: 12, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={false} />
            <XAxis type="number" stroke="#94a3b8" fontSize={11} allowDecimals={false} tickFormatter={formatCompactNumber} />
            <YAxis type="category" dataKey="label" width={92} stroke="#94a3b8" fontSize={11} tickFormatter={(value) => truncateLabel(String(value), 14)} />
            <Tooltip cursor={false} formatter={(value, _name, item) => [`${Number(value).toLocaleString()} articles (${formatPercent(item.payload.percentage)})`, item.payload.label]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }} />
            <Bar dataKey="count" name="Articles" fill="#8b5cf6" radius={[0, 4, 4, 0]}><LabelList dataKey="percentage" position="right" fill="#cbd5e1" fontSize={10} formatter={(value) => formatPercent(Number(value), 0)} /></Bar>
          </BarChart></ResponsiveContainer> : !overviewData ? <ChartSkeleton /> : <EmptyState message="No category data" />}
        </ChartCard>
      </div>
    </>
  );
}

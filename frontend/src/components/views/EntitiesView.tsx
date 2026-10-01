"use client";

import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Cell, LabelList, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis, type TooltipContentProps } from "recharts";
import { Hash, MessageSquare, ThumbsUp, Users } from "lucide-react";
import ChartCard from "../ui/ChartCard";
import EmptyState from "../ui/EmptyState";
import ChartSkeleton from "../ui/ChartSkeleton";
import ColoredTooltipValue, { DARK_TOOLTIP_CONTENT_STYLE, DARK_TOOLTIP_ITEM_STYLE, readableChartColor } from "../ui/ColoredTooltipValue";
import { formatCompactNumber, formatPercent, truncateLabel } from "@/lib/formatters";

const TYPE_COLORS: Record<string, string> = { PER: "#f97316", PERSON: "#f97316", LOC: "#8b5cf6", LOCATION: "#8b5cf6", ORG: "#10b981", ORGANIZATION: "#10b981" };
const SENTIMENT_COLORS = { Positive: "#10b981", Neutral: "#94a3b8", Negative: "#f97316" };

function entityColor(type: unknown): string {
  return TYPE_COLORS[String(type).toUpperCase()] ?? "#3b82f6";
}

function EntityBarTooltip({ active, payload }: TooltipContentProps) {
  const row = payload?.[0]?.payload as { entity_name?: string; entity_type?: string; mention_count?: number } | undefined;
  if (!active || !row) return null;
  const color = entityColor(row.entity_type);
  return <div className="entity-bar-tooltip">
    <div className="entity-bar-tooltip-title">{row.entity_name}</div>
    <div className="entity-bar-tooltip-detail" style={{ color: readableChartColor(color) }}>
      <span className="entity-bar-tooltip-swatch" style={{ backgroundColor: color }} aria-hidden="true" />
      {row.entity_name} · {row.entity_type}: {Number(row.mention_count ?? 0).toLocaleString()} mentions
    </div>
  </div>;
}

function value(row: Record<string, unknown>, key: string): number {
  const match = Object.keys(row).find((candidate) => candidate.toLowerCase() === key.toLowerCase());
  return Number(match ? row[match] : 0) || 0;
}

export default function EntitiesView({ entitiesData, trendingKeywords, entityTypeDist, entitySentiment, updatedAt }: any) {
  const [topN, setTopN] = useState(10);
  const entities = useMemo(() => [...(entitiesData ?? [])].sort((a: any, b: any) => b.mention_count - a.mention_count).slice(0, topN), [entitiesData, topN]);
  const keywords = useMemo(() => [...(trendingKeywords ?? [])].sort((a: any, b: any) => b.count - a.count).slice(0, 12), [trendingKeywords]);
  const typeData = useMemo(() => (entityTypeDist ?? []).map((row: any) => ({ ...row, type: String(row.entity_type).toUpperCase(), color: TYPE_COLORS[String(row.entity_type).toUpperCase()] ?? "#3b82f6" })), [entityTypeDist]);
  const typeTotal = typeData.reduce((sum: number, row: any) => sum + Number(row.count || 0), 0);
  const sentimentRows = useMemo(() => (entitySentiment ?? []).map((row: Record<string, unknown>) => {
    const Positive = value(row, "Positive"); const Neutral = value(row, "Neutral"); const Negative = value(row, "Negative");
    const total = Positive + Neutral + Negative;
    return { entity: String(row.entity ?? row.entity_name ?? "Unknown"), total, Positive, Neutral, Negative, PositivePct: total ? Positive * 100 / total : 0, NeutralPct: total ? Neutral * 100 / total : 0, NegativePct: total ? Negative * 100 / total : 0 };
  }).sort((a: any, b: any) => b.total - a.total).slice(0, topN), [entitySentiment, topN]);

  const topNControl = <label className="top-n-control"><span>Top</span><select aria-label="Number of top entities" value={topN} onChange={(event) => setTopN(Number(event.target.value))}>{[10, 20, 50].map((limit) => <option key={limit} value={limit}>{limit}</option>)}</select></label>;

  return <div className="charts-grid">
    <ChartCard title={<><Users size={20} /> Top Entities</>} description="Which named entities receive the most mentions?" timeRange="Last 7 days" unit="Mentions" total={(entitiesData ?? []).reduce((sum: number, row: any) => sum + Number(row.mention_count || 0), 0)} updatedAt={updatedAt} actions={topNControl} large>
      {entities.length > 0 ? <ResponsiveContainer width="100%" height="100%"><BarChart data={entities} layout="vertical" margin={{ left: 12, right: 46 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={false} />
        <XAxis type="number" stroke="#94a3b8" fontSize={11} allowDecimals={false} tickFormatter={formatCompactNumber} />
        <YAxis type="category" dataKey="entity_name" width={112} stroke="#94a3b8" fontSize={11} tickFormatter={(label) => truncateLabel(String(label), 18)} />
        <Tooltip cursor={false} content={EntityBarTooltip} />
        <Bar dataKey="mention_count" name="Mentions" radius={[0, 4, 4, 0]}>
          {entities.map((row: any) => <Cell key={row.entity_name} fill={entityColor(row.entity_type)} />)}
          <LabelList dataKey="mention_count" position="right" content={({ x, y, width, height, index, value }) => (
            <text x={Number(x) + Number(width) + 4} y={Number(y) + Number(height) / 2}
              dominantBaseline="central" fill={readableChartColor(entityColor(entities[Number(index)]?.entity_type))} fontSize={10}>
              {formatCompactNumber(Number(value))}
            </text>
          )} />
        </Bar>
      </BarChart></ResponsiveContainer> : !entitiesData ? <ChartSkeleton /> : <EmptyState message="No entity data" />}
    </ChartCard>

    <ChartCard title={<><Hash size={20} /> Trending Keywords</>} description="Which keywords occur most frequently? Ranked bars preserve accurate comparison." timeRange="Last 7 days" unit="Occurrences" total={(trendingKeywords ?? []).reduce((sum: number, row: any) => sum + Number(row.count || 0), 0)} updatedAt={updatedAt} large>
      {keywords.length > 0 ? <ResponsiveContainer width="100%" height="100%"><BarChart data={keywords} layout="vertical" margin={{ left: 0, right: 16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={false} />
        <XAxis type="number" stroke="#94a3b8" fontSize={11} allowDecimals={false} tickFormatter={formatCompactNumber} />
        <YAxis type="category" dataKey="keyword" width={88} stroke="#94a3b8" fontSize={11} tickFormatter={(label) => truncateLabel(String(label), 17)} />
        <Tooltip cursor={false} formatter={(count, _name, item) => [`${Number(count).toLocaleString()} occurrences`, item.payload.keyword]} contentStyle={DARK_TOOLTIP_CONTENT_STYLE} itemStyle={DARK_TOOLTIP_ITEM_STYLE} labelStyle={DARK_TOOLTIP_ITEM_STYLE} />
        <Bar dataKey="count" fill="#38bdf8" radius={[0, 4, 4, 0]}><LabelList dataKey="count" position="right" fill="#cbd5e1" fontSize={10} /></Bar>
      </BarChart></ResponsiveContainer> : !trendingKeywords ? <ChartSkeleton /> : <EmptyState message="No keyword data" />}
    </ChartCard>

    <ChartCard title={<><MessageSquare size={20} /> Entity Types</>} description="How are mentions distributed across people, locations and organizations?" timeRange="Last 7 days" unit="Entities and share" total={typeTotal} updatedAt={updatedAt}>
      {typeData.length > 0 ? <ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={typeData} dataKey="count" nameKey="type" cx="50%" cy="45%" innerRadius="42%" outerRadius="70%" labelLine={false}>{typeData.map((row: any) => <Cell key={row.type} fill={row.color} />)}</Pie><Tooltip formatter={(count, _name, item) => [<ColoredTooltipValue key="value" color={String(item.payload.color)}>{Number(count).toLocaleString()} ({formatPercent(typeTotal ? Number(count) * 100 / typeTotal : 0)})</ColoredTooltipValue>, item.payload.type]} contentStyle={DARK_TOOLTIP_CONTENT_STYLE} itemStyle={DARK_TOOLTIP_ITEM_STYLE} labelStyle={DARK_TOOLTIP_ITEM_STYLE} /><Legend verticalAlign="bottom" /></PieChart></ResponsiveContainer> : !entityTypeDist ? <ChartSkeleton /> : <EmptyState message="No entity type data" />}
    </ChartCard>

    <ChartCard title={<><ThumbsUp size={20} /> Sentiment by Entity</>} description="How does sentiment composition compare for the most-mentioned entities?" timeRange="Last 7 days" unit="Share of mentions" total={sentimentRows.reduce((sum: number, row: any) => sum + row.total, 0)} updatedAt={updatedAt} large>
      {sentimentRows.length > 0 ? <ResponsiveContainer width="100%" height="100%"><BarChart data={sentimentRows} layout="vertical" margin={{ left: 0, right: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={false} />
        <XAxis type="number" domain={[0, 100]} tickFormatter={(tick) => `${Math.round(Number(tick))}%`} stroke="#94a3b8" fontSize={11} />
        <YAxis type="category" dataKey="entity" width={100} tickFormatter={(label) => truncateLabel(String(label), 18)} stroke="#94a3b8" fontSize={11} />
        <Tooltip cursor={false} formatter={(_pct, name, item) => { const key = String(name).replace("Pct", "") as keyof typeof SENTIMENT_COLORS; return [<ColoredTooltipValue key="value" color={SENTIMENT_COLORS[key] ?? "#f8fafc"}>{Number(item.payload[key] ?? 0).toLocaleString()} · {formatPercent(item.payload[`${key}Pct`])}</ColoredTooltipValue>, key]; }} contentStyle={DARK_TOOLTIP_CONTENT_STYLE} itemStyle={DARK_TOOLTIP_ITEM_STYLE} labelStyle={DARK_TOOLTIP_ITEM_STYLE} />
        <Legend formatter={(name) => String(name).replace("Pct", "")} />
        {(Object.keys(SENTIMENT_COLORS) as Array<keyof typeof SENTIMENT_COLORS>).map((key) => <Bar key={key} dataKey={`${key}Pct`} stackId="sentiment" fill={SENTIMENT_COLORS[key]} />)}
      </BarChart></ResponsiveContainer> : !entitySentiment ? <ChartSkeleton /> : <EmptyState message="No entity sentiment data" />}
    </ChartCard>
  </div>;
}

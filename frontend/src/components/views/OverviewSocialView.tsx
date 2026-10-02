"use client";

import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Activity } from "lucide-react";
import ChartCard from "../ui/ChartCard";
import ChartSkeleton from "../ui/ChartSkeleton";
import EmptyState from "../ui/EmptyState";
import ColoredTooltipValue, { DARK_TOOLTIP_CONTENT_STYLE, DARK_TOOLTIP_ITEM_STYLE } from "../ui/ColoredTooltipValue";
import { formatCompactNumber } from "@/lib/formatters";

const ENGAGEMENT_COLORS = { Likes: "#3b82f6", Replies: "#ec4899" } as const;

export default function OverviewSocialView({
  overviewData,
  activeCard,
  setActiveCard,
  updatedAt,
}: any) {
  const engagementTotal = (overviewData?.engagement_timeline ?? []).reduce(
    (sum: number, row: any) => sum + Number(row.Likes || 0) + Number(row.Replies || 0),
    0,
  );
  return (
    <>
      <>
        <div className="overview-grid">
          {overviewData?.kpi_cards?.map((kpi: any, i: number) => {
            let details = null;
            if (i === 0 && overviewData.source_distribution) {
              details = (
                <ul className="metric-details-list">
                  {overviewData.source_distribution.map((s: any) => (
                    <li key={s.source}>
                      <span style={{ textTransform: "capitalize" }}>
                        {s.source}
                      </span>
                      <strong>{s.count}</strong>
                    </li>
                  ))}
                </ul>
              );
            } else if (i === 1 && overviewData.likes_distribution) {
              details = (
                <ul className="metric-details-list">
                  {overviewData.likes_distribution.map((s: any) => (
                    <li key={s.source}>
                      <span style={{ textTransform: "capitalize" }}>
                        {s.source}
                      </span>
                      <strong>{s.count}</strong>
                    </li>
                  ))}
                </ul>
              );
            } else if (i === 2 && overviewData.replies_distribution) {
              details = (
                <ul className="metric-details-list">
                  {overviewData.replies_distribution.map((s: any) => (
                    <li key={s.source}>
                      <span style={{ textTransform: "capitalize" }}>
                        {s.source}
                      </span>
                      <strong>{s.count}</strong>
                    </li>
                  ))}
                </ul>
              );
            } else if (i === 3 && overviewData.source_distribution) {
              details = (
                <ul className="metric-details-list">
                  {overviewData.source_distribution.map((s: any) => (
                    <li key={s.source}>
                      <span style={{ textTransform: "capitalize" }}>
                        {s.source}
                      </span>
                      <span
                        style={{
                          color: "var(--accent-green)",
                          fontSize: "0.8rem",
                        }}
                      >
                        ● Active
                      </span>
                    </li>
                  ))}
                </ul>
              );
            }

            return (
              <button
                type="button"
                key={i}
                className={`glass-panel metric-card ${activeCard === i + 20 ? "expanded" : ""}`}
                aria-expanded={activeCard === i + 20}
                onClick={() =>
                  setActiveCard(activeCard === i + 20 ? null : i + 20)
                }
              >
                <div
                  className="metric-content"
                  style={{
                    display: activeCard === i + 20 ? "none" : "block",
                  }}
                >
                  <div className="metric-label">{kpi.label}</div>
                  <div className="metric-value">{kpi.value}</div>
                  <div className="metric-hint">View details →</div>
                </div>
                {activeCard === i + 20 && (
                  <div className="metric-details">
                    <div
                      className="metric-label"
                      style={{
                        marginBottom: "8px",
                        borderBottom: "1px solid rgba(255,255,255,0.1)",
                        paddingBottom: "4px",
                      }}
                    >
                      {kpi.label} details
                    </div>
                    {details}
                  </div>
                )}
              </button>
            );
          })}
        </div>

        <div className="charts-grid">
          <ChartCard wide title={<><Activity size={20} /> Engagement Timeline</>} description="How do likes and replies change across time buckets?" timeRange="All available data" unit="Interactions" total={engagementTotal} updatedAt={updatedAt}>
              {overviewData?.engagement_timeline?.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={overviewData.engagement_timeline}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.1)"
                    />
                    <XAxis
                      dataKey="time"
                      stroke="#94a3b8"
                      fontSize={12}
                      tickFormatter={(t) =>
                        new Date(t).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })
                      }
                    />
                    <YAxis stroke="#94a3b8" fontSize={12} allowDecimals={false} tickFormatter={formatCompactNumber} />
                    <Tooltip
                      labelFormatter={(t) =>
                        new Date(t as string).toLocaleString()
                      }
                      formatter={(value, name) => [<ColoredTooltipValue key="value" color={ENGAGEMENT_COLORS[name as keyof typeof ENGAGEMENT_COLORS] ?? "#f8fafc"}>{Number(value).toLocaleString()}</ColoredTooltipValue>, name]}
                      contentStyle={DARK_TOOLTIP_CONTENT_STYLE}
                      itemStyle={DARK_TOOLTIP_ITEM_STYLE}
                      labelStyle={DARK_TOOLTIP_ITEM_STYLE}
                    />
                    <Legend />
                    <Line
                      type="linear"
                      dataKey="Likes"
                      stroke={ENGAGEMENT_COLORS.Likes}
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="linear"
                      dataKey="Replies"
                      stroke={ENGAGEMENT_COLORS.Replies}
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : !overviewData ? <ChartSkeleton /> : <EmptyState message="No engagement timeline data" />}
          </ChartCard>
        </div>
      </>
    </>
  );
}

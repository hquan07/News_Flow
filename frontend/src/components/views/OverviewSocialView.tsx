"use client";

import React, { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import {
  Activity,
  BarChart2,
  ThumbsUp,
  MessageSquare,
  Hash,
} from "lucide-react";

export default function OverviewSocialView({
  overviewData,
  activeCard,
  setActiveCard,
}: any) {
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
              <div
                key={i}
                className={`glass-panel metric-card ${activeCard === i + 20 ? "expanded" : ""}`}
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
                  <div className="metric-hint">Click để xem chi tiết</div>
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
                      {kpi.label} (Chi tiết)
                    </div>
                    {details}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="charts-grid">
          <div className="glass-panel" style={{ gridColumn: "1 / -1" }}>
            <div className="panel-header">
              <div className="panel-title">
                <Activity size={20} /> Engagement Timeline
              </div>
            </div>
            <div style={{ height: 300, width: "100%" }}>
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
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip
                      labelFormatter={(t) =>
                        new Date(t as string).toLocaleString()
                      }
                      contentStyle={{
                        backgroundColor: "rgba(30, 41, 59, 0.9)",
                        border: "1px solid rgba(255,255,255,0.1)",
                      }}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="Likes"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="Replies"
                      stroke="#ec4899"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100%",
                    color: "var(--text-muted)",
                  }}
                >
                  No timeline data available
                </div>
              )}
            </div>
          </div>
        </div>
      </>
    </>
  );
}

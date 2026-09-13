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
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { Activity, BarChart2, Hash, ThumbsUp, BookOpen , FileText } from "lucide-react";

export default function OverviewNewsView({
  overviewData,
  chartData,
  sourceData,
  activeCard,
  setActiveCard,
  exportToCSV,
}: any) {
  return (
    <>
      <>
        <div className="overview-grid">
          {overviewData?.kpi_cards?.map((kpi: any, i: number) => {
            let details = null;
            if (i === 0 && overviewData.source_speed) {
              details = (
                <ul className="metric-details-list">
                  {overviewData.source_speed.map((s: any) => (
                    <li key={s.source}>
                      <span style={{ textTransform: "capitalize" }}>
                        {s.source}
                      </span>
                      <strong>{s.article_count}</strong>
                    </li>
                  ))}
                </ul>
              );
            } else if (i === 1 && overviewData.source_speed) {
              details = (
                <ul className="metric-details-list">
                  {overviewData.source_speed.map((s: any) => (
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
                        ● Hoạt động
                      </span>
                    </li>
                  ))}
                </ul>
              );
            } else if (i === 2 && overviewData.category_distribution) {
              const total =
                overviewData.category_distribution.reduce(
                  (acc: number, c: any) => acc + c.count,
                  0,
                ) || 1;
              details = (
                <ul className="metric-details-list">
                  {overviewData.category_distribution
                    .slice(0, 5)
                    .map((c: any) => (
                      <li key={c.category}>
                        <span style={{ textTransform: "capitalize" }}>
                          {c.category}
                        </span>
                        <span>
                          <strong>{c.count}</strong>
                          <span
                            style={{
                              color: "var(--text-muted)",
                              fontSize: "0.8rem",
                              marginLeft: "6px",
                            }}
                          >
                            ({Math.round((c.count / total) * 100)}%)
                          </span>
                        </span>
                      </li>
                    ))}
                </ul>
              );
            } else if (i === 3 && overviewData.source_speed) {
              details = (
                <ul className="metric-details-list">
                  {overviewData.source_speed
                    .filter((s: any) => s.avg_latency_min > 0)
                    .map((s: any) => (
                      <li key={s.source}>
                        <span style={{ textTransform: "capitalize" }}>
                          {s.source}
                        </span>
                        <strong>{s.avg_latency_min.toFixed(1)} min</strong>
                      </li>
                    ))}
                </ul>
              );
            }

            return (
              <div
                key={i}
                className={`glass-panel metric-card ${activeCard === i ? "expanded" : ""}`}
                onClick={() => setActiveCard(activeCard === i ? null : i)}
              >
                <div
                  className="metric-content"
                  style={{ display: activeCard === i ? "none" : "block" }}
                >
                  <div className="metric-label">{kpi.label}</div>
                  <div className="metric-value">{kpi.value}</div>
                  <div className="metric-hint">Click để xem chi tiết</div>
                </div>
                {activeCard === i && (
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
          {!overviewData?.kpi_cards && (
            <div style={{ color: "var(--text-muted)" }}>Loading metrics...</div>
          )}
        </div>

        <div className="charts-grid">
          <div className="glass-panel">
            <div
              className="panel-header"
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <div className="panel-title">
                <BarChart2 size={20} /> Publication Trend (24h)
              </div>
              <button
                onClick={() => exportToCSV(chartData, "publication_trend.csv")}
                className="print-hide"
                style={{
                  background: "rgba(16, 185, 129, 0.2)",
                  border: "1px solid rgba(16, 185, 129, 0.4)",
                  padding: "4px 8px",
                  borderRadius: "6px",
                  color: "#10b981",
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: "4px",
                  fontSize: "0.8rem",
                }}
              >
                <FileText size={14} /> CSV
              </button>
            </div>
            <div style={{ height: 300, width: "100%" }}>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient
                        id="colorCount"
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop
                          offset="5%"
                          stopColor="#3b82f6"
                          stopOpacity={0.8}
                        />
                        <stop
                          offset="95%"
                          stopColor="#3b82f6"
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.1)"
                    />
                    <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "rgba(30, 41, 59, 0.9)",
                        border: "1px solid rgba(255,255,255,0.1)",
                      }}
                      itemStyle={{ color: "#fff" }}
                    />
                    <Area
                      type="monotone"
                      dataKey="count"
                      stroke="#3b82f6"
                      fillOpacity={1}
                      fill="url(#colorCount)"
                    />
                  </AreaChart>
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
                  No trend data available
                </div>
              )}
            </div>
          </div>

          <div className="glass-panel">
            <div className="panel-header">
              <div className="panel-title">
                <Activity size={20} /> Category Distribution
              </div>
            </div>
            <div style={{ height: 300, width: "100%" }}>
              {sourceData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sourceData}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.1)"
                    />
                    <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip
                      cursor={{ fill: "rgba(255,255,255,0.05)" }}
                      contentStyle={{
                        backgroundColor: "rgba(30, 41, 59, 0.9)",
                        border: "1px solid rgba(255,255,255,0.1)",
                      }}
                    />
                    <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                  </BarChart>
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
                  No source data available
                </div>
              )}
            </div>
          </div>
        </div>
      </>
    </>
  );
}

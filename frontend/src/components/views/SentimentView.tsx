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
import { ThumbsUp , BarChart2 , Activity } from "lucide-react";

export default function SentimentView({
  sentimentDist,
  sentimentTimeline,
  sentimentSources,
}: any) {
  return (
    <>
      <div className="charts-grid">
        <div className="glass-panel">
          <div className="panel-header">
            <div className="panel-title">
              <ThumbsUp size={20} /> Overall Sentiment
            </div>
          </div>
          <div style={{ height: 300, width: "100%" }}>
            {sentimentDist.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={sentimentDist}
                    dataKey="count"
                    nameKey="sentiment_label"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    label
                  >
                    {sentimentDist.map((entry: any, index: number) => (
                      <Cell
                        key={`cell-${index}`}
                        fill={
                          entry.sentiment_label === "Positive"
                            ? "var(--accent-green)"
                            : entry.sentiment_label === "Negative"
                              ? "#ef4444"
                              : "#94a3b8"
                        }
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "rgba(30, 41, 59, 0.9)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                    itemStyle={{ color: "#fff" }}
                  />
                  <Legend />
                </PieChart>
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
                No sentiment data available
              </div>
            )}
          </div>
        </div>

        <div className="glass-panel">
          <div className="panel-header">
            <div className="panel-title">
              <BarChart2 size={20} /> Sentiment by Source
            </div>
          </div>
          <div style={{ height: 300, width: "100%" }}>
            {sentimentSources.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={sentimentSources}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.1)"
                  />
                  <XAxis dataKey="source" stroke="#94a3b8" fontSize={12} />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip
                    cursor={{ fill: "rgba(255,255,255,0.05)" }}
                    contentStyle={{
                      backgroundColor: "rgba(30, 41, 59, 0.9)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  />
                  <Legend />
                  <Bar
                    dataKey="Positive"
                    stackId="a"
                    fill="var(--accent-green)"
                  />
                  <Bar dataKey="Neutral" stackId="a" fill="#94a3b8" />
                  <Bar dataKey="Negative" stackId="a" fill="#ef4444" />
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
                No source sentiment data available
              </div>
            )}
          </div>
        </div>

        <div className="glass-panel" style={{ gridColumn: "1 / -1" }}>
          <div className="panel-header">
            <div className="panel-title">
              <Activity size={20} /> Sentiment Timeline
            </div>
          </div>
          <div style={{ height: 300, width: "100%" }}>
            {sentimentTimeline.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={sentimentTimeline}>
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
                    dataKey="Positive"
                    stroke="var(--accent-green)"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="Negative"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="Neutral"
                    stroke="#94a3b8"
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
  );
}

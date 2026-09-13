"use client";

import React, { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { Users, Hash , MessageSquare , ThumbsUp } from "lucide-react";

export default function EntitiesView({
  entitiesData,
  trendingKeywords,
  entityTypeDist,
  entitySentiment,
}: any) {
  return (
    <>
      <div
        className="charts-grid"
        style={{ gridTemplateColumns: "repeat(3, 1fr)" }}
      >
        <div className="glass-panel">
          <div className="panel-header">
            <div className="panel-title">
              <Users size={20} /> Top Entities
            </div>
          </div>
          <div style={{ height: 400, width: "100%" }}>
            {entitiesData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={entitiesData}
                  layout="vertical"
                  margin={{ left: 20 }}
                >
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.1)"
                    horizontal={true}
                    vertical={false}
                  />
                  <XAxis type="number" stroke="#94a3b8" fontSize={12} />
                  <YAxis
                    type="category"
                    dataKey="entity_name"
                    stroke="#94a3b8"
                    fontSize={11}
                    width={150}
                  />
                  <Tooltip
                    cursor={{ fill: "rgba(255,255,255,0.05)" }}
                    contentStyle={{
                      backgroundColor: "rgba(30, 41, 59, 0.9)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  />
                  <Bar
                    dataKey="mention_count"
                    fill="#3b82f6"
                    radius={[0, 4, 4, 0]}
                  />
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
                No entity data available
              </div>
            )}
          </div>
        </div>

        <div className="glass-panel">
          <div className="panel-header">
            <div className="panel-title">
              <MessageSquare size={20} /> Word Cloud
            </div>
          </div>
          <div
            style={{
              height: 400,
              width: "100%",
              display: "flex",
              flexWrap: "wrap",
              alignContent: "center",
              justifyContent: "center",
              gap: "10px",
              padding: "1rem",
              overflow: "hidden",
            }}
          >
            {trendingKeywords.length > 0 ? (
              (() => {
                const maxCount =
                  Math.max(...trendingKeywords.map((k: any) => k.count)) || 1;
                const minCount =
                  Math.min(...trendingKeywords.map((k: any) => k.count)) || 0;
                const colors = [
                  "#60a5fa",
                  "#34d399",
                  "#a78bfa",
                  "#f472b6",
                  "#fcd34d",
                  "#38bdf8",
                  "#818cf8",
                ];

                return trendingKeywords.map((k: any, i: number) => {
                  const size =
                    12 +
                    ((k.count - minCount) / (maxCount - minCount || 1)) * 32; // 12px to 44px
                  return (
                    <span
                      key={i}
                      style={{
                        fontSize: `${size}px`,
                        color: colors[i % colors.length],
                        fontWeight: size > 24 ? 700 : size > 18 ? 600 : 400,
                        lineHeight: 1,
                        opacity: 0.8 + Math.random() * 0.2,
                        transition: "transform 0.2s",
                        cursor: "default",
                      }}
                      onMouseEnter={(e) =>
                        (e.currentTarget.style.transform = "scale(1.1)")
                      }
                      onMouseLeave={(e) =>
                        (e.currentTarget.style.transform = "scale(1)")
                      }
                      title={`Xuất hiện ${k.count} lần`}
                    >
                      {k.keyword}
                    </span>
                  );
                });
              })()
            ) : (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: "100%",
                  color: "var(--text-muted)",
                }}
              >
                No keyword data available
              </div>
            )}
          </div>
        </div>

        <div className="glass-panel">
          <div className="panel-header">
            <div className="panel-title">
              <MessageSquare size={20} /> Entity Types
            </div>
          </div>
          <div style={{ height: 400, width: "100%" }}>
            {entityTypeDist.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={entityTypeDist}
                    dataKey="count"
                    nameKey="entity_type"
                    cx="50%"
                    cy="50%"
                    outerRadius={120}
                    label
                  >
                    {entityTypeDist.map((entry: any, index: number) => {
                      const colors = [
                        "#8b5cf6",
                        "#3b82f6",
                        "#10b981",
                        "#f59e0b",
                        "#ef4444",
                      ];
                      return (
                        <Cell
                          key={`cell-${index}`}
                          fill={colors[index % colors.length]}
                        />
                      );
                    })}
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
                No type data available
              </div>
            )}
          </div>
        </div>

        <div className="glass-panel" style={{ gridColumn: "1 / -1" }}>
          <div className="panel-header">
            <div className="panel-title">
              <ThumbsUp size={20} /> Sentiment by Entity
            </div>
          </div>
          <div style={{ height: 400, width: "100%" }}>
            {entitySentiment.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={entitySentiment} margin={{ bottom: 40 }}>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(255,255,255,0.1)"
                  />
                  <XAxis
                    dataKey="entity"
                    stroke="#94a3b8"
                    fontSize={12}
                    angle={-45}
                    textAnchor="end"
                  />
                  <YAxis stroke="#94a3b8" fontSize={12} />
                  <Tooltip
                    cursor={{ fill: "rgba(255,255,255,0.05)" }}
                    contentStyle={{
                      backgroundColor: "rgba(30, 41, 59, 0.9)",
                      border: "1px solid rgba(255,255,255,0.1)",
                    }}
                  />
                  <Legend verticalAlign="top" />
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
                No entity sentiment data available
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

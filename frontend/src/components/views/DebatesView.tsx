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
} from "recharts";
import { MessageSquare, ThumbsUp } from "lucide-react";

export default function DebatesView({ overviewData, feed }: any) {
  return (
    <>
      <div className="glass-panel" style={{ marginTop: "20px" }}>
        <div className="panel-header">
          <div className="panel-title">
            <MessageSquare size={20} /> Top Debates
          </div>
        </div>
        <div className="stream-container">
          {overviewData?.top_debates?.map((post: any) => (
            <div
              key={post.post_id}
              className="feed-item"
              style={{
                borderLeft: `4px solid ${post.sentiment_score > 0.1 ? "var(--accent-green)" : post.sentiment_score < -0.1 ? "#ef4444" : "#94a3b8"}`,
              }}
            >
              <div className="feed-header">
                <span
                  className="feed-type"
                  style={{
                    background: "rgba(139, 92, 246, 0.2)",
                    color: "#a78bfa",
                  }}
                >
                  {post.source}
                </span>
                <span className="feed-time">
                  {new Date(post.publish_time).toLocaleString()}
                </span>
              </div>
              <div className="feed-message">
                <strong>{post.title}</strong>
                <p
                  style={{
                    margin: "8px 0",
                    fontSize: "0.9rem",
                    color: "#cbd5e1",
                  }}
                >
                  {post.content.substring(0, 150)}...
                </p>
              </div>
              <div
                style={{
                  display: "flex",
                  gap: "15px",
                  marginTop: "10px",
                  fontSize: "0.85rem",
                  color: "#94a3b8",
                }}
              >
                <span
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <ThumbsUp size={14} /> {post.like_count}
                </span>
                <span
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                  }}
                >
                  <MessageSquare size={14} /> {post.reply_count} replies
                </span>
              </div>
            </div>
          ))}
          {!overviewData?.top_debates?.length && (
            <div
              style={{
                padding: "20px",
                textAlign: "center",
                color: "var(--text-muted)",
              }}
            >
              No debate data available
            </div>
          )}
        </div>
      </div>
    </>
  );
}

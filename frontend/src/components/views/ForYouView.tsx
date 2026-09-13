"use client";

import React, { useState } from "react";
import { BookOpen, Clock, ThumbsUp } from "lucide-react";

export default function ForYouView({
  articles,
  forYouArticles,
  trackClick,
  timeAgo,
}: any) {
  return (
    <>
      <div className="glass-panel" style={{ minHeight: "600px" }}>
        <div
          className="panel-header"
          style={{
            borderBottom: "1px solid rgba(255,255,255,0.1)",
            paddingBottom: "1rem",
            marginBottom: "1rem",
          }}
        >
          <div
            className="panel-title"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              fontSize: "1.5rem",
            }}
          >
            ✨ Recommended For You
          </div>
          <div style={{ color: "#94a3b8", fontSize: "0.9rem" }}>
            Tailored news based on your reading history
          </div>
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "15px",
          }}
        >
          {forYouArticles.map((a: any, i: number) => (
            <a
              key={i}
              href={a.url}
              target="_blank"
              rel="noreferrer"
              onClick={() => trackClick(a.url_hash)}
              style={{
                display: "block",
                padding: "15px",
                background: "rgba(255,255,255,0.03)",
                borderRadius: "12px",
                textDecoration: "none",
                color: "inherit",
                border: "1px solid rgba(255,255,255,0.05)",
                transition: "transform 0.2s, background 0.2s",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.background = "rgba(255,255,255,0.06)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = "none";
                e.currentTarget.style.background = "rgba(255,255,255,0.03)";
              }}
            >
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  marginBottom: "8px",
                }}
              >
                <span className={`tag ${a.source?.toLowerCase()}`}>
                  {a.source}
                </span>
                <span style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                  {a.publish_time ? timeAgo(a.publish_time) : "-"}
                </span>
              </div>
              <h3
                style={{
                  margin: "0 0 10px 0",
                  fontSize: "1.2rem",
                  color: "#fff",
                  lineHeight: 1.4,
                }}
              >
                {a.title}
              </h3>
              {a.content && (
                <p
                  style={{
                    margin: 0,
                    color: "#94a3b8",
                    fontSize: "0.95rem",
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}
                >
                  {a.content}
                </p>
              )}
            </a>
          ))}
          {forYouArticles.length === 0 && (
            <div
              style={{
                textAlign: "center",
                padding: "3rem",
                color: "var(--text-muted)",
              }}
            >
              No recommendations found yet. Read some articles to build your
              profile!
            </div>
          )}
        </div>
      </div>
    </>
  );
}

"use client";

import React, { useState } from "react";
import { Radio } from "lucide-react";

export default function StreamView({ feed, isConnected }: any) {
  return (
    <>
      <div
        className="glass-panel"
        style={{ maxWidth: "800px", margin: "0 auto" }}
      >
        <div className="panel-header">
          <div className="panel-title">
            <Radio size={20} /> Live Data Feed
          </div>
          <div className="status-indicator">
            <div
              className="pulse-dot"
              style={{
                backgroundColor: isConnected
                  ? "var(--accent-green)"
                  : "#ef4444",
              }}
            ></div>
            <span
              style={{
                color: isConnected ? "var(--accent-green)" : "#ef4444",
              }}
            >
              {isConnected ? "Connected to Stream" : "Reconnecting..."}
            </span>
          </div>
        </div>
        <div className="feed-list">
          {feed.length === 0 ? (
            <div
              style={{
                color: "var(--text-muted)",
                textAlign: "center",
                padding: "4rem 0",
              }}
            >
              Waiting for incoming events from the pipeline...
            </div>
          ) : (
            feed.map((event: any, index: number) => (
              <div key={index} className="feed-item">
                <div className="feed-time">
                  {new Date(event.timestamp).toLocaleTimeString()} -{" "}
                  {event.type.toUpperCase()}
                </div>
                <div className="feed-title">{event.message}</div>
                {event.data && (
                  <div
                    style={{
                      fontSize: "0.85rem",
                      color: "var(--text-muted)",
                      marginTop: "0.5rem",
                      background: "rgba(0,0,0,0.2)",
                      padding: "0.5rem",
                      borderRadius: "4px",
                    }}
                  >
                    <pre style={{ margin: 0 }}>
                      {JSON.stringify(event.data, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}

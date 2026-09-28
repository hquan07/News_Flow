"use client";

import React, { useState } from "react";
import { Check, Copy, Pause, Play, Radio } from "lucide-react";

type FeedEvent = {
  timestamp: string;
  type: string;
  message: string;
  data?: unknown;
};

interface StreamViewProps {
  feed: FeedEvent[];
  isConnected: boolean;
  isPaused: boolean;
  bufferedCount: number;
  onPause: () => void;
  onResume: () => void;
}

export default function StreamView({
  feed,
  isConnected,
  isPaused,
  bufferedCount,
  onPause,
  onResume,
}: StreamViewProps) {
  const [copiedEvent, setCopiedEvent] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);

  const copyPayload = async (event: FeedEvent, eventKey: string) => {
    try {
      await navigator.clipboard.writeText(
        JSON.stringify(event.data ?? event, null, 2),
      );
      setCopyError(null);
      setCopiedEvent(eventKey);
      window.setTimeout(() => setCopiedEvent(null), 1800);
    } catch {
      setCopyError("Clipboard permission was denied.");
    }
  };

  return (
    <>
      <div
        className="glass-panel"
        style={{ maxWidth: "800px", margin: "0 auto" }}
      >
        <div className="panel-header stream-panel-header">
          <div className="panel-title">
            <Radio size={20} /> Live Data Feed
          </div>
          <div className="stream-header-actions">
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
                {isConnected ? "Connected" : "Reconnecting..."}
              </span>
            </div>
            <button
              type="button"
              className={`stream-control-button ${isPaused ? "paused" : ""}`}
              onClick={isPaused ? onResume : onPause}
              aria-pressed={isPaused}
            >
              {isPaused ? <Play size={15} /> : <Pause size={15} />}
              {isPaused ? "Resume feed" : "Pause feed"}
            </button>
          </div>
        </div>
        {isPaused && (
          <div className="stream-paused-banner" role="status">
            <Pause size={15} />
            <span>Display paused. The realtime connection remains active.</span>
            {bufferedCount > 0 && (
              <strong>
                {bufferedCount} new event{bufferedCount === 1 ? "" : "s"}
              </strong>
            )}
          </div>
        )}
        {copyError && (
          <div className="stream-copy-error" role="alert">
            {copyError}
          </div>
        )}
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
            feed.map((event, index) => {
              const eventKey = `${event.timestamp}-${index}`;
              return (
                <div key={eventKey} className="feed-item">
                  <div className="feed-item-header">
                    <div className="feed-time">
                      {new Date(event.timestamp).toLocaleTimeString()} -{" "}
                      {event.type.toUpperCase()}
                    </div>
                    <button
                      type="button"
                      className="copy-payload-button"
                      onClick={() => copyPayload(event, eventKey)}
                      aria-label={`Copy payload for ${event.type} event`}
                    >
                      {copiedEvent === eventKey ? (
                        <Check size={14} />
                      ) : (
                        <Copy size={14} />
                      )}
                      {copiedEvent === eventKey ? "Copied" : "Copy payload"}
                    </button>
                  </div>
                  <div className="feed-title">{event.message}</div>
                  {event.data !== undefined && event.data !== null && (
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
              );
            })
          )}
        </div>
      </div>
    </>
  );
}

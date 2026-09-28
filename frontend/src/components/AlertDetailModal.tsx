"use client";

import React from "react";
import {
  Zap,
  ExternalLink,
  ThumbsUp,
  MessageSquare,
  Clock,
  AlertTriangle,
  User,
  FileWarning,
} from "lucide-react";
import Modal from "./ui/Modal";
import type { ViralPostDetail, ViralPostAlertSummary } from "@/lib/alert-types";

interface AlertDetailModalProps {
  open: boolean;
  onClose: () => void;
  summary: ViralPostAlertSummary | null;
  detail: ViralPostDetail | null;
  loading: boolean;
  error: string | null;
}

function SentimentBadge({ label }: { label: string }) {
  const colors: Record<string, string> = {
    positive: "#22c55e",
    negative: "#ef4444",
    neutral: "#94a3b8",
  };
  const color = colors[label.toLowerCase()] || "#94a3b8";
  return (
    <span
      className="detail-sentiment-badge"
      style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}
    >
      {label}
    </span>
  );
}

function DataWarning({ message }: { message: string }) {
  return (
    <div className="detail-data-warning">
      <FileWarning size={14} />
      <span>{message}</span>
    </div>
  );
}

function MetricBox({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color?: string;
}) {
  return (
    <div className="detail-metric-box">
      <div className="detail-metric-icon" style={{ color: color || "#94a3b8" }}>
        {icon}
      </div>
      <div>
        <div className="detail-metric-label">{label}</div>
        <div className="detail-metric-value" style={{ color: color || "#e2e8f0" }}>
          {value}
        </div>
      </div>
    </div>
  );
}

export default function AlertDetailModal({
  open,
  onClose,
  summary,
  detail,
  loading,
  error,
}: AlertDetailModalProps) {
  const source = detail?.source || summary?.source || "";

  const headerTitle = (
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <Zap size={20} style={{ color: "#f59e0b" }} />
      <span style={{ textTransform: "capitalize" }}>{source}</span>
      <span
        className="alert-badge"
        style={{ background: "#f59e0b", fontSize: "11px", padding: "2px 8px" }}
      >
        Viral
      </span>
    </div>
  );

  const footerContent = (
    <div className="detail-footer-actions">
      {detail?.data_quality.url_available && detail.url ? (
        <a
          href={detail.url}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-primary detail-open-link"
        >
          <ExternalLink size={16} /> Open original post
        </a>
      ) : (
        <button className="btn btn-secondary" disabled title="Original URL not available">
          <ExternalLink size={16} /> URL not available
        </button>
      )}
      <button className="btn btn-secondary" onClick={onClose}>
        Close
      </button>
    </div>
  );

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={headerTitle}
      footer={footerContent}
      ariaLabelledBy="alert-detail-title"
      className="alert-detail-modal"
    >
      {loading && (
        <div className="detail-skeleton">
          <div className="skeleton-line w-80" />
          <div className="skeleton-line w-60" />
          <div className="skeleton-grid">
            <div className="skeleton-box" />
            <div className="skeleton-box" />
            <div className="skeleton-box" />
          </div>
          <div className="skeleton-line w-full" />
          <div className="skeleton-line w-full" />
          <div className="skeleton-line w-40" />
        </div>
      )}

      {error && (
        <div className="detail-error">
          <AlertTriangle size={24} />
          <p>{error}</p>
        </div>
      )}

      {!loading && !error && detail && (
        <div className="detail-content">
          {/* Title */}
          {detail.data_quality.title_available ? (
            <h3 className="detail-title">{detail.title}</h3>
          ) : (
            <DataWarning message="Title unavailable — this post uses placeholder data" />
          )}

          {/* Metadata row */}
          <div className="detail-meta-row">
            {detail.author && (
              <span className="detail-meta-item">
                <User size={14} /> {detail.author}
              </span>
            )}
            {detail.publish_time && (
              <span className="detail-meta-item">
                <Clock size={14} />{" "}
                {new Date(detail.publish_time).toLocaleString("vi-VN", {
                  day: "2-digit",
                  month: "2-digit",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}
            {detail.sentiment_label && (
              <SentimentBadge label={detail.sentiment_label} />
            )}
          </div>

          {/* Metrics grid */}
          <div className="detail-metrics-grid">
            <MetricBox
              icon={<Zap size={18} />}
              label="Interactions"
              value={detail.interactions.toLocaleString()}
              color="#f59e0b"
            />
            <MetricBox
              icon={<ThumbsUp size={18} />}
              label="Likes"
              value={detail.like_count.toLocaleString()}
              color="#3b82f6"
            />
            <MetricBox
              icon={<MessageSquare size={18} />}
              label="Replies"
              value={detail.reply_count.toLocaleString()}
              color="#ec4899"
            />
          </div>

          {/* Content / Excerpt */}
          {detail.data_quality.content_available ? (
            <div className="detail-excerpt">
              <h4>Content</h4>
              <p>{detail.excerpt || detail.content}</p>
            </div>
          ) : (
            <DataWarning message="Content unavailable — original text not captured by crawler" />
          )}

          {/* Sentiment score */}
          {detail.sentiment_score !== 0 && (
            <div className="detail-sentiment-score">
              <span className="detail-meta-label">Sentiment Score</span>
              <div className="sentiment-bar-container">
                <div
                  className="sentiment-bar-fill"
                  style={{
                    width: `${Math.min(Math.max((detail.sentiment_score + 1) * 50, 0), 100)}%`,
                    background:
                      detail.sentiment_score > 0.2
                        ? "#22c55e"
                        : detail.sentiment_score < -0.2
                        ? "#ef4444"
                        : "#94a3b8",
                  }}
                />
              </div>
              <span className="sentiment-score-value">
                {detail.sentiment_score.toFixed(2)}
              </span>
            </div>
          )}

          {/* Data quality banner */}
          {(!detail.data_quality.title_available ||
            !detail.data_quality.content_available ||
            !detail.data_quality.url_available) && (
            <div className="detail-quality-notice">
              <AlertTriangle size={16} />
              <span>
                Some fields contain placeholder data. Data quality will improve as
                real crawl data flows in.
              </span>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

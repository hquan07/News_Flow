"use client";

import React from "react";
import {
  AlertTriangle,
  BarChart3,
  BookOpen,
  Clock,
  ExternalLink,
  ShieldAlert,
  TrendingUp,
  Zap,
} from "lucide-react";
import Modal from "./ui/Modal";
import InteractionTrendPanel from "./InteractionTrendPanel";
import type {
  ArticleAlertFilter,
  SocialCrisisAlert,
  SocialCrisisDetail,
  SpikeAlert,
  VolumeSpikeDetail,
  ViralPostAlertSummary,
} from "@/lib/alert-types";

interface SharedDetailProps {
  open: boolean;
  onClose: () => void;
  loading: boolean;
  error: string | null;
}

function DetailState({ loading, error }: Pick<SharedDetailProps, "loading" | "error">) {
  if (loading) {
    return (
      <div className="detail-skeleton" aria-label="Loading alert details">
        <div className="skeleton-line w-80" />
        <div className="skeleton-line w-60" />
        <div className="skeleton-grid">
          <div className="skeleton-box" />
          <div className="skeleton-box" />
          <div className="skeleton-box" />
        </div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="detail-error" role="alert">
        <AlertTriangle size={24} />
        <p>{error}</p>
      </div>
    );
  }
  return null;
}

function WhyAlert({ reason }: { reason: string }) {
  return (
    <section className="alert-explanation">
      <h4><AlertTriangle size={16} /> Why this alert?</h4>
      <p>{reason}</p>
    </section>
  );
}

interface CrisisModalProps extends SharedDetailProps {
  summary: SocialCrisisAlert | null;
  detail: SocialCrisisDetail | null;
}

export function CrisisDetailModal({
  open,
  onClose,
  loading,
  error,
  summary,
  detail,
}: CrisisModalProps) {
  const source = detail?.source || summary?.source || "Social source";
  return (
    <Modal
      open={open}
      onClose={onClose}
      ariaLabelledBy="crisis-detail-title"
      title={(
        <div className="alert-modal-heading">
          <ShieldAlert size={20} className="danger-text" />
          <span>{source}</span>
          <span className="alert-badge danger-badge">Crisis</span>
        </div>
      )}
      footer={<button className="btn btn-secondary" onClick={onClose}>Close</button>}
    >
      <DetailState loading={loading} error={error} />
      {!loading && !error && detail && (
        <div className="detail-content">
          <div className="detail-metrics-grid">
            <div className="detail-metric-box">
              <div className="detail-metric-icon"><BarChart3 size={18} /></div>
              <div><div className="detail-metric-label">Posts (1h)</div><div className="detail-metric-value">{detail.total_posts}</div></div>
            </div>
            <div className="detail-metric-box">
              <div className="detail-metric-icon danger-text"><TrendingUp size={18} /></div>
              <div><div className="detail-metric-label">Negative</div><div className="detail-metric-value danger-text">{detail.negative_pct}%</div></div>
            </div>
            <div className="detail-metric-box">
              <div className="detail-metric-icon"><ShieldAlert size={18} /></div>
              <div><div className="detail-metric-label">Negative posts</div><div className="detail-metric-value">{detail.negative_posts}</div></div>
            </div>
          </div>

          <WhyAlert reason={detail.alert_reason || `Negative sentiment exceeded ${detail.negative_pct_threshold}% with at least ${detail.min_posts_threshold} posts.`} />

          <section className="alert-detail-section">
            <h4>Sentiment distribution</h4>
            <div className="sentiment-breakdown">
              {detail.sentiment_distribution.map((bucket) => (
                <div key={bucket.label}>
                  <span>{bucket.label || "unknown"}</span>
                  <strong>{bucket.count}</strong>
                </div>
              ))}
            </div>
          </section>

          <section className="alert-detail-section">
            <h4>Top negative posts</h4>
            {detail.top_negative_posts.length === 0 ? (
              <p className="detail-empty-copy">No contributing post details are available.</p>
            ) : (
              <div className="alert-contributor-list">
                {detail.top_negative_posts.map((post) => (
                  <div key={post.post_id} className="alert-contributor-item">
                    <div>
                      <strong>{post.data_quality.title_available ? post.title : `Post on ${post.source}`}</strong>
                      {post.data_quality.synthetic && <span className="synthetic-data-badge">Synthetic data</span>}
                    </div>
                    <span>{post.interactions.toLocaleString()} interactions</span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </Modal>
  );
}

interface ViralClusterModalProps {
  open: boolean;
  onClose: () => void;
  source: string;
  posts: ViralPostAlertSummary[];
  onSelectPost: (post: ViralPostAlertSummary) => void;
}

export function ViralClusterModal({
  open,
  onClose,
  source,
  posts,
  onSelectPost,
}: ViralClusterModalProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      ariaLabelledBy="viral-cluster-title"
      title={(
        <div className="alert-modal-heading">
          <Zap size={20} style={{ color: "#f59e0b" }} />
          <span>{source} cluster</span>
          <span className="alert-badge" style={{ background: "#f59e0b" }}>
            {posts.length} posts
          </span>
        </div>
      )}
      footer={<button className="btn btn-secondary" onClick={onClose}>Close</button>}
    >
      <div className="detail-content">
        <p className="detail-empty-copy">
          Viral alerts from the same source are grouped to reduce duplicate triage work.
        </p>
        <div className="viral-cluster-posts">
          {posts.map((post) => (
            <button
              key={post.post_id}
              type="button"
              onClick={() => onSelectPost(post)}
            >
              <span>
                {post.data_quality.title_available && post.title
                  ? post.title
                  : `Trending post on ${post.source}`}
              </span>
              <strong>{post.interactions.toLocaleString()} interactions</strong>
            </button>
          ))}
        </div>
        <InteractionTrendPanel source={source} active={open} />
      </div>
    </Modal>
  );
}

interface VolumeModalProps extends SharedDetailProps {
  summary: SpikeAlert | null;
  detail: VolumeSpikeDetail | null;
  onOpenArticles: (filter: ArticleAlertFilter) => void;
}

export function VolumeSpikeDetailModal({
  open,
  onClose,
  loading,
  error,
  summary,
  detail,
  onOpenArticles,
}: VolumeModalProps) {
  const hourSlot = detail?.hour_slot || summary?.hour_slot;
  const endTime = detail?.window_end || "";

  const openFilteredArticles = () => {
    if (!detail || !hourSlot || !endTime) return;
    onOpenArticles({
      // Preserve the API timestamps verbatim so a timezone conversion cannot
      // shift the one-hour ClickHouse filter window.
      publishedFrom: hourSlot,
      publishedTo: endTime,
      label: `Volume spike · ${new Date(hourSlot).toLocaleString("vi-VN")}`,
    });
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      ariaLabelledBy="volume-detail-title"
      title={(
        <div className="alert-modal-heading">
          <TrendingUp size={20} className="purple-text" />
          <span>Volume spike</span>
          <span className="alert-badge purple-badge">Anomaly</span>
        </div>
      )}
      footer={(
        <div className="detail-footer-actions">
          <button className="btn btn-primary" onClick={openFilteredArticles} disabled={!detail}>
            <BookOpen size={16} /> View matching articles
          </button>
          <button className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      )}
    >
      <DetailState loading={loading} error={error} />
      {!loading && !error && detail && (
        <div className="detail-content">
          <div className="detail-meta-row">
            <span className="detail-meta-item"><Clock size={14} /> {new Date(detail.hour_slot).toLocaleString("vi-VN")}</span>
            <span className="detail-meta-item">One-hour detection window</span>
          </div>
          <div className="detail-metrics-grid">
            <div className="detail-metric-box"><div><div className="detail-metric-label">Published</div><div className="detail-metric-value">{detail.article_count}</div></div></div>
            <div className="detail-metric-box"><div><div className="detail-metric-label">7-day average</div><div className="detail-metric-value">{detail.avg_count.toFixed(1)}</div></div></div>
            <div className="detail-metric-box"><div><div className="detail-metric-label">Z-score</div><div className="detail-metric-value purple-text">{detail.z_score.toFixed(2)}σ</div></div></div>
          </div>

          <WhyAlert reason={detail.alert_reason} />

          <section className="alert-detail-section">
            <h4>Articles in this hour</h4>
            {detail.articles.length === 0 ? (
              <p className="detail-empty-copy">No article preview is available.</p>
            ) : (
              <div className="volume-article-list">
                {detail.articles.map((article) => (
                  <a key={article.article_id} href={article.url} target="_blank" rel="noreferrer">
                    <span>{article.title}</span>
                    <small>{article.source} · {article.category}</small>
                    <ExternalLink size={14} />
                  </a>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </Modal>
  );
}

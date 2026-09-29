"use client";

import { Heart, MessageCircle, Radio, WifiOff } from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";

export type LiveSocialPost = {
  post_id: string;
  source: string;
  author: string;
  title?: string;
  content?: string;
  like_count: number;
  reply_count: number;
  interactions: number;
  sentiment_label?: string;
  publish_time?: string;
  synthetic?: boolean;
};

function relativeTime(value?: string) {
  if (!value) return "just now";
  const elapsed = Date.now() - new Date(value).getTime();
  if (!Number.isFinite(elapsed) || elapsed < 60_000) return "just now";
  if (elapsed < 3_600_000) return `${Math.floor(elapsed / 60_000)}m ago`;
  if (elapsed < 86_400_000) return `${Math.floor(elapsed / 3_600_000)}h ago`;
  return `${Math.floor(elapsed / 86_400_000)}d ago`;
}

export default function LiveSocialFeedView({
  posts,
  connected,
}: {
  posts: LiveSocialPost[];
  connected: boolean;
}) {
  return (
    <section className="live-social-panel" aria-label="Live social feed">
      <header className="social-view-header">
        <div>
          <h2><Radio size={22} /> Live Social Feed</h2>
          <p>Recent social posts delivered through the realtime SSE stream.</p>
        </div>
        <span className={`stream-status ${connected ? "connected" : "disconnected"}`}>
          {connected ? <Radio size={14} /> : <WifiOff size={14} />}
          {connected ? "Live" : "Reconnecting"}
        </span>
      </header>

      {!posts.length ? (
        <EmptyState message={connected ? "Waiting for incoming social posts" : "Waiting for the realtime connection"} />
      ) : (
        <div className="social-feed-list" aria-live="polite">
          {posts.map((post) => {
            const sentiment = (post.sentiment_label || "neutral").toLowerCase();
            return (
              <article className={`social-feed-item sentiment-${sentiment}`} key={post.post_id}>
                <div className="feed-avatar">{(post.author || post.source).charAt(0).toUpperCase()}</div>
                <div className="feed-content">
                  <div className="feed-meta">
                    <strong>{post.author || `${post.source} channel`}</strong>
                    <span>@{post.source}</span>
                    <span>·</span>
                    <time>{relativeTime(post.publish_time)}</time>
                    {post.synthetic && <span className="synthetic-badge">Synthetic data</span>}
                  </div>
                  {post.title && <h3>{post.title}</h3>}
                  {post.content && <p>{post.content}</p>}
                  <div className="feed-engagement">
                    <span><Heart size={15} /> {Number(post.like_count || 0).toLocaleString()}</span>
                    <span><MessageCircle size={15} /> {Number(post.reply_count || 0).toLocaleString()}</span>
                    <span className={`sentiment-pill ${sentiment}`}>{sentiment}</span>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

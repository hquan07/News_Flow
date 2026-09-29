"use client";

import { Award, Heart, MessageCircle, Trophy, Users } from "lucide-react";
import EmptyState from "@/components/ui/EmptyState";
import ChartSkeleton from "@/components/ui/ChartSkeleton";

export type SocialInfluencer = {
  author: string;
  source: string;
  post_count: number;
  total_likes: number;
  total_replies: number;
  total_interactions: number;
  avg_sentiment: number;
};

const SOURCE_LABELS: Record<string, string> = {
  youtube: "YouTube",
  youtube_comments: "YouTube",
  reddit: "Reddit",
  reddit_vn: "Reddit VN",
  facebook: "Facebook",
  voz: "Voz",
  voz_forum: "Voz Forum",
};

function compact(value: number) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

function rankIcon(rank: number) {
  if (rank === 1) return <Trophy size={20} />;
  if (rank <= 3) return <Award size={20} />;
  return <span>{rank}</span>;
}

export default function SocialInfluencersView({
  influencers,
}: {
  influencers: SocialInfluencer[] | null;
}) {
  if (influencers === null) {
    return <div className="social-view-loading"><ChartSkeleton /></div>;
  }

  if (!influencers.length) {
    return <EmptyState message="No influencer data available for this filter" />;
  }

  return (
    <section className="influencers-panel" aria-label="Top social influencers">
      <header className="social-view-header">
        <div>
          <h2><Users size={22} /> Top Influencers</h2>
          <p>Authors and channels ranked by total likes and replies.</p>
        </div>
        <span className="live-count">Top {influencers.length}</span>
      </header>

      <div className="influencer-list">
        {influencers.map((item, index) => {
          const rank = index + 1;
          const sourceClass = item.source.toLowerCase().replace(/_/g, "-");
          return (
            <article className={`influencer-row rank-${Math.min(rank, 4)}`} key={`${item.source}-${item.author}`}>
              <div className="influencer-rank">{rankIcon(rank)}</div>
              <div className={`platform-avatar platform-${sourceClass}`}>
                {item.author.trim().charAt(0).toUpperCase() || "?"}
              </div>
              <div className="influencer-identity">
                <strong>{item.author}</strong>
                <span className={`platform-badge platform-${sourceClass}`}>
                  {SOURCE_LABELS[item.source] ?? item.source}
                </span>
              </div>
              <div className="influencer-stat">
                <span>Posts</span>
                <strong>{compact(item.post_count)}</strong>
              </div>
              <div className="influencer-stat">
                <span><Heart size={13} /> Likes</span>
                <strong>{compact(item.total_likes)}</strong>
              </div>
              <div className="influencer-stat">
                <span><MessageCircle size={13} /> Replies</span>
                <strong>{compact(item.total_replies)}</strong>
              </div>
              <div className="influencer-engagement">
                <span>Interactions</span>
                <strong>{compact(item.total_interactions)}</strong>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

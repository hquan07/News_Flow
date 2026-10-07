"use client";

import { useState } from "react";
import { BarChart3, Heart, MessageCircle, TrendingUp } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ChartCard from "@/components/ui/ChartCard";
import ChartSkeleton from "@/components/ui/ChartSkeleton";
import EmptyState from "@/components/ui/EmptyState";
import MetricCard from "@/components/ui/MetricCard";
import MetricDetailList from "@/components/ui/MetricDetailList";
import { formatCompactNumber, formatDateTime, formatPercent, formatSourceName } from "@/lib/formatters";
import { deduplicateSocialPosts } from "@/lib/social-posts";
import type { SocialContentPerformanceData } from "@/lib/social-types";

export default function SocialContentPerformanceView({
  data,
  updatedAt,
}: {
  data: SocialContentPerformanceData | null;
  updatedAt: string | null;
}) {
  const [activeMetric, setActiveMetric] = useState<string | null>(null);
  if (!data) return <div className="social-view-loading"><ChartSkeleton /></div>;

  const { summary } = data;
  const interactiveMetric = (metric: string) => ({
    expanded: activeMetric === metric,
    onToggle: () => setActiveMetric((current) => current === metric ? null : metric),
  });
  const topPlatforms = data.platform_performance.slice(0, 5);
  const topPosts = deduplicateSocialPosts(data.top_posts);
  const topInteractionCount = Math.max(0, ...topPosts.map((post) => post.interactions));

  return (
    <div className="social-analytics-view">
      <div className="overview-grid social-summary-grid">
        <MetricCard {...interactiveMetric("posts")} label="Total posts" value={formatCompactNumber(summary.total_posts)} hint="Content in the selected scope" details={<MetricDetailList rows={topPlatforms.map((platform) => ({ label: formatSourceName(platform.source), value: `${formatCompactNumber(platform.post_count)} posts` }))} emptyMessage="No platform post data available" />} />
        <MetricCard {...interactiveMetric("interactions")} label="Total interactions" value={formatCompactNumber(summary.total_interactions)} hint="Likes and replies combined" details={<MetricDetailList rows={topPlatforms.map((platform) => ({ label: formatSourceName(platform.source), value: formatCompactNumber(platform.total_interactions) }))} emptyMessage="No platform interaction data available" />} />
        <MetricCard {...interactiveMetric("average")} label="Avg. per post" value={formatCompactNumber(summary.avg_interactions_per_post)} hint="Observed interactions per post" details={<MetricDetailList rows={topPlatforms.map((platform) => ({ label: formatSourceName(platform.source), value: formatCompactNumber(platform.avg_interactions_per_post) }))} emptyMessage="No platform averages available" />} />
        <MetricCard {...interactiveMetric("high-performers")} label="High performers" value={formatCompactNumber(summary.high_performing_posts)} hint="Posts with at least 50 interactions" tone="success" details={<MetricDetailList rows={[
          { label: "Performance threshold", value: "≥ 50 interactions" },
          { label: "Share of all posts", value: formatPercent(summary.total_posts ? (summary.high_performing_posts / summary.total_posts) * 100 : 0) },
          { label: "Top observed post", value: `${formatCompactNumber(topInteractionCount)} interactions` },
          { label: "Time range", value: data.time_range },
        ]} />} />
      </div>

      <div className="charts-grid">
        <ChartCard
          wide
          title={<><BarChart3 size={20} /> Platform Performance</>}
          description="Which platforms generate the most likes and replies?"
          timeRange="All available data"
          unit="Interactions"
          total={summary.total_posts}
          updatedAt={updatedAt}
        >
          {data.platform_performance.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.platform_performance} margin={{ left: 8, right: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.1)" />
                <XAxis dataKey="source" tickFormatter={formatSourceName} stroke="#94a3b8" fontSize={12} />
                <YAxis tickFormatter={formatCompactNumber} stroke="#94a3b8" fontSize={12} />
                <Tooltip cursor={{ fill: "rgba(148,163,184,.08)" }} />
                <Legend />
                <Bar dataKey="total_likes" name="Likes" stackId="interactions" fill="#3b82f6" radius={[0, 0, 3, 3]} />
                <Bar dataKey="total_replies" name="Replies" stackId="interactions" fill="#ec4899" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState message="No platform performance data available" />}
        </ChartCard>
      </div>

      <section className="social-analytics-panel" aria-label="Top performing social content">
        <header className="social-view-header">
          <div>
            <h2><TrendingUp size={21} /> Top Content</h2>
            <p>Posts ranked by likes and replies, without estimating unavailable reach.</p>
          </div>
          <span className="live-count">Top {topPosts.length}</span>
        </header>
        {topPosts.length ? (
          <div className="social-ranked-list">
            {topPosts.map((post, index) => (
              <article className="social-ranked-row" key={`${post.source}-${post.post_id}`}>
                <span className="social-rank-number">{index + 1}</span>
                <div className="social-ranked-main">
                  <div className="social-row-meta">
                    <span className="platform-badge">{formatSourceName(post.source)}</span>
                    <span>{post.author || "Unknown author"}</span>
                    <span>{formatDateTime(post.publish_time)}</span>
                  </div>
                  <strong>{post.title?.trim() || post.content?.trim().slice(0, 120) || "Untitled post"}</strong>
                </div>
                <div className="social-row-stat"><Heart size={14} /><span>{formatCompactNumber(post.like_count)}</span></div>
                <div className="social-row-stat"><MessageCircle size={14} /><span>{formatCompactNumber(post.reply_count)}</span></div>
                <div className="social-row-total">{formatCompactNumber(post.interactions)}</div>
              </article>
            ))}
          </div>
        ) : <EmptyState message="No top content available for this filter" />}
      </section>
    </div>
  );
}

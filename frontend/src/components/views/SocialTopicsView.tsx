"use client";

import { useState } from "react";
import { Hash, MessageSquareText } from "lucide-react";
import ChartSkeleton from "@/components/ui/ChartSkeleton";
import EmptyState from "@/components/ui/EmptyState";
import MetricCard from "@/components/ui/MetricCard";
import MetricDetailList from "@/components/ui/MetricDetailList";
import { formatCompactNumber, formatSourceName } from "@/lib/formatters";
import type { SocialTopicsData } from "@/lib/social-types";

function sentimentClass(score: number) {
  if (score > 0.1) return "positive";
  if (score < -0.1) return "negative";
  return "neutral";
}

export default function SocialTopicsView({ data }: { data: SocialTopicsData | null }) {
  const [activeMetric, setActiveMetric] = useState<string | null>(null);
  if (!data) return <div className="social-view-loading"><ChartSkeleton /></div>;

  const { summary } = data;
  const interactiveMetric = (metric: string) => ({
    expanded: activeMetric === metric,
    onToggle: () => setActiveMetric((current) => current === metric ? null : metric),
  });
  const topHashtags = data.hashtags.slice(0, 5);
  const topTopics = data.top_topics.slice(0, 5);

  return (
    <div className="social-analytics-view">
      <div className="overview-grid social-summary-grid">
        <MetricCard {...interactiveMetric("hashtags")} label="Top hashtags" value={summary.unique_hashtags.toLocaleString()} hint="Distinct tags in the ranked set" details={<MetricDetailList rows={topHashtags.map((hashtag) => ({ label: hashtag.hashtag, value: `${formatCompactNumber(hashtag.mentions)} mentions` }))} emptyMessage="No hashtag details available" />} />
        <MetricCard {...interactiveMetric("mentions")} label="Hashtag mentions" value={formatCompactNumber(summary.hashtag_mentions)} hint="Mentions across top hashtags" details={<MetricDetailList rows={topHashtags.map((hashtag) => ({ label: hashtag.hashtag, value: formatCompactNumber(hashtag.mentions) }))} emptyMessage="No hashtag mention data available" />} />
        <MetricCard {...interactiveMetric("topics")} label="Tracked topics" value={summary.tracked_topics.toLocaleString()} hint="Ranked conversation clusters" details={<MetricDetailList rows={topTopics.map((topic) => ({ label: topic.topic, value: `${formatCompactNumber(topic.post_count)} posts` }))} emptyMessage="No tracked topic data available" />} />
        <MetricCard {...interactiveMetric("topic-interactions")} label="Topic interactions" value={formatCompactNumber(summary.topic_interactions)} hint="Interactions across ranked topics" tone="success" details={<MetricDetailList rows={topTopics.map((topic) => ({ label: topic.topic, value: formatCompactNumber(topic.interactions) }))} emptyMessage="No topic interaction data available" />} />
      </div>

      <section className="social-analytics-panel">
        <header className="social-view-header">
          <div>
            <h2><Hash size={21} /> Trending Hashtags</h2>
            <p>Hashtags ranked by mentions, with engagement as a secondary signal.</p>
          </div>
          <span className="live-count">Top {data.hashtags.length}</span>
        </header>
        {data.hashtags.length ? (
          <div className="hashtag-cloud">
            {data.hashtags.map((item, index) => (
              <article className={`hashtag-card hashtag-rank-${Math.min(index + 1, 4)}`} key={item.hashtag}>
                <strong>{item.hashtag}</strong>
                <span>{formatCompactNumber(item.mentions)} mentions</span>
                <span>{formatCompactNumber(item.interactions)} interactions</span>
              </article>
            ))}
          </div>
        ) : <EmptyState message="No hashtags found in the selected content" />}
      </section>

      <section className="social-analytics-panel">
        <header className="social-view-header">
          <div>
            <h2><MessageSquareText size={21} /> Top Conversations</h2>
            <p>Recurring titles and discussions ranked by observed interactions.</p>
          </div>
        </header>
        {data.top_topics.length ? (
          <div className="social-ranked-list">
            {data.top_topics.map((topic, index) => (
              <article className="social-ranked-row social-topic-row" key={`${topic.source}-${topic.topic}`}>
                <span className="social-rank-number">{index + 1}</span>
                <div className="social-ranked-main">
                  <div className="social-row-meta"><span className="platform-badge">{formatSourceName(topic.source)}</span></div>
                  <strong>{topic.topic}</strong>
                </div>
                <span className={`sentiment-pill ${sentimentClass(topic.sentiment_score)}`}>{sentimentClass(topic.sentiment_score)}</span>
                <div className="social-topic-count"><strong>{formatCompactNumber(topic.post_count)}</strong><span>posts</span></div>
                <div className="social-row-total">{formatCompactNumber(topic.interactions)}</div>
              </article>
            ))}
          </div>
        ) : <EmptyState message="No conversation topics available" />}
      </section>
    </div>
  );
}

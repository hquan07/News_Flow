"use client";

import { useState } from "react";
import { AlertTriangle, Flame, ShieldCheck } from "lucide-react";
import ChartSkeleton from "@/components/ui/ChartSkeleton";
import EmptyState from "@/components/ui/EmptyState";
import MetricCard from "@/components/ui/MetricCard";
import MetricDetailList from "@/components/ui/MetricDetailList";
import { formatCompactNumber, formatDateTime, formatPercent, formatSourceName, truncateLabel } from "@/lib/formatters";
import { deduplicateSocialPosts } from "@/lib/social-posts";
import type { SocialAlertSignalsData } from "@/lib/social-types";

export default function SocialAlertsView({ data }: { data: SocialAlertSignalsData | null }) {
  const [activeMetric, setActiveMetric] = useState<string | null>(null);
  if (!data) return <div className="social-view-loading"><ChartSkeleton /></div>;

  const { summary, thresholds } = data;
  const interactiveMetric = (metric: string) => ({
    expanded: activeMetric === metric,
    onToggle: () => setActiveMetric((current) => current === metric ? null : metric),
  });
  const activeRisks = data.source_risks.filter((risk) => risk.active);
  const topRisks = [...data.source_risks].sort((left, right) => right.negative_pct - left.negative_pct).slice(0, 5);
  const viralPosts = deduplicateSocialPosts(data.viral_posts);
  const topViralPosts = viralPosts.slice(0, 5);

  return (
    <div className="social-analytics-view">
      <div className="overview-grid social-summary-grid">
        <MetricCard {...interactiveMetric("signals")} label="Active signals" value={summary.active_alerts.toLocaleString()} hint={data.window} tone={summary.active_alerts ? "danger" : "success"} details={<MetricDetailList rows={[
          { label: "Sentiment risks", value: summary.crisis_sources.toLocaleString() },
          { label: "Viral posts", value: summary.viral_posts.toLocaleString() },
          { label: "Monitoring window", value: data.window },
          { label: "Last evaluated", value: formatDateTime(data.generated_at) },
        ]} />} />
        <MetricCard {...interactiveMetric("sentiment-risks")} label="Sentiment risks" value={summary.crisis_sources.toLocaleString()} hint={`≥ ${formatPercent(thresholds.negative_pct)} negative sentiment`} tone={summary.crisis_sources ? "danger" : "success"} details={<MetricDetailList rows={(activeRisks.length ? activeRisks : topRisks).map((risk) => ({ label: formatSourceName(risk.source), value: `${formatPercent(risk.negative_pct)} negative` }))} emptyMessage="No platform sentiment data available" />} />
        <MetricCard {...interactiveMetric("viral-posts")} label="Viral posts" value={summary.viral_posts.toLocaleString()} hint={`≥ ${formatCompactNumber(thresholds.interactions)} interactions`} tone={summary.viral_posts ? "warning" : "success"} details={<MetricDetailList rows={topViralPosts.map((post) => ({ label: `${formatSourceName(post.source)} · ${truncateLabel(post.title?.trim() || post.content?.trim() || "Untitled", 24)}`, value: formatCompactNumber(post.interactions) }))} emptyMessage="No viral posts in the current window" />} />
        <MetricCard {...interactiveMetric("negative-posts")} label="Negative posts" value={formatCompactNumber(summary.negative_posts)} hint="Observed during the alert window" details={<MetricDetailList rows={topRisks.map((risk) => ({ label: formatSourceName(risk.source), value: `${formatCompactNumber(risk.negative_posts)} of ${formatCompactNumber(risk.total_posts)}` }))} emptyMessage="No negative post breakdown available" />} />
      </div>

      <section className="social-analytics-panel">
        <header className="social-view-header">
          <div>
            <h2><AlertTriangle size={21} /> Sentiment Risk Monitor</h2>
            <p>Flags a platform after at least {thresholds.min_posts} posts and {formatPercent(thresholds.negative_pct)} negative sentiment.</p>
          </div>
          <span className={summary.crisis_sources ? "alert-status active" : "alert-status clear"}>
            {summary.crisis_sources ? `${summary.crisis_sources} require attention` : "No active crisis signals"}
          </span>
        </header>
        {data.source_risks.length ? (
          <div className="risk-grid">
            {data.source_risks.map((risk) => (
              <article className={`risk-card ${risk.active ? "active" : "clear"}`} key={risk.source}>
                <div className="risk-card-heading">
                  <span className="platform-badge">{formatSourceName(risk.source)}</span>
                  {risk.active ? <AlertTriangle size={18} /> : <ShieldCheck size={18} />}
                </div>
                <strong>{formatPercent(risk.negative_pct)}</strong>
                <span>negative sentiment</span>
                <div className="risk-meter"><span style={{ width: `${Math.min(risk.negative_pct, 100)}%` }} /></div>
                <div><span>{formatCompactNumber(risk.negative_posts)} negative</span><span>{formatCompactNumber(risk.total_posts)} total posts</span></div>
              </article>
            ))}
          </div>
        ) : <EmptyState message="No recent social activity to evaluate" />}
      </section>

      <section className="social-analytics-panel">
        <header className="social-view-header">
          <div>
            <h2><Flame size={21} /> Viral Content Signals</h2>
            <p>Recent posts crossing the configured interaction threshold.</p>
          </div>
          <span className="live-count">Updated {formatDateTime(data.generated_at)}</span>
        </header>
        {viralPosts.length ? (
          <div className="social-ranked-list">
            {viralPosts.map((post) => (
              <article className="social-ranked-row" key={`${post.source}-${post.post_id}`}>
                <span className="social-rank-number viral"><Flame size={16} /></span>
                <div className="social-ranked-main">
                  <div className="social-row-meta">
                    <span className="platform-badge">{formatSourceName(post.source)}</span>
                    <span>{post.author || "Unknown author"}</span>
                    <span>{formatDateTime(post.publish_time)}</span>
                  </div>
                  <strong>{post.title?.trim() || post.content?.trim().slice(0, 120) || "Untitled post"}</strong>
                </div>
                <span className={`sentiment-pill ${post.sentiment_label || "neutral"}`}>{post.sentiment_label || "neutral"}</span>
                <div className="social-row-total">{formatCompactNumber(post.interactions)}</div>
              </article>
            ))}
          </div>
        ) : <EmptyState message="No posts crossed the viral threshold in the last 24 hours" />}
      </section>
    </div>
  );
}

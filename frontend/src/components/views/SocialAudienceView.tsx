"use client";

import { useState } from "react";
import { Clock3, Users } from "lucide-react";
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
import { formatCompactNumber, formatSourceName } from "@/lib/formatters";
import type { SocialAudienceData } from "@/lib/social-types";

function hourLabel(hour: number | null) {
  return hour === null ? "—" : `${String(hour).padStart(2, "0")}:00`;
}

export default function SocialAudienceView({
  data,
  updatedAt,
}: {
  data: SocialAudienceData | null;
  updatedAt: string | null;
}) {
  const [activeMetric, setActiveMetric] = useState<string | null>(null);
  if (!data) return <div className="social-view-loading"><ChartSkeleton /></div>;

  const { summary } = data;
  const interactiveMetric = (metric: string) => ({
    expanded: activeMetric === metric,
    onToggle: () => setActiveMetric((current) => current === metric ? null : metric),
  });
  const peakActivity = data.activity_by_hour.find((item) => item.hour === summary.peak_hour);
  const topPlatforms = data.platform_audience.slice(0, 5);

  return (
    <div className="social-analytics-view">
      <div className="overview-grid social-summary-grid">
        <MetricCard {...interactiveMetric("contributors")} label="Contributors" value={formatCompactNumber(summary.unique_contributors)} hint="Identified authors and channels" details={<MetricDetailList rows={topPlatforms.map((platform) => ({ label: formatSourceName(platform.source), value: formatCompactNumber(platform.contributors) }))} emptyMessage="No contributor breakdown available" />} />
        <MetricCard {...interactiveMetric("frequency")} label="Posts per contributor" value={summary.avg_posts_per_contributor.toLocaleString()} hint="Average contribution frequency" details={<MetricDetailList rows={[
          { label: "Posts analyzed", value: formatCompactNumber(summary.total_posts) },
          { label: "Unique contributors", value: formatCompactNumber(summary.unique_contributors) },
          ...data.contributor_segments.slice(0, 3).map((segment) => ({ label: segment.segment, value: `${formatCompactNumber(segment.contributors)} contributors` })),
        ]} />} />
        <MetricCard {...interactiveMetric("peak-hour")} label="Peak activity" value={hourLabel(summary.peak_hour)} hint="Hour with the most published content" tone="success" details={<MetricDetailList rows={peakActivity ? [
          { label: "Peak hour", value: hourLabel(peakActivity.hour) },
          { label: "Posts", value: formatCompactNumber(peakActivity.post_count) },
          { label: "Contributors", value: formatCompactNumber(peakActivity.active_contributors) },
          { label: "Interactions", value: formatCompactNumber(peakActivity.interactions) },
        ] : []} emptyMessage="No peak-hour data available" />} />
        <MetricCard {...interactiveMetric("platforms")} label="Active platforms" value={summary.active_platforms.toLocaleString()} hint={`${formatCompactNumber(summary.total_posts)} posts analyzed`} details={<MetricDetailList rows={topPlatforms.map((platform) => ({ label: formatSourceName(platform.source), value: `${formatCompactNumber(platform.post_count)} posts` }))} emptyMessage="No active platform data available" />} />
      </div>

      <div className="charts-grid social-two-column-grid">
        <ChartCard
          title={<><Clock3 size={20} /> Activity by Hour</>}
          description="When are contributors posting and interacting?"
          timeRange="All available data"
          unit="Posts / contributors"
          total={summary.total_posts}
          updatedAt={updatedAt}
        >
          {data.activity_by_hour.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.activity_by_hour}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,.1)" />
                <XAxis dataKey="hour" tickFormatter={(hour) => `${String(hour).padStart(2, "0")}:00`} stroke="#94a3b8" fontSize={11} />
                <YAxis tickFormatter={formatCompactNumber} stroke="#94a3b8" fontSize={12} />
                <Tooltip />
                <Legend />
                <Bar dataKey="post_count" name="Posts" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="active_contributors" name="Contributors" fill="#22d3ee" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState message="No hourly audience activity available" />}
        </ChartCard>

        <section className="social-analytics-panel social-segment-panel">
          <header className="social-view-header">
            <div>
              <h2><Users size={21} /> Contributor Mix</h2>
              <p>One-time, occasional, and core contributors.</p>
            </div>
          </header>
          {data.contributor_segments.length ? (
            <div className="social-segment-list">
              {data.contributor_segments.map((segment) => {
                const max = Math.max(...data.contributor_segments.map((item) => item.contributors), 1);
                return (
                  <div className="social-segment-row" key={segment.segment}>
                    <div><strong>{segment.segment}</strong><span>{formatCompactNumber(segment.contributors)} contributors</span></div>
                    <div className="social-segment-track"><span style={{ width: `${(segment.contributors / max) * 100}%` }} /></div>
                  </div>
                );
              })}
            </div>
          ) : <EmptyState message="No contributor frequency data available" />}
          <p className="social-methodology">{data.methodology}</p>
        </section>
      </div>

      <section className="social-analytics-panel">
        <header className="social-view-header">
          <div>
            <h2><Users size={21} /> Audience by Platform</h2>
            <p>Participating contributors and observed activity by source.</p>
          </div>
        </header>
        {data.platform_audience.length ? (
          <div className="social-platform-grid">
            {data.platform_audience.map((platform) => (
              <article className="social-platform-card" key={platform.source}>
                <span className="platform-badge">{formatSourceName(platform.source)}</span>
                <strong>{formatCompactNumber(platform.contributors)}</strong>
                <span>contributors</span>
                <div><span>{formatCompactNumber(platform.post_count)} posts</span><span>{formatCompactNumber(platform.interactions)} interactions</span></div>
              </article>
            ))}
          </div>
        ) : <EmptyState message="No platform audience data available" />}
      </section>
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  CalendarDays,
  FileQuestion,
  Newspaper,
  Tags,
  TrendingUp,
  UserRoundSearch,
  Users,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ChartSkeleton from "@/components/ui/ChartSkeleton";
import EmptyState from "@/components/ui/EmptyState";
import { formatCompactNumber, formatDateTime, truncateLabel } from "@/lib/formatters";

export type NewsAuthor = {
  author: string;
  source: string;
  article_count: number;
  top_category: string;
  first_published_at: string;
  last_published_at: string;
  positive_count: number;
  neutral_count: number;
  negative_count: number;
  analyzed_count: number;
  avg_sentiment: number | null;
};

type SourceBreakdown = {
  source: string;
  total_articles: number;
  authored_articles: number;
  missing_articles: number;
  author_count: number;
  coverage_pct: number;
};

type AuthorTrendPoint = {
  period: string;
  author: string;
  source: string;
  article_count: number;
};

type AuthorCategoryPoint = {
  author: string;
  source: string;
  category: string;
  article_count: number;
};

export type AuthorAnalytics = {
  summary: {
    total_authors: number;
    total_articles: number;
    authored_articles: number;
    unattributed_articles: number;
    coverage_pct: number;
  };
  authors: NewsAuthor[];
  source_breakdown: SourceBreakdown[];
  publication_trend: AuthorTrendPoint[];
  category_breakdown: AuthorCategoryPoint[];
  time_range: string;
  source: string | null;
};

type KpiId = "authors" | "attributed" | "coverage" | "missing";

const SOURCE_LABELS: Record<string, string> = {
  vnexpress: "VnExpress",
  tuoitre: "Tuổi Trẻ",
  thanhnien: "Thanh Niên",
  dantri: "Dân Trí",
  laodong: "Lao Động",
  tienphong: "Tiền Phong",
};

const CHART_COLORS = ["#60a5fa", "#a78bfa", "#34d399", "#fbbf24", "#fb7185"];

function sourceLabel(source: string) {
  return SOURCE_LABELS[source] ?? source;
}

function authorKey(author: Pick<NewsAuthor, "author" | "source">) {
  return `${author.source}::${author.author}`;
}

function sentimentLabel(score: number | null) {
  if (score === null) return { label: "Not analyzed", className: "unanalyzed" };
  if (score > 0.05) return { label: `Positive ${score.toFixed(2)}`, className: "positive" };
  if (score < -0.05) return { label: `Negative ${score.toFixed(2)}`, className: "negative" };
  return { label: `Neutral ${score.toFixed(2)}`, className: "neutral" };
}

function ChartPanel({ title, description, icon, badge, children }: {
  title: string;
  description: string;
  icon: React.ReactNode;
  badge: string;
  children: React.ReactNode;
}) {
  return (
    <article className="glass-panel authors-chart-panel">
      <header className="authors-section-header">
        <div>
          <h2>{icon} {title}</h2>
          <p>{description}</p>
        </div>
        <span>{badge}</span>
      </header>
      <div className="authors-chart">{children}</div>
    </article>
  );
}

export default function AuthorsView({ data, onViewArticles }: {
  data: AuthorAnalytics | null;
  onViewArticles: (author: string, source: string) => void;
}) {
  const [activeKpi, setActiveKpi] = useState<KpiId | null>(null);
  const [selectedAuthorKey, setSelectedAuthorKey] = useState<string | null>(null);

  const prepared = useMemo(() => {
    if (!data) return null;

    const topAuthors = data.authors.slice(0, 10).map((author) => ({
      ...author,
      label: `${author.author} · ${sourceLabel(author.source)}`,
    }));
    const trendAuthors = data.authors.slice(0, 5);
    const trendSeries = trendAuthors.map((author, index) => ({
      key: `author_${index}`,
      identity: authorKey(author),
      label: author.author,
      color: CHART_COLORS[index],
    }));
    const trendByPeriod = new Map<string, Record<string, string | number>>();
    for (const point of data.publication_trend ?? []) {
      const period = String(point.period);
      const row = trendByPeriod.get(period) ?? { period };
      const series = trendSeries.find((item) => item.identity === `${point.source}::${point.author}`);
      if (series) row[series.key] = Number(point.article_count);
      trendByPeriod.set(period, row);
    }
    const trendData = Array.from(trendByPeriod.values()).sort((left, right) =>
      String(left.period).localeCompare(String(right.period)),
    );

    const categoryTotals = new Map<string, number>();
    for (const point of data.category_breakdown ?? []) {
      const category = point.category || "uncategorized";
      categoryTotals.set(category, (categoryTotals.get(category) ?? 0) + Number(point.article_count));
    }
    const categorySeries = Array.from(categoryTotals.entries())
      .sort((left, right) => right[1] - left[1])
      .slice(0, 6)
      .map(([category], index) => ({
        category,
        key: `category_${index}`,
        color: CHART_COLORS[index % CHART_COLORS.length],
      }));
    const categoryByAuthor = new Map<string, Record<string, string | number>>();
    for (const author of trendAuthors) {
      categoryByAuthor.set(authorKey(author), { identity: authorKey(author), author: author.author });
    }
    for (const point of data.category_breakdown ?? []) {
      const row = categoryByAuthor.get(`${point.source}::${point.author}`);
      const category = point.category || "uncategorized";
      const series = categorySeries.find((item) => item.category === category);
      if (row && series) row[series.key] = Number(point.article_count);
    }

    return {
      topAuthors,
      trendSeries,
      trendData,
      categorySeries,
      categoryData: Array.from(categoryByAuthor.values()),
      sentimentData: topAuthors.map((author) => ({
        author: author.author,
        positive: Number(author.positive_count),
        neutral: Number(author.neutral_count),
        negative: Number(author.negative_count),
      })),
      sourceData: (data.source_breakdown ?? []).map((source) => ({
        ...source,
        label: sourceLabel(source.source),
      })),
    };
  }, [data]);

  if (data === null || prepared === null) {
    return <div className="authors-loading"><ChartSkeleton /></div>;
  }

  const selectedAuthor = data.authors.find((author) => authorKey(author) === selectedAuthorKey) ?? null;
  const topAuthor = data.authors[0];
  const bestCoverageSource = [...prepared.sourceData].sort((left, right) => right.coverage_pct - left.coverage_pct)[0];
  const worstCoverageSource = [...prepared.sourceData].sort((left, right) => right.missing_articles - left.missing_articles)[0];
  const averageArticles = data.summary.total_authors
    ? data.summary.authored_articles / data.summary.total_authors
    : 0;

  const kpis: Array<{
    id: KpiId;
    label: string;
    value: string;
    icon: React.ReactNode;
    warning?: boolean;
    details: Array<[string, string]>;
  }> = [
    {
      id: "authors",
      label: "Named authors",
      value: formatCompactNumber(data.summary.total_authors),
      icon: <Users size={19} />,
      details: [
        ["Sources represented", String(prepared.sourceData.filter((item) => item.author_count > 0).length)],
        ["Average output", `${averageArticles.toFixed(1)} articles / author`],
        ["Top author", topAuthor ? `${topAuthor.author} (${topAuthor.article_count})` : "Not available"],
      ],
    },
    {
      id: "attributed",
      label: "Attributed articles",
      value: formatCompactNumber(data.summary.authored_articles),
      icon: <BookOpen size={19} />,
      details: [
        ["All articles", data.summary.total_articles.toLocaleString()],
        ["Attributed share", `${data.summary.coverage_pct.toFixed(1)}%`],
        ["Top contributor", topAuthor ? sourceLabel(topAuthor.source) : "Not available"],
      ],
    },
    {
      id: "coverage",
      label: "Author coverage",
      value: `${data.summary.coverage_pct.toFixed(1)}%`,
      icon: <Newspaper size={19} />,
      details: [
        ["Attributed", data.summary.authored_articles.toLocaleString()],
        ["Missing", data.summary.unattributed_articles.toLocaleString()],
        ["Best source", bestCoverageSource ? `${bestCoverageSource.label} (${bestCoverageSource.coverage_pct.toFixed(1)}%)` : "Not available"],
      ],
    },
    {
      id: "missing",
      label: "Missing author",
      value: formatCompactNumber(data.summary.unattributed_articles),
      icon: <FileQuestion size={19} />,
      warning: true,
      details: [
        ["Missing share", `${(100 - data.summary.coverage_pct).toFixed(1)}%`],
        ["Total checked", data.summary.total_articles.toLocaleString()],
        ["Largest gap", worstCoverageSource ? `${worstCoverageSource.label} (${worstCoverageSource.missing_articles.toLocaleString()})` : "Not available"],
      ],
    },
  ];

  return (
    <section className="authors-view" aria-label="Official news authors">
      <div className="author-summary-grid">
        {kpis.map((kpi) => {
          const expanded = activeKpi === kpi.id;
          return (
            <button
              type="button"
              key={kpi.id}
              className={`glass-panel author-summary-card ${kpi.warning ? "warning" : ""} ${expanded ? "expanded" : ""}`}
              aria-expanded={expanded}
              onClick={() => setActiveKpi(expanded ? null : kpi.id)}
            >
              {!expanded ? (
                <>
                  {kpi.icon}
                  <div>
                    <span>{kpi.label}</span>
                    <strong>{kpi.value}</strong>
                    <small>View details →</small>
                  </div>
                </>
              ) : (
                <div className="author-kpi-details">
                  <span>{kpi.label} details</span>
                  <ul>
                    {kpi.details.map(([label, value]) => (
                      <li key={label}><span>{label}</span><strong>{value}</strong></li>
                    ))}
                  </ul>
                </div>
              )}
            </button>
          );
        })}
      </div>

      <div className="authors-analysis-grid">
        <ChartPanel title="Top Authors" description="Authors ranked by attributed article volume." icon={<Users size={21} />} badge={`Top ${prepared.topAuthors.length}`}>
          {prepared.topAuthors.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={prepared.topAuthors} layout="vertical" margin={{ top: 4, right: 44, left: 20, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" horizontal={false} />
                <XAxis type="number" allowDecimals={false} stroke="#94a3b8" fontSize={11} tickFormatter={formatCompactNumber} />
                <YAxis type="category" dataKey="label" width={135} stroke="#94a3b8" fontSize={11} tickFormatter={(value) => truncateLabel(String(value), 21)} />
                <Tooltip cursor={false} formatter={(value) => [`${Number(value).toLocaleString()} articles`, "Published"]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }} />
                <Bar dataKey="article_count" fill="#3b82f6" radius={[0, 5, 5, 0]}><LabelList dataKey="article_count" position="right" fill="#cbd5e1" fontSize={10} /></Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState message="No named authors are available for this source" />}
        </ChartPanel>

        <ChartPanel title="Coverage by Source" description="Share of articles that include a usable author name." icon={<Newspaper size={21} />} badge="Percent">
          {prepared.sourceData.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={prepared.sourceData} layout="vertical" margin={{ top: 4, right: 50, left: 10, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} stroke="#94a3b8" fontSize={11} tickFormatter={(value) => `${value}%`} />
                <YAxis type="category" dataKey="label" width={90} stroke="#94a3b8" fontSize={11} />
                <Tooltip cursor={false} formatter={(value) => [`${Number(value).toFixed(1)}%`, "Coverage"]} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }} />
                <Bar dataKey="coverage_pct" fill="#10b981" radius={[0, 5, 5, 0]}><LabelList dataKey="coverage_pct" position="right" fill="#cbd5e1" fontSize={10} formatter={(value) => `${Number(value).toFixed(1)}%`} /></Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState message="No source coverage data" />}
        </ChartPanel>

        <ChartPanel title="Publication Trend" description="Article output over time for the five leading authors." icon={<TrendingUp size={21} />} badge={data.time_range === "all" ? "Monthly" : "Daily"}>
          {prepared.trendData.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={prepared.trendData} margin={{ top: 6, right: 12, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis dataKey="period" stroke="#94a3b8" fontSize={10} minTickGap={24} tickFormatter={(value) => String(value).slice(0, 7)} />
                <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                <Tooltip contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                {prepared.trendSeries.map((series) => <Line key={series.key} type="monotone" dataKey={series.key} name={truncateLabel(series.label, 18)} stroke={series.color} strokeWidth={2} dot={false} connectNulls />)}
              </LineChart>
            </ResponsiveContainer>
          ) : <EmptyState message="No publication timeline data" />}
        </ChartPanel>

        <ChartPanel title="Category Expertise" description="Category mix for the five leading authors." icon={<Tags size={21} />} badge="Top categories">
          {prepared.categoryData.length && prepared.categorySeries.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={prepared.categoryData} margin={{ top: 6, right: 8, left: 0, bottom: 34 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={false} />
                <XAxis dataKey="author" stroke="#94a3b8" fontSize={10} angle={-20} textAnchor="end" height={58} tickFormatter={(value) => truncateLabel(String(value), 13)} />
                <YAxis stroke="#94a3b8" fontSize={11} allowDecimals={false} />
                <Tooltip contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                {prepared.categorySeries.map((series) => <Bar key={series.key} dataKey={series.key} name={series.category} stackId="categories" fill={series.color} />)}
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState message="No author category data" />}
        </ChartPanel>

        <ChartPanel title="Sentiment Comparison" description="Analyzed article sentiment for the ten leading authors." icon={<UserRoundSearch size={21} />} badge="Analyzed articles">
          {prepared.sentimentData.some((item) => item.positive + item.neutral + item.negative > 0) ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={prepared.sentimentData} layout="vertical" margin={{ top: 4, right: 12, left: 20, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" horizontal={false} />
                <XAxis type="number" allowDecimals={false} stroke="#94a3b8" fontSize={11} />
                <YAxis type="category" dataKey="author" width={120} stroke="#94a3b8" fontSize={10} tickFormatter={(value) => truncateLabel(String(value), 18)} />
                <Tooltip contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="positive" name="Positive" stackId="sentiment" fill="#10b981" />
                <Bar dataKey="neutral" name="Neutral" stackId="sentiment" fill="#64748b" />
                <Bar dataKey="negative" name="Negative" stackId="sentiment" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState message="No sentiment analysis is available for these authors" />}
        </ChartPanel>

        <ChartPanel title="Missing Author by Source" description="Attributed and unattributed article volume by publisher." icon={<FileQuestion size={21} />} badge="Data quality">
          {prepared.sourceData.length ? (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={prepared.sourceData} margin={{ top: 6, right: 8, left: 0, bottom: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" vertical={false} />
                <XAxis dataKey="label" stroke="#94a3b8" fontSize={10} tickFormatter={(value) => truncateLabel(String(value), 12)} />
                <YAxis stroke="#94a3b8" fontSize={11} tickFormatter={formatCompactNumber} />
                <Tooltip formatter={(value) => Number(value).toLocaleString()} contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar dataKey="authored_articles" name="Attributed" stackId="quality" fill="#3b82f6" />
                <Bar dataKey="missing_articles" name="Missing author" stackId="quality" fill="#f59e0b" />
              </BarChart>
            </ResponsiveContainer>
          ) : <EmptyState message="No source quality data" />}
        </ChartPanel>
      </div>

      {selectedAuthor && (
        <article className="glass-panel author-detail-panel" aria-label={`Details for ${selectedAuthor.author}`}>
          <header>
            <div className="author-detail-identity">
              <span className="author-detail-avatar">{selectedAuthor.author.charAt(0).toUpperCase()}</span>
              <div><h2>{selectedAuthor.author}</h2><span className={`tag ${selectedAuthor.source.toLowerCase()}`}>{sourceLabel(selectedAuthor.source)}</span></div>
            </div>
            <button type="button" onClick={() => setSelectedAuthorKey(null)} aria-label="Close author details"><X size={17} /></button>
          </header>
          <div className="author-detail-metrics">
            <div><span>Articles</span><strong>{selectedAuthor.article_count.toLocaleString()}</strong></div>
            <div><span>Top category</span><strong className="author-category">{selectedAuthor.top_category || "—"}</strong></div>
            <div><span>First published</span><strong>{formatDateTime(selectedAuthor.first_published_at)}</strong></div>
            <div><span>Latest published</span><strong>{formatDateTime(selectedAuthor.last_published_at)}</strong></div>
            <div><span>Analyzed</span><strong>{selectedAuthor.analyzed_count} / {selectedAuthor.article_count}</strong></div>
            <div><span>Average sentiment</span><strong>{sentimentLabel(selectedAuthor.avg_sentiment).label}</strong></div>
          </div>
          <div className="author-detail-sentiment">
            <span className="positive">Positive <strong>{selectedAuthor.positive_count}</strong></span>
            <span className="neutral">Neutral <strong>{selectedAuthor.neutral_count}</strong></span>
            <span className="negative">Negative <strong>{selectedAuthor.negative_count}</strong></span>
          </div>
          <button type="button" className="author-articles-button" onClick={() => onViewArticles(selectedAuthor.author, selectedAuthor.source)}>View all articles <ArrowRight size={14} /></button>
        </article>
      )}

      <div className="glass-panel authors-table-panel">
        <header className="authors-section-header">
          <div><h2><Newspaper size={21} /> Author Directory</h2><p>Select an author for activity, category, and sentiment details.</p></div>
          <span>{data.authors.length} shown</span>
        </header>
        {data.authors.length ? (
          <div className="table-scroll-container">
            <table className="data-table authors-table">
              <thead><tr><th>Author</th><th>Source</th><th>Articles</th><th>Top category</th><th>Active period</th><th>Avg sentiment</th><th>Analyzed</th><th aria-label="Actions" /></tr></thead>
              <tbody>
                {data.authors.map((author) => {
                  const sentiment = sentimentLabel(author.avg_sentiment);
                  return (
                    <tr key={authorKey(author)} className={selectedAuthorKey === authorKey(author) ? "selected" : ""}>
                      <td><button type="button" className="author-name-button" onClick={() => setSelectedAuthorKey(authorKey(author))}>{author.author}</button></td>
                      <td><span className={`tag ${author.source.toLowerCase()}`}>{sourceLabel(author.source)}</span></td>
                      <td>{Number(author.article_count).toLocaleString()}</td>
                      <td className="author-category">{author.top_category || "—"}</td>
                      <td className="author-active-period"><CalendarDays size={13} /> {formatDateTime(author.first_published_at)} – {formatDateTime(author.last_published_at)}</td>
                      <td><span className={`author-sentiment ${sentiment.className}`}>{sentiment.label}</span></td>
                      <td>{Number(author.analyzed_count).toLocaleString()} / {Number(author.article_count).toLocaleString()}</td>
                      <td><button type="button" className="author-articles-button print-hide" onClick={() => onViewArticles(author.author, author.source)}>View articles <ArrowRight size={14} /></button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : <EmptyState message="No authors are available for this filter" />}
      </div>
    </section>
  );
}

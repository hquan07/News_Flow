"use client";

import {
  ArrowRight,
  BookOpen,
  FileQuestion,
  Newspaper,
  Users,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import ChartSkeleton from "@/components/ui/ChartSkeleton";
import EmptyState from "@/components/ui/EmptyState";
import { formatCompactNumber, truncateLabel } from "@/lib/formatters";

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

export type AuthorAnalytics = {
  summary: {
    total_authors: number;
    total_articles: number;
    authored_articles: number;
    unattributed_articles: number;
    coverage_pct: number;
  };
  authors: NewsAuthor[];
  time_range: string;
  source: string | null;
};

const SOURCE_LABELS: Record<string, string> = {
  vnexpress: "VnExpress",
  tuoitre: "Tuổi Trẻ",
  thanhnien: "Thanh Niên",
  dantri: "Dân Trí",
  laodong: "Lao Động",
  tienphong: "Tiền Phong",
};

function sentimentLabel(score: number | null) {
  if (score === null) return { label: "Not analyzed", className: "unanalyzed" };
  if (score > 0.05) return { label: `Positive ${score.toFixed(2)}`, className: "positive" };
  if (score < -0.05) return { label: `Negative ${score.toFixed(2)}`, className: "negative" };
  return { label: `Neutral ${score.toFixed(2)}`, className: "neutral" };
}

export default function AuthorsView({
  data,
  onViewArticles,
}: {
  data: AuthorAnalytics | null;
  onViewArticles: (author: string, source: string) => void;
}) {
  if (data === null) {
    return <div className="authors-loading"><ChartSkeleton /></div>;
  }

  const topAuthors = data.authors.slice(0, 10).map((author) => ({
    ...author,
    label: `${author.author} · ${SOURCE_LABELS[author.source] ?? author.source}`,
  }));

  return (
    <section className="authors-view" aria-label="Official news authors">
      <div className="author-summary-grid">
        <article className="glass-panel author-summary-card">
          <Users size={19} />
          <div><span>Named authors</span><strong>{formatCompactNumber(data.summary.total_authors)}</strong></div>
        </article>
        <article className="glass-panel author-summary-card">
          <BookOpen size={19} />
          <div><span>Attributed articles</span><strong>{formatCompactNumber(data.summary.authored_articles)}</strong></div>
        </article>
        <article className="glass-panel author-summary-card">
          <Newspaper size={19} />
          <div><span>Author coverage</span><strong>{data.summary.coverage_pct.toFixed(1)}%</strong></div>
        </article>
        <article className="glass-panel author-summary-card warning">
          <FileQuestion size={19} />
          <div><span>Missing author</span><strong>{formatCompactNumber(data.summary.unattributed_articles)}</strong></div>
        </article>
      </div>

      <div className="glass-panel authors-chart-panel">
        <header className="authors-section-header">
          <div>
            <h2><Users size={21} /> Top Authors</h2>
            <p>Authors are grouped by normalized name and news source.</p>
          </div>
          <span>Top {topAuthors.length}</span>
        </header>
        {topAuthors.length ? (
          <div className="authors-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topAuthors} layout="vertical" margin={{ top: 4, right: 44, left: 28, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" horizontal={false} />
                <XAxis type="number" allowDecimals={false} stroke="#94a3b8" fontSize={11} tickFormatter={formatCompactNumber} />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={150}
                  stroke="#94a3b8"
                  fontSize={11}
                  tickFormatter={(value) => truncateLabel(String(value), 24)}
                />
                <Tooltip
                  cursor={false}
                  formatter={(value) => [`${Number(value).toLocaleString()} articles`, "Published"]}
                  contentStyle={{ backgroundColor: "#1e293b", border: "1px solid rgba(255,255,255,0.15)" }}
                />
                <Bar dataKey="article_count" fill="#3b82f6" radius={[0, 5, 5, 0]}>
                  <LabelList dataKey="article_count" position="right" fill="#cbd5e1" fontSize={10} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState message="No named authors are available for this source" />
        )}
      </div>

      <div className="glass-panel authors-table-panel">
        <header className="authors-section-header">
          <div>
            <h2><Newspaper size={21} /> Author Directory</h2>
            <p>Publication volume, editorial focus, and analyzed sentiment.</p>
          </div>
          <span>{data.authors.length} shown</span>
        </header>
        {data.authors.length ? (
          <div className="table-scroll-container">
            <table className="data-table authors-table">
              <thead>
                <tr>
                  <th>Author</th>
                  <th>Source</th>
                  <th>Articles</th>
                  <th>Top category</th>
                  <th>Avg sentiment</th>
                  <th>Analyzed</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {data.authors.map((author) => {
                  const sentiment = sentimentLabel(author.avg_sentiment);
                  return (
                    <tr key={`${author.source}-${author.author}`}>
                      <td><strong>{author.author}</strong></td>
                      <td><span className={`tag ${author.source.toLowerCase()}`}>{SOURCE_LABELS[author.source] ?? author.source}</span></td>
                      <td>{Number(author.article_count).toLocaleString()}</td>
                      <td className="author-category">{author.top_category || "—"}</td>
                      <td><span className={`author-sentiment ${sentiment.className}`}>{sentiment.label}</span></td>
                      <td>{Number(author.analyzed_count).toLocaleString()} / {Number(author.article_count).toLocaleString()}</td>
                      <td>
                        <button
                          type="button"
                          className="author-articles-button print-hide"
                          onClick={() => onViewArticles(author.author, author.source)}
                        >
                          View articles <ArrowRight size={14} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </section>
  );
}

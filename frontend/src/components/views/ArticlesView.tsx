"use client";

import { useState, type Dispatch, type SetStateAction } from "react";
import { BookOpen, BrainCircuit, Check, Copy, FileText, Filter, Search, X } from "lucide-react";
import type { ArticleAlertFilter } from "@/lib/alert-types";
import {
  EMPTY_ARTICLE_FILTERS,
  type ArticleFilters,
} from "@/lib/article-types";

const ARTICLE_SOURCES = [
  ["vnexpress", "VnExpress"],
  ["tuoitre", "Tuổi Trẻ"],
  ["thanhnien", "Thanh Niên"],
  ["dantri", "Dân Trí"],
  ["laodong", "Lao Động"],
  ["tienphong", "Tiền Phong"],
] as const;

const ARTICLE_CATEGORIES = [
  "general",
  "sports",
  "tech",
  "economy",
  "politics",
  "entertainment",
  "health",
  "education",
  "world",
  "law",
] as const;

type Article = {
  article_id: string;
  title: string;
  url: string;
  source: string;
  author?: string;
  category?: string;
  publish_date?: string;
  sentiment_score: number | null;
  sentiment_label?: string | null;
  sentiment_analyzed?: boolean | number;
};

type ArticlesMeta = {
  total_pages: number;
  total?: number;
};

type ArticlesViewProps = {
  title: string;
  articles: Article[];
  articlesMeta: ArticlesMeta;
  page: number;
  setPage: Dispatch<SetStateAction<number>>;
  searchQuery: string;
  setSearchQuery: Dispatch<SetStateAction<string>>;
  loading: boolean;
  filters: ArticleFilters;
  setFilters: (filters: ArticleFilters) => void;
  contextFilter: ArticleAlertFilter | null;
  clearContextFilter: () => void;
  trackClick: (articleHash: string) => void | Promise<void>;
  timeAgo: (date: string) => string;
  exportToCSV: (data: Record<string, unknown>[], filename: string) => void;
  canExportCSV: boolean;
  onExplainArticle: (articleId: string) => void;
};

export default function ArticlesView({
  title,
  articles,
  articlesMeta,
  page,
  setPage,
  searchQuery,
  setSearchQuery,
  loading,
  filters,
  setFilters,
  contextFilter,
  clearContextFilter,
  trackClick,
  timeAgo,
  exportToCSV,
  canExportCSV,
  onExplainArticle,
}: ArticlesViewProps) {
  const [copiedArticleId, setCopiedArticleId] = useState("");
  const activeFilterCount = Object.values(filters).filter(Boolean).length;
  const invalidDateRange = Boolean(
    filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo,
  );

  const updateFilter = (field: keyof ArticleFilters, value: string) => {
    setFilters({ ...filters, [field]: value });
  };

  const copyArticleId = async (articleId: string) => {
    await navigator.clipboard.writeText(articleId);
    setCopiedArticleId(articleId);
    window.setTimeout(() => setCopiedArticleId((current) => current === articleId ? "" : current), 1800);
  };

  return (
    <>
      <div className="glass-panel" style={{ minHeight: "600px" }}>
        <div
          className="panel-header"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div className="panel-title">
            <BookOpen size={20} /> {title}
          </div>
          {canExportCSV && <button
            onClick={() => {
              const dataToExport = articles.map((a) => ({
                article_id: a.article_id,
                title: a.title,
                source: a.source,
                category: a.category,
                publish_date: a.publish_date,
                url: a.url,
              }));
              exportToCSV(dataToExport, "articles_database.csv");
            }}
            className="print-hide"
            style={{
              background: "rgba(16, 185, 129, 0.2)",
              border: "1px solid rgba(16, 185, 129, 0.4)",
              padding: "4px 8px",
              borderRadius: "6px",
              color: "#10b981",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "4px",
              fontSize: "0.8rem",
            }}
          >
            <FileText size={14} /> CSV
          </button>}
        </div>
        <div className="article-search-row">
          <div className="article-search-field">
            <Search size={17} aria-hidden="true" />
            <input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search article titles..."
              aria-label="Search articles by title"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                aria-label="Clear article search"
                title="Clear search"
              >
                <X size={16} />
              </button>
            )}
          </div>
          <span className="article-search-meta" role="status" aria-live="polite">
            {loading
              ? "Searching…"
              : `${articlesMeta.total ?? articles.length} article${(articlesMeta.total ?? articles.length) === 1 ? "" : "s"}`}
          </span>
        </div>
        <div className="article-filter-panel" aria-label="Article filters">
          <div className="article-filter-heading">
            <span><Filter size={16} /> Filters</span>
            {activeFilterCount > 0 && (
              <button
                type="button"
                onClick={() => setFilters({ ...EMPTY_ARTICLE_FILTERS })}
              >
                <X size={14} /> Clear all ({activeFilterCount})
              </button>
            )}
          </div>
          <div className="article-filter-grid">
            <label>
              <span>Author</span>
              <input
                type="search"
                value={filters.author}
                placeholder="Exact author name"
                onChange={(event) => updateFilter("author", event.target.value)}
              />
            </label>
            <label>
              <span>Source</span>
              <select
                value={filters.source}
                onChange={(event) => updateFilter("source", event.target.value)}
              >
                <option value="">All sources</option>
                {ARTICLE_SOURCES.map(([value, label]) => (
                  <option key={value} value={value}>{label}</option>
                ))}
              </select>
            </label>
            <label>
              <span>Category</span>
              <select
                value={filters.category}
                onChange={(event) => updateFilter("category", event.target.value)}
              >
                <option value="">All categories</option>
                {ARTICLE_CATEGORIES.map((category) => (
                  <option key={category} value={category}>
                    {category.charAt(0).toUpperCase() + category.slice(1)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>From date</span>
              <input
                type="date"
                value={filters.dateFrom}
                max={filters.dateTo || undefined}
                onChange={(event) => updateFilter("dateFrom", event.target.value)}
              />
            </label>
            <label>
              <span>To date</span>
              <input
                type="date"
                value={filters.dateTo}
                min={filters.dateFrom || undefined}
                onChange={(event) => updateFilter("dateTo", event.target.value)}
              />
            </label>
            <label>
              <span>Entity</span>
              <input
                type="search"
                value={filters.entity}
                placeholder="e.g. VinFast"
                onChange={(event) => updateFilter("entity", event.target.value)}
              />
            </label>
            <label>
              <span>Keyword</span>
              <input
                type="search"
                value={filters.keyword}
                placeholder="e.g. lãi suất"
                onChange={(event) => updateFilter("keyword", event.target.value)}
              />
            </label>
            <label>
              <span>Sentiment</span>
              <select
                value={filters.sentiment}
                onChange={(event) => updateFilter("sentiment", event.target.value)}
              >
                <option value="">All sentiments</option>
                <option value="positive">Positive</option>
                <option value="neutral">Neutral</option>
                <option value="negative">Negative</option>
                <option value="unanalyzed">Not analyzed</option>
              </select>
            </label>
          </div>
          {invalidDateRange && (
            <p className="article-filter-error" role="alert">
              From date must be earlier than or equal to the To date.
            </p>
          )}
        </div>
        {contextFilter && (
          <div className="article-context-filter" role="status">
            <span>
              <strong>Alert filter:</strong> {contextFilter.label}
            </span>
            <button type="button" onClick={clearContextFilter}>
              <X size={15} /> Clear filter
            </button>
          </div>
        )}
        <div className="table-scroll-container">
          <table className="data-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Source</th>
              <th>Author</th>
              <th>Category</th>
              <th>Published</th>
              <th>Sentiment</th>
              <th>Article ID</th>
            </tr>
          </thead>
          <tbody>
            {articles.map((a) => (
              <tr key={a.article_id}>
                <td>
                  <a
                    href={a.url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() => trackClick(a.article_id)}
                  >
                    {a.title}
                  </a>
                </td>
                <td>
                  <span className={`tag ${a.source?.toLowerCase()}`}>
                    {a.source}
                  </span>
                </td>
                <td>{a.author || "—"}</td>
                <td>{a.category || "-"}</td>
                <td>{a.publish_date ? timeAgo(a.publish_date) : "-"}</td>
                <td>
                  {a.sentiment_analyzed && a.sentiment_score !== null ? (
                    <span
                      style={{
                        color:
                          a.sentiment_score > 0
                            ? "var(--accent-green)"
                            : a.sentiment_score < 0
                              ? "#ef4444"
                              : "var(--text-muted)",
                      }}
                      title={a.sentiment_label || "Analyzed sentiment"}
                    >
                      {a.sentiment_score.toFixed(2)}
                    </span>
                  ) : (
                    <span className="sentiment-unavailable" title="Waiting for NLP analysis">
                      Not analyzed
                    </span>
                  )}
                </td>
                <td><div className="article-id-actions"><code>{a.article_id}</code><div><button type="button" aria-label={`Copy article ID ${a.article_id}`} onClick={() => void copyArticleId(a.article_id)}>{copiedArticleId === a.article_id ? <Check size={13} /> : <Copy size={13} />} {copiedArticleId === a.article_id ? "Copied" : "Copy"}</button><button type="button" onClick={() => onExplainArticle(a.article_id)}><BrainCircuit size={13} /> Explain NLP</button></div></div></td>
              </tr>
            ))}
            {articles.length === 0 && (
              <tr>
                <td
                  colSpan={6}
                  style={{
                    textAlign: "center",
                    padding: "3rem",
                    color: "var(--text-muted)",
                  }}
                >
                  {loading
                    ? "Loading articles…"
                    : searchQuery || activeFilterCount > 0 || contextFilter
                      ? "No articles match the current search and filters."
                      : "No articles found in the database."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
        </div>
        {articlesMeta.total_pages > 1 && (
          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setPage((p: number) => p - 1)}>
              ← Previous
            </button>
            <span className="page-info">
              Page {page} / {articlesMeta.total_pages}
            </span>
            <button
              disabled={page >= articlesMeta.total_pages}
              onClick={() => setPage((p: number) => p + 1)}
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </>
  );
}

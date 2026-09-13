"use client";

import React, { useState } from "react";
import { BookOpen, Clock , FileText } from "lucide-react";

export default function ArticlesView({
  articles,
  articlesMeta,
  page,
  setPage,
  trackClick,
  timeAgo,
  exportToCSV,
}: any) {
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
            <BookOpen size={20} /> Latest Articles
          </div>
          <button
            onClick={() => {
              const dataToExport = articles.map((a: any) => ({
                id: a.id,
                title: a.title,
                source: a.source,
                category: a.category,
                pub_date: a.pub_date,
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
          </button>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Source</th>
              <th>Category</th>
              <th>Published</th>
              <th>Sentiment</th>
            </tr>
          </thead>
          <tbody>
            {articles.map((a: any, i: number) => (
              <tr key={i}>
                <td>
                  <a
                    href={a.url}
                    target="_blank"
                    rel="noreferrer"
                    onClick={() => trackClick(a.url_hash)}
                  >
                    {a.title}
                  </a>
                </td>
                <td>
                  <span className={`tag ${a.source?.toLowerCase()}`}>
                    {a.source}
                  </span>
                </td>
                <td>{a.category || "-"}</td>
                <td>{a.publish_date ? timeAgo(a.publish_date) : "-"}</td>
                <td>
                  <span
                    style={{
                      color:
                        a.sentiment_score > 0
                          ? "var(--accent-green)"
                          : a.sentiment_score < 0
                            ? "#ef4444"
                            : "var(--text-muted)",
                    }}
                  >
                    {a.sentiment_score?.toFixed(2) || "0.00"}
                  </span>
                </td>
              </tr>
            ))}
            {articles.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  style={{
                    textAlign: "center",
                    padding: "3rem",
                    color: "var(--text-muted)",
                  }}
                >
                  No articles found in the database.
                </td>
              </tr>
            )}
          </tbody>
        </table>
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

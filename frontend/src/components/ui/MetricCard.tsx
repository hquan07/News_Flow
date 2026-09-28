import type { ReactNode } from "react";

type MetricTone = "default" | "success" | "warning" | "danger";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  hint: string;
  loading?: boolean;
  tone?: MetricTone;
  title?: string;
}

export default function MetricCard({
  label,
  value,
  hint,
  loading = false,
  tone = "default",
  title,
}: MetricCardProps) {
  return (
    <article
      className={`glass-panel metric-card metric-card-static metric-tone-${tone}`}
      aria-busy={loading}
      title={title}
    >
      <div className="metric-content">
        <div className="metric-label">{label}</div>
        <div className="metric-value">{loading ? "—" : value}</div>
        <div className="chart-description">
          {loading ? "Loading metric…" : hint}
        </div>
      </div>
    </article>
  );
}

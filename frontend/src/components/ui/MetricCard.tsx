import type { ReactNode } from "react";

type MetricTone = "default" | "success" | "warning" | "danger";

interface MetricCardProps {
  label: string;
  value: ReactNode;
  hint: string;
  loading?: boolean;
  tone?: MetricTone;
  title?: string;
  details?: ReactNode;
  expanded?: boolean;
  onToggle?: () => void;
}

export default function MetricCard({
  label,
  value,
  hint,
  loading = false,
  tone = "default",
  title,
  details,
  expanded = false,
  onToggle,
}: MetricCardProps) {
  const content = expanded ? (
    <div className="metric-details">
      <div className="metric-label metric-details-heading">{label} details</div>
      {details}
    </div>
  ) : (
    <div className="metric-content">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{loading ? "—" : value}</div>
      <div className="chart-description">
        {loading ? "Loading metric…" : hint}
      </div>
      {onToggle && !loading && <div className="metric-hint">Click for details</div>}
    </div>
  );

  if (onToggle) {
    return (
      <button
        type="button"
        className={`glass-panel metric-card metric-card-interactive metric-tone-${tone} ${expanded ? "expanded" : ""}`}
        aria-busy={loading}
        aria-expanded={expanded}
        title={title}
        onClick={onToggle}
        disabled={loading}
      >
        {content}
      </button>
    );
  }

  return (
    <article
      className={`glass-panel metric-card metric-card-static metric-tone-${tone}`}
      aria-busy={loading}
      title={title}
    >
      {content}
    </article>
  );
}

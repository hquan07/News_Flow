import type { ReactNode } from "react";
import { Clock3, Database } from "lucide-react";
import { formatCompactNumber, formatDateTime } from "@/lib/formatters";

interface ChartCardProps {
  title: ReactNode;
  description: string;
  timeRange: string;
  unit: string;
  total?: number;
  updatedAt?: string | null;
  actions?: ReactNode;
  wide?: boolean;
  large?: boolean;
  children: ReactNode;
}

export default function ChartCard({
  title,
  description,
  timeRange,
  unit,
  total,
  updatedAt,
  actions,
  wide = false,
  large = false,
  children,
}: ChartCardProps) {
  return (
    <section className={`glass-panel chart-card${wide ? " chart-card-wide" : ""}`}>
      <div className="chart-card-header">
        <div>
          <h2 className="panel-title">{title}</h2>
          <p className="chart-description">{description}</p>
        </div>
        {actions && <div className="chart-actions">{actions}</div>}
      </div>
      <div className="chart-meta" aria-label="Chart context">
        <span><Clock3 size={13} /> {timeRange}</span>
        <span>Unit: {unit}</span>
        {typeof total === "number" && (
          <span><Database size={13} /> {formatCompactNumber(total)} records</span>
        )}
        <span>Updated: {formatDateTime(updatedAt)}</span>
      </div>
      <div className={large ? "chart-container-large" : "chart-container"}>
        {children}
      </div>
    </section>
  );
}

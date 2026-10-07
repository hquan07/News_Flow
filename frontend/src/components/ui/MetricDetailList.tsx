import type { ReactNode } from "react";

interface MetricDetailRow {
  label: ReactNode;
  value: ReactNode;
}

export default function MetricDetailList({
  rows,
  emptyMessage = "No detail data available",
}: {
  rows: MetricDetailRow[];
  emptyMessage?: string;
}) {
  if (!rows.length) {
    return <p className="chart-description">{emptyMessage}</p>;
  }

  return (
    <ul className="metric-details-list">
      {rows.map((row, index) => (
        <li key={index}>
          <span>{row.label}</span>
          <strong>{row.value}</strong>
        </li>
      ))}
    </ul>
  );
}

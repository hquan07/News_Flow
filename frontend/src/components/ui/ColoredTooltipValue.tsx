import type { CSSProperties, ReactNode } from "react";

export const DARK_TOOLTIP_CONTENT_STYLE: CSSProperties = {
  backgroundColor: "#1e293b",
  border: "1px solid rgba(255,255,255,0.15)",
  color: "#f8fafc",
};

export const DARK_TOOLTIP_ITEM_STYLE: CSSProperties = { color: "#f8fafc" };

const READABLE_COLORS: Record<string, string> = {
  "#3b82f6": "#60a5fa",
  "#8b5cf6": "#a78bfa",
  "#ef4444": "#f87171",
  "#ec4899": "#f472b6",
};

export function readableChartColor(color: string): string {
  return READABLE_COLORS[color.toLowerCase()] ?? color;
}

export default function ColoredTooltipValue({ color, children }: { color: string; children: ReactNode }) {
  return <span className="chart-colored-value" style={{ color: readableChartColor(color) }}>
    <span className="chart-colored-value-swatch" style={{ backgroundColor: color }} aria-hidden="true" />
    {children}
  </span>;
}

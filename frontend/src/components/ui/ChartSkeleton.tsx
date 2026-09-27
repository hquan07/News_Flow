import React from 'react';
import { Activity } from 'lucide-react';

interface ChartSkeletonProps {
  height?: string;
}

export default function ChartSkeleton({ height = "100%" }: ChartSkeletonProps) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      height: height,
      color: "var(--accent-blue)",
      padding: "2rem",
      animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite"
    }}>
      <Activity size={32} style={{ marginBottom: "12px", opacity: 0.5 }} />
      <span style={{ fontSize: "0.95rem", opacity: 0.7 }}>Loading data...</span>
    </div>
  );
}

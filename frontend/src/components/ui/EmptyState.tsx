import React from 'react';
import { Database } from 'lucide-react';

interface EmptyStateProps {
  message?: string;
  height?: string;
}

export default function EmptyState({ message = "No data available", height = "100%" }: EmptyStateProps) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      height: height,
      color: "var(--text-muted)",
      padding: "2rem"
    }}>
      <Database size={32} style={{ opacity: 0.2, marginBottom: "12px" }} />
      <span style={{ fontSize: "0.95rem" }}>{message}</span>
    </div>
  );
}

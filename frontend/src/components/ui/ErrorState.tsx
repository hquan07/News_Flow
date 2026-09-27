import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
  height?: string;
}

export default function ErrorState({ message = "Failed to load data", onRetry, height = "100%" }: ErrorStateProps) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      height: height,
      color: "#ef4444",
      padding: "2rem",
      background: "rgba(239, 68, 68, 0.05)",
      borderRadius: "12px",
      border: "1px dashed rgba(239, 68, 68, 0.2)"
    }}>
      <AlertCircle size={32} style={{ marginBottom: "12px" }} />
      <span style={{ fontSize: "0.95rem", marginBottom: onRetry ? "16px" : "0" }}>{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            color: "#ef4444",
            padding: "6px 12px",
            borderRadius: "6px",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: "6px",
            fontSize: "0.85rem"
          }}
        >
          <RefreshCw size={14} /> Retry
        </button>
      )}
    </div>
  );
}

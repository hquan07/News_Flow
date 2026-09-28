"use client";

import React from "react";
import { Share2 } from "lucide-react";
import KnowledgeGraph from "@/components/KnowledgeGraph";
import { formatDateTime } from "@/lib/formatters";

export default function NetworkView({ knowledgeGraph, updatedAt }: any) {
  return (
    <>
      <div
        className="glass-panel"
        style={{ display: "flex", flexDirection: "column" }}
      >
        <div className="panel-header">
          <div className="panel-title">
            <Share2 size={20} /> Entity Knowledge Graph
          </div>
        </div>
        <p className="chart-description">Explore the strongest relationships among the top 100 entities. Node size represents mentions; link width represents co-occurrence.</p>
        <div className="chart-meta"><span>Last 7 days</span><span>{knowledgeGraph?.nodes?.length ?? 0} entities</span><span>{knowledgeGraph?.links?.length ?? 0} relationships</span><span>Updated: {formatDateTime(updatedAt)}</span></div>
        <div style={{ flex: 1, position: "relative" }}>
          <KnowledgeGraph data={knowledgeGraph} />
        </div>
      </div>
    </>
  );
}

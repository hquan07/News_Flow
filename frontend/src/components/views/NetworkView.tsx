"use client";

import React, { useState } from "react";
import { Share2 } from "lucide-react";
import KnowledgeGraph from "@/components/KnowledgeGraph";

export default function NetworkView({ knowledgeGraph }: any) {
  return (
    <>
      <div
        className="glass-panel"
        style={{
          height: "700px",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div className="panel-header">
          <div className="panel-title">
            <Share2 size={20} /> Entity Knowledge Graph
          </div>
        </div>
        <div style={{ flex: 1, position: "relative" }}>
          <KnowledgeGraph data={knowledgeGraph} />
        </div>
      </div>
    </>
  );
}

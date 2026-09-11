"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import dynamic from "next/dynamic";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

const COLOR_MAP: Record<string, string> = {
  "PERSON": "#f97316", // orange-500
  "PER": "#f97316",
  "LOCATION": "#8b5cf6", // violet-500
  "LOC": "#8b5cf6",
  "ORGANIZATION": "#10b981", // emerald-500
  "ORG": "#10b981",
  "default": "#3b82f6" // blue-500
};

interface GraphProps {
  data: {
    nodes: any[];
    links: any[];
  };
}

export default function KnowledgeGraph({ data }: GraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const graphRef = useRef<any>(null);

  // States for highlighting
  const [selectedNode, setSelectedNode] = useState<any>(null);
  const [highlightNodes, setHighlightNodes] = useState(new Set());
  const [highlightLinks, setHighlightLinks] = useState(new Set());

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Make the graph zoom to fit after loading data and adjust forces
  useEffect(() => {
    if (graphRef.current && data.nodes.length > 0) {
      graphRef.current.d3Force('charge').strength(-400);
      graphRef.current.d3Force('link').distance(100);
      graphRef.current.d3Force('center').strength(0.05);

      setTimeout(() => {
        if (graphRef.current) {
          graphRef.current.zoomToFit(400, 50);
        }
      }, 800);
    }
  }, [data]);

  const handleNodeClick = useCallback((node: any) => {
    if (selectedNode === node) {
      // Toggle off if clicking the same node
      setSelectedNode(null);
      setHighlightNodes(new Set());
      setHighlightLinks(new Set());
      return;
    }
    
    setSelectedNode(node);
    const newHighlightNodes = new Set();
    const newHighlightLinks = new Set();

    newHighlightNodes.add(node);
    
    data.links.forEach(link => {
      const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
      const targetId = typeof link.target === 'object' ? link.target.id : link.target;
      
      if (sourceId === node.id || targetId === node.id) {
        newHighlightLinks.add(link);
        const sourceNode = typeof link.source === 'object' ? link.source : data.nodes.find(n => n.id === sourceId);
        const targetNode = typeof link.target === 'object' ? link.target : data.nodes.find(n => n.id === targetId);
        if (sourceNode) newHighlightNodes.add(sourceNode);
        if (targetNode) newHighlightNodes.add(targetNode);
      }
    });

    setHighlightNodes(newHighlightNodes);
    setHighlightLinks(newHighlightLinks);
  }, [selectedNode, data]);

  const handleBackgroundClick = useCallback(() => {
    setSelectedNode(null);
    setHighlightNodes(new Set());
    setHighlightLinks(new Set());
  }, []);

  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.name;
    const fontSize = 12 / globalScale;
    ctx.font = `${fontSize}px Inter, sans-serif`;
    
    // Determine opacity based on selection state
    const isHighlighted = highlightNodes.size === 0 || highlightNodes.has(node);
    const opacity = isHighlighted ? 1 : 0.2;
    
    // Draw node circle
    const color = COLOR_MAP[node.group?.toUpperCase()] || COLOR_MAP.default;
    // Use logarithmic scaling to prevent extremely large nodes
    const radius = Math.min(Math.max(Math.log2(node.val + 1) * 3, 3), 30);
    
    ctx.beginPath();
    ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI, false);
    
    // Convert hex color to rgba for opacity
    ctx.fillStyle = color;
    ctx.globalAlpha = opacity;
    ctx.fill();
    ctx.globalAlpha = 1; // reset
    
    // Draw text label only if highlighted
    if (isHighlighted || selectedNode) { // you might only want to show labels for highlighted nodes if something is selected
      const textWidth = ctx.measureText(label).width;
      const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2); 
      
      ctx.fillStyle = `rgba(15, 23, 42, ${isHighlighted ? 0.7 : 0.2})`;
      ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y + radius + 2, bckgDimensions[0], bckgDimensions[1]);
      
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = `rgba(248, 250, 252, ${opacity})`;
      ctx.fillText(label, node.x, node.y + radius + 2 + fontSize / 2);
    }
  }, [highlightNodes, selectedNode]);

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", minHeight: "600px", borderRadius: "12px", overflow: "hidden", border: "1px solid rgba(255,255,255,0.1)" }}>
      {data.nodes.length > 0 ? (
        <ForceGraph2D
          ref={graphRef}
          width={dimensions.width}
          height={dimensions.height}
          graphData={data}
          nodeLabel={() => ""} // disable default tooltip
          nodeCanvasObject={paintNode}
          nodeRelSize={6}
          onNodeClick={handleNodeClick}
          onBackgroundClick={handleBackgroundClick}
          linkColor={(link: any) => 
            highlightNodes.size === 0 ? "rgba(148, 163, 184, 0.4)" : 
            highlightLinks.has(link) ? "rgba(255, 255, 255, 0.8)" : "rgba(148, 163, 184, 0.05)"
          }
          linkWidth={(link: any) => 
            highlightLinks.has(link) ? Math.min(Math.max(link.weight * 0.5, 2), 6) : 
            highlightNodes.size === 0 ? Math.min(Math.max(link.weight * 0.5, 1), 5) : 1
          }
          linkDirectionalParticles={(link: any) => highlightLinks.has(link) ? 4 : 0}
          linkDirectionalParticleWidth={3}
          backgroundColor="transparent"
        />
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
          Loading network...
        </div>
      )}
    </div>
  );
}

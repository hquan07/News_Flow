"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Focus, RotateCcw, Search, ZoomIn, ZoomOut } from "lucide-react";
import EmptyState from "./ui/EmptyState";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), { ssr: false });

export interface GraphNode {
  id: string;
  name: string;
  group?: string;
  val?: number;
  x?: number;
  y?: number;
}

export interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  weight?: number;
}

interface GraphProps { data: { nodes: GraphNode[]; links: GraphLink[] } }

const COLOR_MAP: Record<string, string> = {
  PERSON: "#f97316", PER: "#f97316", LOCATION: "#8b5cf6", LOC: "#8b5cf6",
  ORGANIZATION: "#10b981", ORG: "#10b981", default: "#3b82f6",
};

const TYPE_LABELS = { PER: "Person", LOC: "Location", ORG: "Organization" };
const idOf = (value: string | GraphNode) => typeof value === "object" ? value.id : value;
const canonicalType = (value = "") => value.toUpperCase().startsWith("PER") ? "PER" : value.toUpperCase().startsWith("LOC") ? "LOC" : value.toUpperCase().startsWith("ORG") ? "ORG" : "OTHER";

export default function KnowledgeGraph({ data }: GraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 560 });
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [highlightNodeIds, setHighlightNodeIds] = useState<Set<string>>(new Set());
  const [highlightLinks, setHighlightLinks] = useState<Set<GraphLink>>(new Set());
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("ALL");

  useEffect(() => {
    if (!containerRef.current) return;
    const observer = new ResizeObserver(([entry]) => setDimensions({ width: entry.contentRect.width, height: Math.max(entry.contentRect.height, 420) }));
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  const filteredData = useMemo(() => {
    const nodes = data.nodes.filter((node) => typeFilter === "ALL" || canonicalType(node.group) === typeFilter).slice(0, 100);
    const ids = new Set(nodes.map((node) => node.id));
    return { nodes, links: data.links.filter((link) => ids.has(idOf(link.source)) && ids.has(idOf(link.target))).slice(0, 300) };
  }, [data, typeFilter]);

  const fitGraph = useCallback(() => graphRef.current?.zoomToFit(400, 50), []);

  useEffect(() => {
    if (!graphRef.current || filteredData.nodes.length === 0) return;
    graphRef.current.d3Force("charge")?.strength(-350);
    graphRef.current.d3Force("link")?.distance(90);
    const timer = window.setTimeout(fitGraph, 600);
    return () => window.clearTimeout(timer);
  }, [filteredData, fitGraph]);

  const selectNode = useCallback((node: GraphNode | null) => {
    setSelectedNode(node);
    if (!node) { setHighlightNodeIds(new Set()); setHighlightLinks(new Set()); return; }
    const nodeIds = new Set<string>([node.id]);
    const links = new Set<GraphLink>();
    filteredData.links.forEach((link) => {
      const source = idOf(link.source); const target = idOf(link.target);
      if (source === node.id || target === node.id) { links.add(link); nodeIds.add(source); nodeIds.add(target); }
    });
    setHighlightNodeIds(nodeIds); setHighlightLinks(links);
  }, [filteredData.links]);

  const focusSearch = () => {
    const needle = query.trim().toLowerCase();
    if (!needle) return;
    const node = filteredData.nodes.find((candidate) => candidate.name.toLowerCase().includes(needle));
    if (!node) return;
    selectNode(node);
    if (typeof node.x === "number" && typeof node.y === "number") { graphRef.current?.centerAt(node.x, node.y, 500); graphRef.current?.zoom(3, 500); }
  };

  const related = selectedNode ? filteredData.links.filter((link) => idOf(link.source) === selectedNode.id || idOf(link.target) === selectedNode.id).map((link) => {
    const relatedId = idOf(link.source) === selectedNode.id ? idOf(link.target) : idOf(link.source);
    return filteredData.nodes.find((node) => node.id === relatedId)?.name ?? relatedId;
  }).slice(0, 8) : [];

  const paintNode = useCallback((node: GraphNode, context: CanvasRenderingContext2D, scale: number) => {
    const x = node.x ?? 0; const y = node.y ?? 0;
    const active = highlightNodeIds.size === 0 || highlightNodeIds.has(node.id);
    const radius = Math.min(Math.max(Math.log2((node.val ?? 1) + 1) * 3, 4), 28);
    context.globalAlpha = active ? 1 : 0.15;
    context.fillStyle = COLOR_MAP[node.group?.toUpperCase() ?? "default"] ?? COLOR_MAP.default;
    context.beginPath(); context.arc(x, y, radius, 0, Math.PI * 2); context.fill(); context.globalAlpha = 1;
    if (active && (scale > 1.2 || selectedNode?.id === node.id || (node.val ?? 0) > 20)) {
      const fontSize = Math.max(10 / scale, 3); context.font = `${fontSize}px Inter, sans-serif`; context.textAlign = "center"; context.textBaseline = "top"; context.fillStyle = "#f8fafc"; context.fillText(node.name, x, y + radius + 2);
    }
  }, [highlightNodeIds, selectedNode]);

  return <>
    <div className="graph-toolbar">
      <div className="graph-controls">
        <div style={{ display: "flex" }}><input aria-label="Search entity" value={query} onChange={(event) => setQuery(event.target.value)} onKeyDown={(event) => event.key === "Enter" && focusSearch()} placeholder="Search entity…" /><button type="button" onClick={focusSearch} aria-label="Find entity"><Search size={16} /></button></div>
        <select aria-label="Filter entity type" value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value); selectNode(null); }}><option value="ALL">All types</option><option value="PER">People</option><option value="LOC">Locations</option><option value="ORG">Organizations</option></select>
        <button type="button" onClick={() => graphRef.current?.zoom((graphRef.current?.zoom() ?? 1) * 1.35, 250)} aria-label="Zoom in"><ZoomIn size={16} /></button>
        <button type="button" onClick={() => graphRef.current?.zoom((graphRef.current?.zoom() ?? 1) / 1.35, 250)} aria-label="Zoom out"><ZoomOut size={16} /></button>
        <button type="button" onClick={fitGraph}><Focus size={16} /> Fit</button>
        <button type="button" onClick={() => selectNode(null)}><RotateCcw size={16} /> Reset</button>
      </div>
      <div className="graph-legend" aria-label="Entity type legend">{Object.entries(TYPE_LABELS).map(([type, label]) => <span key={type} className="legend-dot" style={{ "--legend-color": COLOR_MAP[type] } as React.CSSProperties}>{label}</span>)}</div>
    </div>
    <div className="graph-shell">
      <div ref={containerRef} className="graph-stage" role="img" aria-label={`Knowledge graph with ${filteredData.nodes.length} entities and ${filteredData.links.length} relationships`}>
        {filteredData.nodes.length ? <ForceGraph2D ref={graphRef} width={dimensions.width} height={dimensions.height} graphData={filteredData} nodeLabel={(node: any) => `${node.name} · ${node.group ?? "Entity"} · ${node.val ?? 0} mentions`} nodeCanvasObject={paintNode as any} onNodeClick={(node: any) => selectNode(node)} onBackgroundClick={() => selectNode(null)} linkColor={(link: any) => highlightNodeIds.size === 0 ? "rgba(148,163,184,.35)" : highlightLinks.has(link) ? "rgba(255,255,255,.85)" : "rgba(148,163,184,.05)"} linkWidth={(link: any) => highlightLinks.has(link) ? 3 : Math.min(Math.max(Number(link.weight ?? 1) * 0.35, 1), 4)} backgroundColor="transparent" /> : <EmptyState message="No relationship data" />}
      </div>
      <aside className="graph-details" aria-live="polite">
        {selectedNode ? <><h3>{selectedNode.name}</h3><dl><div><dt>Type</dt><dd>{TYPE_LABELS[canonicalType(selectedNode.group) as keyof typeof TYPE_LABELS] ?? selectedNode.group ?? "Entity"}</dd></div><div><dt>Mentions</dt><dd>{Number(selectedNode.val ?? 0).toLocaleString()}</dd></div><div><dt>Connections</dt><dd>{related.length}</dd></div><div><dt>Related entities</dt><dd>{related.length ? related.join(", ") : "None"}</dd></div></dl></> : <><h3>Entity details</h3><p className="chart-description">Select a node to inspect its type, mentions and closest relationships.</p></>}
      </aside>
    </div>
    <div className="graph-data-table"><table className="data-table"><caption className="chart-description">Accessible relationship list (top 20)</caption><thead><tr><th>Source</th><th>Target</th><th>Weight</th></tr></thead><tbody>{filteredData.links.slice(0, 20).map((link, index) => <tr key={`${idOf(link.source)}-${idOf(link.target)}-${index}`}><td>{filteredData.nodes.find((node) => node.id === idOf(link.source))?.name ?? idOf(link.source)}</td><td>{filteredData.nodes.find((node) => node.id === idOf(link.target))?.name ?? idOf(link.target)}</td><td>{link.weight ?? 1}</td></tr>)}</tbody></table></div>
  </>;
}

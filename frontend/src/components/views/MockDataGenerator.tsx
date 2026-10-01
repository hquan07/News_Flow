"use client";

import { useEffect, useState } from "react";
import { Database, Plus, Loader2, CheckCircle, XCircle } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

type MockScenario = {
  id: string;
  label: string;
  description: string;
  sources: string[];
  sentiments: string[];
  like_range: [number, number];
  reply_range: [number, number];
};

export default function MockDataGenerator() {
  const [count, setCount] = useState(10);
  const [scenarios, setScenarios] = useState<MockScenario[]>([]);
  const [scenario, setScenario] = useState("balanced");
  const [scenarioError, setScenarioError] = useState("");
  const [retry, setRetry] = useState(0);
  const [isGenerating, setIsGenerating] = useState(false);
  const [resultMsg, setResultMsg] = useState("");
  const [resultOk, setResultOk] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const selected = scenarios.find((item) => item.id === scenario);

  useEffect(() => {
    let active = true;
    void apiFetch<{ scenarios: MockScenario[] }>(`${API_BASE}/admin/mock/social/scenarios`)
      .then((data) => {
        if (active) {
          setScenarios(data.scenarios);
          setScenarioError("");
        }
      })
      .catch((error) => {
        if (active) setScenarioError(error instanceof Error ? error.message : "Cannot load test scenarios");
      });
    return () => { active = false; };
  }, [retry]);

  const handleGenerate = async () => {
    if (!selected) return;
    setConfirming(false);
    setIsGenerating(true);
    setResultMsg("");
    try {
      const data = await apiFetch<{ status?: string; message?: string }>(
        `${API_BASE}/admin/mock/social?count=${count}&scenario=${encodeURIComponent(selected.id)}`,
        { method: "POST" },
      );
      if (data.status === "success") {
        setResultMsg(data.message || `+${count} posts injected`);
        setResultOk(true);
      } else {
        setResultMsg(data.message || "Error");
        setResultOk(false);
      }
    } catch (e) {
      setResultMsg(`${e}`);
      setResultOk(false);
    } finally {
      setIsGenerating(false);
      setTimeout(() => setResultMsg(""), 4000);
    }
  };

  return <div className="mock-scenario-layout">
    <div className="mock-data-generator">
      <div className="mock-header">
        <Database size={16} />
        <span>Mock Data</span>
      </div>
      <p className="mock-description">Choose a scenario and number of social posts.</p>
      <div className="mock-controls">
        <label className="sr-only" htmlFor="mock-count">Number of sample posts</label>
        <input
          id="mock-count"
          type="number"
          value={count}
          onChange={(e) => { setCount(Math.max(1, Math.min(1000, parseInt(e.target.value) || 1))); setConfirming(false); }}
          min="1"
          max="1000"
          className="mock-input"
        />
        <button
          type="button"
          onClick={() => setConfirming(true)}
          disabled={isGenerating || confirming || !selected}
          className="mock-btn"
        >
          {isGenerating ? <Loader2 size={14} className="spin" /> : <Plus size={14} />}
          {isGenerating ? "..." : "Inject"}
        </button>
      </div>
      {confirming && <div className="mock-confirmation">
        <p>Inject {count} “{selected?.label}” sample posts into the current environment? These posts will affect social analytics and alerts.</p>
        <div>
          <button type="button" className="mock-cancel-btn" onClick={() => setConfirming(false)}>Cancel</button>
          <button type="button" className="mock-btn" onClick={() => void handleGenerate()}>Confirm inject</button>
        </div>
      </div>}
      {resultMsg && (
        <div className={`mock-result ${resultOk ? "success" : "error"}`} role="status">
          {resultOk ? <CheckCircle size={12} /> : <XCircle size={12} />}
          {resultMsg}
        </div>
      )}
    </div>
    <div className="mock-scenario-preview">
      <h3>Test scenarios</h3>
      {scenarioError ? <div className="mock-scenario-error" role="alert">{scenarioError} <button type="button" onClick={() => setRetry((value) => value + 1)}>Retry</button></div>
        : scenarios.length === 0 ? <p>Loading scenarios…</p> : <>
          <div className="mock-scenario-options" aria-label="Test scenario">
            {scenarios.map((item) => <button key={item.id} type="button" className={`mock-scenario-option ${item.id === scenario ? "active" : ""}`} aria-pressed={item.id === scenario} disabled={isGenerating || confirming} onClick={() => { setScenario(item.id); setConfirming(false); }}>
              <strong>{item.label}</strong>
              <span>{item.description}</span>
            </button>)}
          </div>
          {selected && <div className="mock-preview-details">
            <strong>Preview · {count} posts</strong>
            <span>Sources: {selected.sources.slice(0, Math.min(count, selected.sources.length)).join(", ")}</span>
            <span>Sentiment: {selected.sentiments.slice(0, Math.min(count, selected.sentiments.length)).join(", ")}</span>
            <span>Likes: {selected.like_range[0].toLocaleString()}–{selected.like_range[1].toLocaleString()} · Replies: {selected.reply_range[0].toLocaleString()}–{selected.reply_range[1].toLocaleString()}</span>
            <small>Preview shows the expected ranges. Exact values are randomized when injected.</small>
          </div>}
        </>}
    </div>
  </div>;
}

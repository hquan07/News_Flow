"use client";

import { useState } from "react";
import { Database, Plus, Loader2, CheckCircle, XCircle } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

export default function MockDataGenerator() {
  const [count, setCount] = useState(10);
  const [isGenerating, setIsGenerating] = useState(false);
  const [resultMsg, setResultMsg] = useState("");
  const [resultOk, setResultOk] = useState(false);
  const [confirming, setConfirming] = useState(false);

  const handleGenerate = async () => {
    setConfirming(false);
    setIsGenerating(true);
    setResultMsg("");
    try {
      const token = localStorage.getItem("token");
      const data = await apiFetch<{ status?: string; message?: string }>(
        `${API_BASE}/admin/mock/social?count=${count}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        },
      );
      if (data.status === "success") {
        setResultMsg(`+${count} posts injected`);
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

  return (
    <div className="mock-data-generator">
      <div className="mock-header">
        <Database size={16} />
        <span>Mock Data</span>
      </div>
      <p className="mock-description">Inject sample social posts for testing</p>
      <div className="mock-controls">
        <input
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
          disabled={isGenerating || confirming}
          className="mock-btn"
        >
          {isGenerating ? <Loader2 size={14} className="spin" /> : <Plus size={14} />}
          {isGenerating ? "..." : "Inject"}
        </button>
      </div>
      {confirming && <div className="mock-confirmation">
        <p>Inject {count} sample social posts into the current environment?</p>
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
  );
}

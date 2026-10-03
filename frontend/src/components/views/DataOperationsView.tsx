"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { DatabaseBackup, GitBranch, HardDrive, Play } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

type Dataset = { dataset: string; table: string; retention_days: number; enabled: boolean; rows: number; bytes_on_disk: number };

export default function DataOperationsView({ canMutate }: { canMutate: boolean }) {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [lineage, setLineage] = useState<any>(null);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try { const result = await apiFetch<{ datasets: Dataset[] }>(`${API_BASE}/operations/retention`); setDatasets(result.datasets); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "Unable to load storage data"); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const inspect = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const id = String(new FormData(event.currentTarget).get("article_id") || "").trim();
    if (!id) return;
    try { setLineage(await apiFetch(`${API_BASE}/operations/lineage/${encodeURIComponent(id)}`)); setMessage(""); }
    catch (reason) { setMessage(reason instanceof Error ? reason.message : "Lineage unavailable"); }
  };

  const replay = async () => {
    if (!lineage || !window.confirm(`Replay ${lineage.article.article_id} through Kafka and NLP?`)) return;
    const result = await apiFetch<any>(`${API_BASE}/operations/lineage/${lineage.article.article_id}/replay`, { method: "POST" });
    setMessage(`Replay queued: ${result.dag_run_id}`);
  };

  const savePolicy = async (dataset: Dataset, changes: Partial<Dataset>) => {
    await apiFetch(`${API_BASE}/operations/retention/${dataset.dataset}`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ retention_days: changes.retention_days ?? dataset.retention_days, enabled: changes.enabled ?? dataset.enabled }),
    });
    await load();
  };

  const applyPolicy = async (dataset: Dataset) => {
    const preview = await apiFetch<any>(`${API_BASE}/operations/retention/${dataset.dataset}/preview`);
    if (!window.confirm(`Delete ${preview.rows_to_delete.toLocaleString()} rows older than ${preview.retention_days} days from ${dataset.dataset}?`)) return;
    const result = await apiFetch<any>(`${API_BASE}/operations/retention/${dataset.dataset}/apply`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true }) });
    setMessage(`Retention run queued: ${result.dag_run_id}`);
  };

  return <div className="data-operations-grid">
    {message && <p className="access-feedback operations-wide">{message}</p>}
    <section className="glass-panel lineage-panel">
      <h3><GitBranch size={18}/> Article lineage & replay</h3>
      <form onSubmit={(event) => void inspect(event)}><input name="article_id" required placeholder="Article ID"/><button>Inspect</button></form>
      {lineage && <div className="lineage-flow"><strong>{lineage.article.title}</strong>{lineage.stages.map((stage: any) => <div key={stage.stage} className={`lineage-stage ${stage.status}`}><span>{stage.stage}</span><small>{stage.status}{stage.timestamp ? ` · ${new Date(stage.timestamp).toLocaleString()}` : ""}</small></div>)}{canMutate && <button type="button" onClick={() => void replay()}><Play size={14}/> Replay pipeline</button>}</div>}
    </section>
    <section className="glass-panel retention-panel">
      <h3><HardDrive size={18}/> Retention & storage</h3>
      <p>Policies are disabled by default. Apply runs are explicitly confirmed and executed through Airflow.</p>
      {datasets.map((dataset) => <article key={dataset.dataset}><div><strong>{dataset.dataset}</strong><small>{dataset.rows.toLocaleString()} rows · {(dataset.bytes_on_disk / 1024 / 1024).toFixed(1)} MB</small></div><input type="number" min="7" max="3650" value={dataset.retention_days} disabled={!canMutate} onChange={(event) => setDatasets((current) => current.map((item) => item.dataset === dataset.dataset ? { ...item, retention_days: Number(event.target.value) } : item))}/><label><input type="checkbox" checked={dataset.enabled} disabled={!canMutate} onChange={() => void savePolicy(dataset, { enabled: !dataset.enabled })}/> Enabled</label>{canMutate && <><button onClick={() => void savePolicy(dataset, {})}>Save</button><button className="danger" disabled={!dataset.enabled} onClick={() => void applyPolicy(dataset)}><DatabaseBackup size={14}/> Apply</button></>}</article>)}
    </section>
  </div>;
}

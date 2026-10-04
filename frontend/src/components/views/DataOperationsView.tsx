"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { DatabaseBackup, GitBranch, HardDrive, Play } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

type Dataset = { dataset: string; table: string; retention_days: number; enabled: boolean; rows: number; bytes_on_disk: number };

export default function DataOperationsView({ canMutate }: { canMutate: boolean }) {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [lineage, setLineage] = useState<any>(null);
  const [message, setMessage] = useState("");
  const [dirtyDatasets, setDirtyDatasets] = useState<Record<string, boolean>>({});
  const [busyDataset, setBusyDataset] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<"save" | "apply" | null>(null);

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

  const updatePolicyDraft = (datasetName: string, changes: Partial<Dataset>) => {
    setDatasets((current) => current.map((item) => item.dataset === datasetName ? { ...item, ...changes } : item));
    setDirtyDatasets((current) => ({ ...current, [datasetName]: true }));
    setMessage("");
  };

  const savePolicy = async (dataset: Dataset) => {
    setBusyDataset(dataset.dataset);
    setBusyAction("save");
    setMessage("");
    try {
      await apiFetch(`${API_BASE}/operations/retention/${dataset.dataset}`, {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ retention_days: dataset.retention_days, enabled: dataset.enabled }),
      });
      setDirtyDatasets((current) => ({ ...current, [dataset.dataset]: false }));
      setMessage(`Saved the ${dataset.dataset} retention policy.`);
      await load();
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : `Unable to save the ${dataset.dataset} retention policy`);
    } finally {
      setBusyDataset(null);
      setBusyAction(null);
    }
  };

  const applyPolicy = async (dataset: Dataset) => {
    setBusyDataset(dataset.dataset);
    setBusyAction("apply");
    setMessage("");
    try {
      const preview = await apiFetch<any>(`${API_BASE}/operations/retention/${dataset.dataset}/preview`);
      if (!window.confirm(`Delete ${preview.rows_to_delete.toLocaleString()} rows older than ${preview.retention_days} days from ${dataset.dataset}?`)) return;
      const result = await apiFetch<any>(`${API_BASE}/operations/retention/${dataset.dataset}/apply`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirm: true }) });
      setMessage(`Retention run queued: ${result.dag_run_id}`);
    } catch (reason) {
      setMessage(reason instanceof Error ? reason.message : `Unable to apply the ${dataset.dataset} retention policy`);
    } finally {
      setBusyDataset(null);
      setBusyAction(null);
    }
  };

  return <div className="data-operations-grid">
    {message && <p className="access-feedback operations-wide" role="status" aria-live="polite">{message}</p>}
    <section className="glass-panel lineage-panel">
      <h3><GitBranch size={18}/> Article lineage & replay</h3>
      <form onSubmit={(event) => void inspect(event)}><input name="article_id" required placeholder="Article ID"/><button>Inspect</button></form>
      {lineage && <div className="lineage-flow"><strong>{lineage.article.title}</strong>{lineage.stages.map((stage: any) => <div key={stage.stage} className={`lineage-stage ${stage.status}`}><span>{stage.stage}</span><small>{stage.status}{stage.timestamp ? ` · ${new Date(stage.timestamp).toLocaleString()}` : ""}</small></div>)}{canMutate && <button type="button" onClick={() => void replay()}><Play size={14}/> Replay pipeline</button>}</div>}
    </section>
    <section className="glass-panel retention-panel">
      <h3><HardDrive size={18}/> Retention & storage</h3>
      <p>Policies are disabled by default. Apply runs are explicitly confirmed and executed through Airflow.</p>
      {!canMutate && <p className="retention-readonly">You have read-only access to retention policies.</p>}
      {datasets.map((dataset) => {
        const isDirty = Boolean(dirtyDatasets[dataset.dataset]);
        const isBusy = busyDataset === dataset.dataset;
        const hasInvalidDays = !Number.isInteger(dataset.retention_days) || dataset.retention_days < 7 || dataset.retention_days > 3650;
        return <article key={dataset.dataset}>
          <div className="retention-dataset">
            <strong>{dataset.dataset}</strong>
            <small>{dataset.rows.toLocaleString()} rows · {(dataset.bytes_on_disk / 1024 / 1024).toFixed(1)} MB</small>
            {isDirty && <small className="retention-unsaved">Unsaved changes</small>}
          </div>
          <label className="retention-days">
            <span>Days</span>
            <input
              type="number"
              min="7"
              max="3650"
              value={dataset.retention_days}
              disabled={!canMutate || isBusy}
              aria-label={`Retention days for ${dataset.dataset}`}
              onChange={(event) => updatePolicyDraft(dataset.dataset, { retention_days: Number(event.target.value) })}
            />
          </label>
          <label className="retention-toggle">
            <input
              type="checkbox"
              checked={dataset.enabled}
              disabled={!canMutate || isBusy}
              aria-label={`Enable retention for ${dataset.dataset}`}
              onChange={(event) => updatePolicyDraft(dataset.dataset, { enabled: event.target.checked })}
            />
            Enabled
          </label>
          {canMutate && <div className="retention-actions">
            <button type="button" disabled={!isDirty || hasInvalidDays || isBusy} onClick={() => void savePolicy(dataset)}>
              {isBusy && busyAction === "save" ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              className="danger"
              disabled={!dataset.enabled || isDirty || hasInvalidDays || isBusy}
              title={isDirty ? "Save changes before applying this policy" : !dataset.enabled ? "Enable and save this policy before applying it" : "Preview and apply this policy"}
              onClick={() => void applyPolicy(dataset)}
            >
              <DatabaseBackup size={14}/> {isBusy && busyAction === "apply" ? "Applying…" : "Apply"}
            </button>
          </div>}
        </article>;
      })}
    </section>
  </div>;
}

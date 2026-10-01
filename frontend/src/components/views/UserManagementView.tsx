"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { RefreshCw, ShieldCheck, UserCog } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

type ManagedUser = {
  id: string;
  email: string;
  full_name: string;
  avatar_data_url?: string | null;
  role: "user" | "analyst" | "operator" | "admin";
  is_active: boolean;
  created_at?: string;
};

type AuditLog = {
  id: string;
  action: string;
  actor_email: string;
  target_email: string;
  changes: Record<string, unknown>;
  created_at?: string;
};

const ROLES: ManagedUser["role"][] = ["user", "analyst", "operator", "admin"];
const PREVIEW_LOG_COUNT = 5;

export default function UserManagementView({ currentUserId }: { currentUserId?: string }) {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [hideAudit, setHideAudit] = useState(false);
  const [showAllAudit, setShowAllAudit] = useState(false);
  const [auditSearch, setAuditSearch] = useState("");
  const [auditDays, setAuditDays] = useState("all");
  const [auditCutoff, setAuditCutoff] = useState(0);

  const search = auditSearch.trim().toLocaleLowerCase();
  const filteredAuditLogs = auditLogs.filter((log) => {
    const timestamp = Date.parse(log.created_at || "");
    if (auditCutoff && (!Number.isFinite(timestamp) || timestamp < auditCutoff)) return false;
    if (!search) return true;
    return [log.actor_email || "Admin", log.target_email || "user", log.action, JSON.stringify(log.changes)]
      .some((value) => value.toLocaleLowerCase().includes(search));
  });
  const visibleAuditLogs = showAllAudit ? filteredAuditLogs : filteredAuditLogs.slice(0, PREVIEW_LOG_COUNT);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [userData, auditData] = await Promise.all([
        apiFetch<{ users: ManagedUser[] }>(`${API_BASE}/admin/users`),
        apiFetch<{ logs: AuditLog[] }>(`${API_BASE}/admin/audit-logs?limit=100`),
      ]);
      setUsers(userData.users ?? []);
      setAuditLogs(auditData.logs ?? []);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const updateAccess = async (user: ManagedUser, changes: Partial<Pick<ManagedUser, "role" | "is_active">>) => {
    setSavingId(user.id);
    setMessage("");
    try {
      const updated = await apiFetch<ManagedUser>(`${API_BASE}/admin/users/${user.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(changes),
      });
      setUsers((current) => current.map((item) => item.id === updated.id ? updated : item));
      const auditData = await apiFetch<{ logs: AuditLog[] }>(`${API_BASE}/admin/audit-logs?limit=100`);
      setAuditLogs(auditData.logs ?? []);
      setMessage(`Updated access for ${updated.email}. The user must sign in again to refresh permissions.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to update user access");
    } finally {
      setSavingId(null);
    }
  };

  return (
    <section className="glass-panel access-panel">
      <div className="access-panel-header">
        <div>
          <h2><UserCog size={21} /> User Access</h2>
          <p>Assign roles and disable accounts. Every access change is recorded in the audit log.</p>
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => void load()} disabled={loading}>
          <RefreshCw size={15} className={loading ? "spin" : ""} /> Refresh
        </button>
      </div>

      {message && <p className="access-feedback" role="status">{message}</p>}
      <div className="table-scroll-container" aria-busy={loading}>
        <table className="data-table access-table">
          <thead><tr><th>User</th><th>Role</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>
            {users.map((managedUser) => {
              const isSelf = managedUser.id === currentUserId;
              return (
                <tr key={managedUser.id}>
                  <td>
                    <div className="access-user">
                      <div className="access-user-avatar" aria-hidden="true">
                        {managedUser.avatar_data_url?.startsWith("data:image/jpeg;base64,")
                          ? <Image src={managedUser.avatar_data_url} alt="" width={36} height={36} unoptimized />
                          : managedUser.email.charAt(0).toUpperCase()}
                      </div>
                      <div className="access-user-details">
                        <strong>{managedUser.full_name || managedUser.email}</strong>
                        <span>{managedUser.email}{isSelf ? " · You" : ""}</span>
                      </div>
                    </div>
                  </td>
                  <td>
                    <label className="sr-only" htmlFor={`role-${managedUser.id}`}>Role for {managedUser.email}</label>
                    <select id={`role-${managedUser.id}`} value={managedUser.role} disabled={isSelf || savingId === managedUser.id} onChange={(event) => void updateAccess(managedUser, { role: event.target.value as ManagedUser["role"] })}>
                      {ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
                    </select>
                  </td>
                  <td>
                    <button type="button" className={`status-toggle ${managedUser.is_active ? "active" : "inactive"}`} disabled={isSelf || savingId === managedUser.id} onClick={() => void updateAccess(managedUser, { is_active: !managedUser.is_active })}>
                      <ShieldCheck size={14} /> {managedUser.is_active ? "Active" : "Disabled"}
                    </button>
                  </td>
                  <td>{managedUser.created_at ? new Date(managedUser.created_at).toLocaleDateString() : "—"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="audit-section">
        <div className="audit-section-heading">
          <h3>Recent access changes <span>({auditLogs.length})</span></h3>
          <button type="button" className="audit-control-button" aria-expanded={!hideAudit} aria-controls="access-audit-content" onClick={() => setHideAudit((current) => !current)}>
            {hideAudit ? "Show" : "Hide"}
          </button>
        </div>
        {!hideAudit && <div id="access-audit-content">
          <div className="audit-filters">
            <label className="sr-only" htmlFor="audit-search">Filter access changes</label>
            <input id="audit-search" type="search" value={auditSearch} onChange={(event) => { setAuditSearch(event.target.value); setShowAllAudit(false); }} placeholder="Filter by account or change" />
            <label className="sr-only" htmlFor="audit-days">Access change period</label>
            <select id="audit-days" value={auditDays} onChange={(event) => { const days = event.target.value; setAuditDays(days); setAuditCutoff(days === "all" ? 0 : Date.now() - Number(days) * 24 * 60 * 60 * 1000); setShowAllAudit(false); }}>
              <option value="all">All dates</option>
              <option value="7">Last 7 days</option>
              <option value="30">Last 30 days</option>
            </select>
          </div>
          {auditLogs.length === 0 ? <p>No access changes recorded yet.</p> : filteredAuditLogs.length === 0 ? <p>No matching access changes.</p> : <>
          <div className="audit-list">
            {visibleAuditLogs.map((log) => (
              <article key={log.id}>
                <div><strong>{log.actor_email || "Admin"}</strong> updated <strong>{log.target_email || "user"}</strong></div>
                <span>{Object.entries(log.changes).map(([key, value]) => `${key}: ${String(value)}`).join(" · ")}</span>
                <time>{log.created_at ? new Date(log.created_at).toLocaleString() : ""}</time>
              </article>
            ))}
          </div>
          {filteredAuditLogs.length > PREVIEW_LOG_COUNT && <button type="button" className="audit-control-button audit-more-button" onClick={() => setShowAllAudit((current) => !current)}>
            {showAllAudit ? "Show latest 5" : `Show all ${filteredAuditLogs.length} matching changes`}
          </button>}
          </>}
        </div>}
      </div>
    </section>
  );
}

"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, ShieldCheck, UserCog } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

type ManagedUser = {
  id: string;
  email: string;
  full_name: string;
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

export default function UserManagementView({ currentUserId }: { currentUserId?: string }) {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [userData, auditData] = await Promise.all([
        apiFetch<{ users: ManagedUser[] }>(`${API_BASE}/admin/users`),
        apiFetch<{ logs: AuditLog[] }>(`${API_BASE}/admin/audit-logs?limit=20`),
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
      const auditData = await apiFetch<{ logs: AuditLog[] }>(`${API_BASE}/admin/audit-logs?limit=20`);
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
                  <td><strong>{managedUser.full_name || managedUser.email}</strong><span>{managedUser.email}{isSelf ? " · You" : ""}</span></td>
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
        <h3>Recent access changes</h3>
        {auditLogs.length === 0 ? <p>No access changes recorded yet.</p> : (
          <div className="audit-list">
            {auditLogs.map((log) => (
              <article key={log.id}>
                <div><strong>{log.actor_email || "Admin"}</strong> updated <strong>{log.target_email || "user"}</strong></div>
                <span>{Object.entries(log.changes).map(([key, value]) => `${key}: ${String(value)}`).join(" · ")}</span>
                <time>{log.created_at ? new Date(log.created_at).toLocaleString() : ""}</time>
              </article>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

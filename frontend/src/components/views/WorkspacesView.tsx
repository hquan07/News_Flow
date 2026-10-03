"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Plus, UsersRound } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

type Member = { email: string; role: "viewer" | "editor" };
type Workspace = { id: string; name: string; owner_email: string; members: Member[] };
type SharedWatchlist = { id: string; name: string; kind: string; value: string };

export default function WorkspacesView({ currentEmail }: { currentEmail?: string }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [selected, setSelected] = useState("");
  const [watchlists, setWatchlists] = useState<SharedWatchlist[]>([]);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const items = await apiFetch<Workspace[]>(`${API_BASE}/workspaces`);
      setWorkspaces(items);
      setSelected((current) => current || items[0]?.id || "");
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load workspaces"); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!selected) { setWatchlists([]); return; }
    void apiFetch<SharedWatchlist[]>(`${API_BASE}/workspaces/${selected}/watchlists`).then(setWatchlists).catch((reason: Error) => setError(reason.message));
  }, [selected]);

  const createWorkspace = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const form = event.currentTarget; const name = String(new FormData(form).get("name") || "").trim(); if (!name) return;
    await apiFetch(`${API_BASE}/workspaces`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) }); form.reset(); await load();
  };
  const addMember = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    await apiFetch(`${API_BASE}/workspaces/${selected}/members`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email: data.get("email"), role: data.get("role") }) }); form.reset(); await load();
  };
  const addWatchlist = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    const item = await apiFetch<SharedWatchlist>(`${API_BASE}/workspaces/${selected}/watchlists`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: data.get("name"), kind: data.get("kind"), value: data.get("value") }) }); setWatchlists((current) => [item, ...current]); form.reset();
  };
  const workspace = workspaces.find((item) => item.id === selected);
  const canManageMembers = workspace?.owner_email?.toLocaleLowerCase() === currentEmail?.toLocaleLowerCase();
  const canEdit = canManageMembers || workspace?.members.some((member) => member.email.toLocaleLowerCase() === currentEmail?.toLocaleLowerCase() && member.role === "editor");

  return <div className="workspace-grid">
    {error && <div className="error-state workspace-wide">{error}</div>}
    <aside className="glass-panel workspace-list"><h3><UsersRound size={18}/> Team workspaces</h3><form onSubmit={(event) => void createWorkspace(event)}><input name="name" required placeholder="New workspace"/><button aria-label="Create workspace"><Plus size={15}/></button></form>{workspaces.map((item) => <button type="button" className={selected === item.id ? "active" : ""} key={item.id} onClick={() => setSelected(item.id)}>{item.name}<small>{item.members.length + 1} members</small></button>)}</aside>
    <section className="glass-panel workspace-detail">{workspace ? <><div className="workspace-heading"><div><h3>{workspace.name}</h3><span>Owner: {workspace.owner_email}</span></div></div><div className="workspace-members"><strong>Members</strong><span>{workspace.owner_email} · owner</span>{workspace.members.map((member) => <span key={member.email}>{member.email} · {member.role}</span>)}</div>{canManageMembers && <form onSubmit={(event) => void addMember(event)}><input name="email" type="email" required placeholder="Member email"/><select name="role"><option value="viewer">Viewer</option><option value="editor">Editor</option></select><button>Add member</button></form>}<div className="workspace-watchlists"><strong>Shared watchlists</strong>{watchlists.map((item) => <article key={item.id}><span>{item.name}</span><small>{item.kind} · {item.value}</small></article>)}{!watchlists.length && <p>No shared watchlists yet.</p>}</div>{canEdit && <form onSubmit={(event) => void addWatchlist(event)}><input name="name" required placeholder="Watchlist name"/><input name="value" required placeholder="Keyword or entity"/><select name="kind"><option value="keyword">Keyword</option><option value="entity">Entity</option><option value="source">Source</option><option value="topic">Topic</option></select><button>Share</button></form>}</> : <p>Select or create a workspace.</p>}</section>
  </div>;
}

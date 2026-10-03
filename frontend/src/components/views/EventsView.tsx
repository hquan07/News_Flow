"use client";

import { useCallback, useEffect, useState } from "react";
import { ExternalLink, MessageCircle, RadioTower, ShieldAlert } from "lucide-react";
import { API_BASE, apiFetch } from "@/lib/api";

type EventArticle = { article_id: string; title: string; url: string; source: string; published_at?: string };
type NewsEvent = { event_id: string; title: string; article_count: number; duplicate_count: number; sources: string[]; articles: EventArticle[] };
type CrisisRoom = { id: string; event_id: string; name: string; notes: string; status: string; event_snapshot: NewsEvent };

export default function EventsView({ onAsk }: { onAsk: (event: NewsEvent) => void }) {
  const [events, setEvents] = useState<NewsEvent[]>([]);
  const [rooms, setRooms] = useState<CrisisRoom[]>([]);
  const [days, setDays] = useState(7);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState("");

  const load = useCallback(async () => {
    try {
      const [eventResult, roomResult] = await Promise.all([
        apiFetch<{ events: NewsEvent[] }>(`${API_BASE}/events?days=${days}`),
        apiFetch<CrisisRoom[]>(`${API_BASE}/events/rooms/mine`),
      ]);
      setEvents(eventResult.events);
      setRooms(roomResult);
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load events"); }
  }, [days]);

  useEffect(() => { void load(); }, [load]);

  const createRoom = async (event: NewsEvent) => {
    setBusyId(event.event_id);
    try {
      await apiFetch(`${API_BASE}/events/rooms`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ event_id: event.event_id, name: event.title, notes: "" }),
      });
      await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to create room"); }
    finally { setBusyId(""); }
  };

  const setRoomStatus = async (room: CrisisRoom, status: string) => {
    await apiFetch(`${API_BASE}/events/rooms/${room.id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }),
    });
    await load();
  };

  return <div className="events-workspace">
    <section className="glass-panel events-toolbar">
      <div><h3><RadioTower size={19} /> Event intelligence</h3><p>Related coverage is grouped by title similarity; near-duplicates are marked inside each cluster.</p></div>
      <label>Window<select value={days} onChange={(event) => setDays(Number(event.target.value))}><option value={1}>24 hours</option><option value={7}>7 days</option><option value={30}>30 days</option></select></label>
    </section>
    {error && <div className="error-state">{error}</div>}
    {rooms.length > 0 && <section className="glass-panel crisis-room-list">
      <div className="panel-title"><ShieldAlert size={19} /> Crisis rooms</div>
      {rooms.map((room) => <article key={room.id}>
        <div><strong>{room.name}</strong><small>{room.event_snapshot.article_count} articles · {room.event_snapshot.sources.join(", ")}</small></div>
        <select value={room.status} onChange={(event) => void setRoomStatus(room, event.target.value)}><option value="monitoring">Monitoring</option><option value="active">Active</option><option value="resolved">Resolved</option></select>
        <button type="button" onClick={() => onAsk(room.event_snapshot)}><MessageCircle size={15} /> Ask</button>
      </article>)}
    </section>}
    <div className="event-card-grid">
      {events.map((event) => {
        const hasRoom = rooms.some((room) => room.event_id === event.event_id);
        return <article className="glass-panel event-card" key={event.event_id}>
          <div className="event-card-heading"><div><span>{event.article_count} articles · {event.sources.length} sources</span><h3>{event.title}</h3></div><span className="duplicate-badge">{event.duplicate_count} near-duplicates</span></div>
          <div className="event-sources">{event.sources.map((source) => <span key={source}>{source}</span>)}</div>
          <ol>{event.articles.slice(0, 5).map((article) => <li key={article.article_id}><a href={article.url} target="_blank" rel="noreferrer">{article.title} <ExternalLink size={12} /></a><small>{article.source}</small></li>)}</ol>
          <div className="event-actions"><button type="button" onClick={() => onAsk(event)}><MessageCircle size={15} /> Ask assistant</button><button type="button" disabled={hasRoom || busyId === event.event_id} onClick={() => void createRoom(event)}>{hasRoom ? "Room created" : "Create crisis room"}</button></div>
        </article>;
      })}
      {!events.length && !error && <div className="glass-panel detail-empty-copy">No multi-source event clusters found in this window.</div>}
    </div>
  </div>;
}

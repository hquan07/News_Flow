"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { API_BASE, apiFetch } from "@/lib/api";

type ChatSource = {
  article_id: string;
  title: string;
  url: string;
  source: string;
};
type ChatChart = {
  type: "bar";
  title: string;
  unit: string;
  points: { label: string; value: number }[];
};
type ChatMessage = {
  id?: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  chart?: ChatChart | null;
  queried_at?: string | null;
};
type Conversation = { id: string; title: string };
type ChatResponse = {
  conversation_id: string;
  answer: string;
  sources: ChatSource[];
  chart: ChatChart | null;
  queried_at: string | null;
};

const suggestions = [
  "Từ khóa nào thịnh hành hôm nay?",
  "So sánh nguồn VnExpress và Tuổi Trẻ",
  "Thực thể nào xuất hiện nhiều trong 7 ngày qua?",
];

export default function ChatView() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [timeRange, setTimeRange] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    void apiFetch<Conversation[]>(`${API_BASE}/chat/conversations`)
      .then((items) => { if (live) setConversations(items); })
      .catch((cause: Error) => { if (live) setError(cause.message); });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    if (!activeId) {
      setHistoryLoading(false);
      return;
    }
    let live = true;
    setHistoryLoading(true);
    void apiFetch<{ messages: ChatMessage[] }>(`${API_BASE}/chat/conversations/${activeId}`)
      .then((detail) => { if (live) setMessages(detail.messages); })
      .catch((cause: Error) => { if (live) setError(cause.message); })
      .finally(() => { if (live) setHistoryLoading(false); });
    return () => { live = false; };
  }, [activeId]);

  async function send(message: string) {
    const text = message.trim();
    if (!text || loading || historyLoading) return;
    setLoading(true);
    setError(null);
    try {
      const response = await apiFetch<ChatResponse>(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation_id: activeId,
          ...(timeRange ? { time_range: timeRange } : {}),
        }),
      });
      setMessages((current) => [
        ...current,
        { role: "user", content: text },
        { role: "assistant", content: response.answer, sources: response.sources, chart: response.chart, queried_at: response.queried_at },
      ]);
      setQuestion("");
      if (!activeId) {
        setActiveId(response.conversation_id);
        setConversations((current) => [
          { id: response.conversation_id, title: text.slice(0, 120) }, ...current,
        ]);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không gửi được câu hỏi.");
    } finally {
      setLoading(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(question);
  }

  return (
    <section className="chat-view" aria-label="NewsPulse chatbot">
      <div className="chat-sidebar glass-panel">
        <div className="chat-sidebar-heading">
          <h2>Hội thoại</h2>
          <button type="button" onClick={() => { setActiveId(null); setMessages([]); setError(null); }} disabled={loading}>+ Mới</button>
        </div>
        <div className="chat-conversation-list">
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              type="button"
              className={activeId === conversation.id ? "active" : ""}
              onClick={() => { setMessages([]); setError(null); setActiveId(conversation.id); }}
              disabled={loading}
              title={conversation.title}
            >
              {conversation.title}
            </button>
          ))}
          {conversations.length === 0 && <p>Chưa có hội thoại.</p>}
        </div>
      </div>
      <div className="chat-main glass-panel">
        <div className="chat-header">
          <div>
            <h2>NewsPulse Assistant</h2>
            <p>Hỏi về bài viết, từ khóa, cảm xúc, thực thể và nguồn tin.</p>
          </div>
          <select aria-label="Khoảng thời gian" value={timeRange} onChange={(event) => setTimeRange(event.target.value)} disabled={loading}>
            <option value="">Theo câu hỏi</option>
            <option value="today">24 giờ qua</option>
            <option value="7d">7 ngày qua</option>
            <option value="30d">30 ngày qua</option>
          </select>
        </div>
        <div className="chat-messages" aria-live="polite">
          {messages.length === 0 && (
            <div className="chat-empty">
              <p>Bắt đầu với một câu hỏi:</p>
              <div className="chat-suggestions">
                {suggestions.map((suggestion) => (
                  <button key={suggestion} type="button" onClick={() => void send(suggestion)} disabled={loading}>{suggestion}</button>
                ))}
              </div>
            </div>
          )}
          {messages.map((message, index) => (
            <div key={message.id ?? `${index}-${message.role}`} className={`chat-message ${message.role}`}>
              <span className="chat-speaker">{message.role === "assistant" ? "NewsPulse" : "Bạn"}</span>
              <p>{message.content}</p>
              {message.queried_at && (
                <small className="chat-query-time">
                  Truy vấn lúc {new Date(message.queried_at).toLocaleString("vi-VN")}
                </small>
              )}
              {message.chart && message.chart.points.length > 0 && (
                <div className="chat-chart" role="img" aria-label={`${message.chart.title}; đơn vị ${message.chart.unit}`}>
                  <h3>{message.chart.title}</h3>
                  <ResponsiveContainer width="100%" height={220}>
                    <BarChart data={message.chart.points} margin={{ top: 8, right: 12, left: 0, bottom: 40 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis dataKey="label" angle={-25} textAnchor="end" interval={0} height={56} tick={{ fill: "#cbd5e1", fontSize: 11 }} />
                      <YAxis allowDecimals={false} tick={{ fill: "#cbd5e1", fontSize: 11 }} />
                      <Tooltip />
                      <Bar dataKey="value" fill="#60a5fa" name={message.chart.unit} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              {!!message.sources?.length && (
                <div className="chat-sources">
                  <span>Nguồn bài viết</span>
                  {message.sources.map((source) => (
                    <a key={source.article_id} href={source.url} target="_blank" rel="noopener noreferrer">{source.title} · {source.source}</a>
                  ))}
                </div>
              )}
            </div>
          ))}
          {historyLoading && <p className="chat-loading">Đang tải hội thoại…</p>}
          {loading && <p className="chat-loading">Đang truy vấn dữ liệu…</p>}
        </div>
        {error && <p className="chat-error" role="alert">{error}</p>}
        <form className="chat-form" onSubmit={submit}>
          <label htmlFor="chat-question" className="chat-visually-hidden">Câu hỏi</label>
          <input id="chat-question" value={question} onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ví dụ: So sánh nguồn VnExpress và Tuổi Trẻ" maxLength={2000} disabled={loading || historyLoading} />
          <button type="submit" disabled={loading || historyLoading || !question.trim()}>Gửi</button>
        </form>
      </div>
    </section>
  );
}

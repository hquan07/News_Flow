"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Trash2, X } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { API_BASE, apiFetch } from "@/lib/api";
import { hasPermission, readCachedUser, type CachedUser } from "@/lib/auth-storage";

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
type ActionType = "acknowledge_alert" | "trigger_crawler" | "generate_report";
type ActionPreview = {
  action_id: string;
  confirmation_token: string;
  summary: string;
  expires_at: string;
};
type ActionResult = {
  status: string;
  action: ActionType;
  result: { download_url?: string; row_count?: number; dag_run_id?: string; alert_id?: string };
};

const crawlerNames = ["vnexpress", "tuoitre", "thanhnien", "tienphong", "dantri", "laodong", "voz_forum", "reddit_vn", "youtube_comments"];

const suggestions = [
  "Từ khóa nào thịnh hành hôm nay?",
  "So sánh nguồn VnExpress và Tuổi Trẻ",
  "Thực thể nào xuất hiện nhiều trong 7 ngày qua?",
];

export default function ChatView({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [timeRange, setTimeRange] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const questionRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<CachedUser | null>(null);
  const [action, setAction] = useState<ActionType>("generate_report");
  const [actionTarget, setActionTarget] = useState("");
  const [actionSource, setActionSource] = useState("");
  const [actionRange, setActionRange] = useState("7d");
  const [actionPreview, setActionPreview] = useState<ActionPreview | null>(null);
  const [actionResult, setActionResult] = useState<ActionResult | null>(null);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => { setCurrentUser(readCachedUser()); }, []);

  useEffect(() => {
    if (open) questionRef.current?.focus();
  }, [open]);

  const availableActions: { value: ActionType; label: string }[] = [
    ...(hasPermission(currentUser, "reports.export") ? [{ value: "generate_report" as ActionType, label: "Tạo báo cáo" }] : []),
    ...(hasPermission(currentUser, "alerts.manage") ? [{ value: "acknowledge_alert" as ActionType, label: "Ghi nhận cảnh báo" }] : []),
    ...(hasPermission(currentUser, "crawler.run") ? [{ value: "trigger_crawler" as ActionType, label: "Chạy crawler" }] : []),
  ];

  function chooseAction(next: ActionType) {
    setAction(next);
    setActionTarget("");
    setActionPreview(null);
    setActionResult(null);
    setActionError(null);
  }

  async function previewControlledAction() {
    setActionBusy(true);
    setActionError(null);
    setActionPreview(null);
    setActionResult(null);
    try {
      const body = action === "acknowledge_alert"
        ? { action, alert_id: actionTarget.trim() }
        : action === "trigger_crawler"
          ? { action, spider_name: actionTarget }
          : { action, time_range: actionRange, ...(actionSource.trim() ? { source: actionSource.trim() } : {}) };
      const preview = await apiFetch<ActionPreview>(`${API_BASE}/chat/actions/preview`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      });
      setActionPreview(preview);
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Không tạo được bản xem trước.");
    } finally {
      setActionBusy(false);
    }
  }

  async function confirmControlledAction() {
    if (!actionPreview) return;
    setActionBusy(true);
    setActionError(null);
    try {
      const outcome = await apiFetch<ActionResult>(`${API_BASE}/chat/actions/confirm`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action_id: actionPreview.action_id,
          confirmation_token: actionPreview.confirmation_token,
          confirm: true,
        }),
      });
      setActionPreview(null);
      setActionResult(outcome);
    } catch (cause) {
      try {
        const status = await apiFetch<ActionResult>(`${API_BASE}/chat/actions/${actionPreview.action_id}`);
        if (status.status === "succeeded") {
          setActionResult(status);
        } else {
          setActionError(`Trạng thái hành động: ${status.status}. Kiểm tra hệ thống đích trước khi tạo yêu cầu mới.`);
        }
      } catch {
        setActionError(cause instanceof Error ? cause.message : "Chưa xác định được trạng thái; kiểm tra trước khi thử lại.");
      }
      setActionPreview(null);
    } finally {
      setActionBusy(false);
    }
  }

  async function downloadReport(path: string) {
    setActionError(null);
    try {
      const token = localStorage.getItem("token");
      const downloadUrl = path.startsWith("/api/v1/") ? `${API_BASE}${path.slice("/api/v1".length)}` : path;
      const response = await fetch(downloadUrl, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
      if (!response.ok) throw new Error(`Không tải được báo cáo (HTTP ${response.status}).`);
      const objectUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = "newspulse-report.csv";
      link.click();
      URL.revokeObjectURL(objectUrl);
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Không tải được báo cáo.");
    }
  }

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
    if (!text || loading || historyLoading || deletingId) return;
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

  async function deleteConversation(conversation: Conversation) {
    if (loading || historyLoading || deletingId) return;
    if (!window.confirm(`Xóa hội thoại “${conversation.title}” và toàn bộ tin nhắn? Hành động này không thể hoàn tác.`)) return;
    setDeletingId(conversation.id);
    setError(null);
    try {
      await apiFetch<void>(`${API_BASE}/chat/conversations/${encodeURIComponent(conversation.id)}`, { method: "DELETE" });
      setConversations((current) => current.filter((item) => item.id !== conversation.id));
      if (activeId === conversation.id) {
        setActiveId(null);
        setMessages([]);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không xóa được hội thoại.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <section className="chat-view" aria-label="NewsPulse chatbot">
      <div className="chat-sidebar glass-panel">
        <div className="chat-sidebar-heading">
          <h2>Hội thoại</h2>
          <button type="button" onClick={() => { setActiveId(null); setMessages([]); setError(null); }} disabled={loading || !!deletingId}>+ Mới</button>
        </div>
        <div className="chat-conversation-list">
          {conversations.map((conversation) => (
            <div className="chat-conversation-row" key={conversation.id}>
              <button
                type="button"
                className={`chat-conversation-open ${activeId === conversation.id ? "active" : ""}`}
                onClick={() => { setMessages([]); setError(null); setActiveId(conversation.id); }}
                disabled={loading || !!deletingId}
                title={conversation.title}
              >
                {conversation.title}
              </button>
              <button type="button" className="chat-conversation-delete"
                onClick={() => void deleteConversation(conversation)}
                disabled={loading || historyLoading || !!deletingId}
                aria-label={`Xóa hội thoại ${conversation.title}`}
                title={`Xóa hội thoại ${conversation.title}`}>
                <Trash2 size={16} aria-hidden="true" />
              </button>
            </div>
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
          <div className="chat-header-controls">
            <select aria-label="Khoảng thời gian" value={timeRange} onChange={(event) => setTimeRange(event.target.value)} disabled={loading}>
              <option value="">Theo câu hỏi</option>
              <option value="today">24 giờ qua</option>
              <option value="7d">7 ngày qua</option>
              <option value="30d">30 ngày qua</option>
            </select>
            <button type="button" className="chat-close-button" onClick={onClose} aria-label="Đóng Chat Assistant" title="Đóng Chat Assistant">
              <X size={18} aria-hidden="true" />
            </button>
          </div>
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
        {availableActions.length > 0 && (
          <section className="chat-action-panel" aria-label="Hành động có xác nhận">
            <h3>Hành động có xác nhận</h3>
            <p>Câu chat không tự thực hiện hành động. Hãy xem tác động và xác nhận ở đây.</p>
            <div className="chat-action-controls">
              <label>
                Loại hành động
                <select value={availableActions.some((item) => item.value === action) ? action : availableActions[0].value}
                  onChange={(event) => chooseAction(event.target.value as ActionType)} disabled={actionBusy || !!actionPreview}>
                  {availableActions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
              {action === "acknowledge_alert" && (
                <label>ID cảnh báo
                  <input value={actionTarget} onChange={(event) => { setActionTarget(event.target.value); setActionPreview(null); }}
                    placeholder="volume:YYYYMMDDHH" disabled={actionBusy || !!actionPreview} maxLength={80} />
                </label>
              )}
              {action === "trigger_crawler" && (
                <label>Crawler
                  <select value={actionTarget} onChange={(event) => { setActionTarget(event.target.value); setActionPreview(null); }} disabled={actionBusy || !!actionPreview}>
                    <option value="">Chọn crawler</option>
                    {crawlerNames.map((name) => <option key={name} value={name}>{name}</option>)}
                  </select>
                </label>
              )}
              {action === "generate_report" && (
                <>
                  <label>Khoảng thời gian
                    <select value={actionRange} onChange={(event) => { setActionRange(event.target.value); setActionPreview(null); }} disabled={actionBusy || !!actionPreview}>
                      <option value="today">24 giờ qua</option><option value="7d">7 ngày</option><option value="30d">30 ngày</option>
                    </select>
                  </label>
                  <label>Nguồn (tùy chọn)
                    <input value={actionSource} onChange={(event) => { setActionSource(event.target.value); setActionPreview(null); }} disabled={actionBusy || !!actionPreview} maxLength={80} />
                  </label>
                </>
              )}
              {!actionPreview && <button type="button" onClick={() => void previewControlledAction()}
                disabled={actionBusy || (action !== "generate_report" && !actionTarget.trim())}>Xem tác động</button>}
            </div>
            {actionPreview && (
              <div className="chat-action-preview">
                <p>{actionPreview.summary}</p>
                <small>Hết hạn: {new Date(actionPreview.expires_at).toLocaleString("vi-VN")}</small>
                <div>
                  <button type="button" onClick={() => void confirmControlledAction()} disabled={actionBusy}>Xác nhận thực hiện</button>
                  <button type="button" onClick={() => setActionPreview(null)} disabled={actionBusy}>Hủy</button>
                </div>
              </div>
            )}
            {actionResult && (
              <div className="chat-action-result" role="status">
                Đã thực hiện: {actionResult.action === "generate_report" ? `${actionResult.result.row_count ?? 0} dòng báo cáo` : actionResult.action === "trigger_crawler" ? `DAG run ${actionResult.result.dag_run_id}` : `cảnh báo ${actionResult.result.alert_id}`}.
                {actionResult.result.download_url && <button type="button" onClick={() => void downloadReport(actionResult.result.download_url!)}>Tải CSV</button>}
              </div>
            )}
            {actionError && <p className="chat-error" role="alert">{actionError}</p>}
          </section>
        )}
        <form className="chat-form" onSubmit={submit}>
          <label htmlFor="chat-question" className="chat-visually-hidden">Câu hỏi</label>
          <input id="chat-question" ref={questionRef} value={question} onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ví dụ: So sánh nguồn VnExpress và Tuổi Trẻ" maxLength={2000} disabled={loading || historyLoading || !!deletingId} />
          <button type="submit" disabled={loading || historyLoading || !!deletingId || !question.trim()}>Gửi</button>
        </form>
      </div>
    </section>
  );
}

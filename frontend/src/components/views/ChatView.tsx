"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { ChevronDown, ChevronRight, Folder, MoreHorizontal, Pencil, SquarePen, Trash2, X } from "lucide-react";
import { createPortal } from "react-dom";
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
type Conversation = { id: string; title: string; project_id: string | null };
type Project = { id: string; title: string };
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
  const [projectConversations, setProjectConversations] = useState<Record<string, Conversation[]>>({});
  const [expandedProjectIds, setExpandedProjectIds] = useState<Set<string>>(new Set());
  const [listRevision, setListRevision] = useState(0);
  const [projects, setProjects] = useState<Project[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [selectedProject, setSelectedProject] = useState("all");
  const [chatSearch, setChatSearch] = useState("");
  const [projectEditor, setProjectEditor] = useState<{ id: string | null; title: string } | null>(null);
  const [projectMenuId, setProjectMenuId] = useState<string | null>(null);
  const [projectBusy, setProjectBusy] = useState(false);
  const [movingId, setMovingId] = useState<string | null>(null);
  const [draggedConversationId, setDraggedConversationId] = useState<string | null>(null);
  const [dropProjectId, setDropProjectId] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [question, setQuestion] = useState("");
  const [timeRange, setTimeRange] = useState("");
  const [loading, setLoading] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<{
    conversation: Conversation;
    x: number;
    y: number;
    trigger: HTMLButtonElement;
  } | null>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);
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

  const visibleConversations = conversations.filter((conversation) =>
    conversation.title.toLocaleLowerCase("vi").includes(chatSearch.trim().toLocaleLowerCase("vi"))
  );
  const contextConversation = contextMenu?.conversation ?? null;

  useEffect(() => { setCurrentUser(readCachedUser()); }, []);

  useEffect(() => {
    if (open) questionRef.current?.focus();
    else setContextMenu(null);
  }, [open]);

  useEffect(() => {
    if (!contextMenu) return;
    contextMenuRef.current?.querySelector("button")?.focus();
    const closeOnOutside = (event: PointerEvent) => {
      if (!contextMenuRef.current?.contains(event.target as Node)) setContextMenu(null);
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setContextMenu(null);
        contextMenu.trigger.focus();
      }
    };
    document.addEventListener("pointerdown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [contextMenu]);

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
    void apiFetch<Project[]>(`${API_BASE}/chat/projects`)
      .then((items) => {
        if (live) {
          setProjects(items);
          setExpandedProjectIds(new Set(items.slice(0, 3).map((item) => item.id)));
        }
      })
      .catch((cause: Error) => { if (live) setError(cause.message); });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    let live = true;
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({ limit: "100" });
      if (chatSearch.trim()) params.set("q", chatSearch.trim());
      setListLoading(true);
      setProjectConversations({});
      void apiFetch<Conversation[]>(`${API_BASE}/chat/conversations?${params}`)
        .then((items) => { if (live) setConversations(items); })
        .catch((cause: Error) => { if (live) setError(cause.message); })
        .finally(() => { if (live) setListLoading(false); });
      for (const projectId of expandedProjectIds) {
        const projectParams = new URLSearchParams(params);
        projectParams.set("project_id", projectId);
        void apiFetch<Conversation[]>(`${API_BASE}/chat/conversations?${projectParams}`)
          .then((items) => { if (live) setProjectConversations((current) => ({ ...current, [projectId]: items })); })
          .catch((cause: Error) => { if (live) setError(cause.message); });
      }
    }, chatSearch ? 200 : 0);
    return () => { live = false; window.clearTimeout(timer); };
  }, [expandedProjectIds, chatSearch, listRevision]);

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
          ...(!activeId && selectedProject !== "all" && selectedProject !== "unassigned"
            ? { project_id: selectedProject } : {}),
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
        setChatSearch("");
        setActiveId(response.conversation_id);
        setConversations((current) => [
          { id: response.conversation_id, title: text.slice(0, 120),
            project_id: selectedProject !== "all" && selectedProject !== "unassigned" ? selectedProject : null }, ...current,
        ]);
        setListRevision((current) => current + 1);
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

  function chooseProject(projectId: string) {
    if (loading || historyLoading || projectBusy || movingId) return;
    setSelectedProject(projectId);
    setActiveId(null);
    setMessages([]);
    setError(null);
    setContextMenu(null);
    setProjectMenuId(null);
  }

  function toggleProject(projectId: string) {
    if (loading || historyLoading || projectBusy || movingId) return;
    const wasExpanded = expandedProjectIds.has(projectId);
    setExpandedProjectIds((current) => {
      const next = new Set(current);
      if (next.has(projectId)) next.delete(projectId);
      else next.add(projectId);
      return next;
    });
    chooseProject(wasExpanded ? "all" : projectId);
  }

  async function saveProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectEditor || projectBusy) return;
    const title = projectEditor.title.trim();
    if (!title) {
      setError("Tên Project không được để trống.");
      return;
    }
    setProjectBusy(true);
    setError(null);
    try {
      const project = projectEditor.id
        ? await apiFetch<Project>(`${API_BASE}/chat/projects/${encodeURIComponent(projectEditor.id)}`, {
            method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }),
          })
        : await apiFetch<Project>(`${API_BASE}/chat/projects`, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }),
          });
      setProjects((current) => projectEditor.id
        ? current.map((item) => item.id === project.id ? project : item)
        : [...current, project]);
      if (!projectEditor.id) {
        setSelectedProject(project.id);
        setExpandedProjectIds((current) => new Set(current).add(project.id));
        setActiveId(null);
        setMessages([]);
        setChatSearch("");
      }
      setProjectEditor(null);
      setProjectMenuId(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không lưu được Project.");
    } finally {
      setProjectBusy(false);
    }
  }

  async function deleteProject(project: Project) {
    if (projectBusy || loading || historyLoading || movingId) return;
    setProjectMenuId(null);
    if (!window.confirm(`Xóa Project “${project.title}”? Các hội thoại sẽ chuyển về “Chưa phân loại” và không bị xóa.`)) return;
    setProjectBusy(true);
    setError(null);
    try {
      await apiFetch<void>(`${API_BASE}/chat/projects/${encodeURIComponent(project.id)}`, { method: "DELETE" });
      setProjects((current) => current.filter((item) => item.id !== project.id));
      setConversations((current) => current.map((item) => item.project_id === project.id
        ? { ...item, project_id: null } : item));
      setExpandedProjectIds((current) => {
        const next = new Set(current);
        next.delete(project.id);
        return next;
      });
      if (selectedProject === project.id) setSelectedProject("all");
      if (projectEditor?.id === project.id) setProjectEditor(null);
      setListRevision((current) => current + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không xóa được Project.");
    } finally {
      setProjectBusy(false);
    }
  }

  async function moveConversation(conversation: Conversation, projectId: string | null) {
    if (movingId || loading || historyLoading || projectBusy) return;
    setContextMenu(null);
    setMovingId(conversation.id);
    setError(null);
    try {
      const updated = await apiFetch<Conversation>(
        `${API_BASE}/chat/conversations/${encodeURIComponent(conversation.id)}/project`,
        { method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project_id: projectId }) },
      );
      setConversations((current) => current.map((item) => item.id === updated.id ? updated : item));
      setListRevision((current) => current + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Không chuyển được hội thoại.");
    } finally {
      setMovingId(null);
    }
  }

  function endConversationDrag() {
    setDraggedConversationId(null);
    setDropProjectId(null);
  }

  function showContextMenu(conversation: Conversation, x: number, y: number, trigger: HTMLButtonElement) {
    if (loading || historyLoading || deletingId || movingId || projectBusy) return;
    const menuHeight = Math.min(420, 170 + projects.length * 44);
    setContextMenu({
      conversation,
      x: Math.max(8, Math.min(x, window.innerWidth - 228)),
      y: Math.max(8, Math.min(y, window.innerHeight - menuHeight - 8)),
      trigger,
    });
  }

  async function deleteConversation(conversation: Conversation) {
    if (loading || historyLoading || deletingId || movingId || projectBusy) return;
    setContextMenu(null);
    if (!window.confirm(`Xóa hội thoại “${conversation.title}” và toàn bộ tin nhắn? Hành động này không thể hoàn tác.`)) return;
    setDeletingId(conversation.id);
    setError(null);
    try {
      await apiFetch<void>(`${API_BASE}/chat/conversations/${encodeURIComponent(conversation.id)}`, { method: "DELETE" });
      setConversations((current) => current.filter((item) => item.id !== conversation.id));
      setListRevision((current) => current + 1);
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

  function renderConversation(conversation: Conversation) {
    return (
      <div className={`chat-conversation-row ${draggedConversationId === conversation.id ? "dragging" : ""}`}
        key={conversation.id}
        draggable={!conversation.project_id && !loading && !historyLoading && !deletingId && !movingId && !projectBusy}
        onDragStart={(event) => {
          if (conversation.project_id) { event.preventDefault(); return; }
          setContextMenu(null);
          setDraggedConversationId(conversation.id);
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("text/plain", conversation.id);
        }}
        onDragEnd={endConversationDrag}>
        <button type="button" className={`chat-conversation-open ${activeId === conversation.id ? "active" : ""}`}
          onClick={() => { setContextMenu(null); setMessages([]); setError(null); setActiveId(conversation.id); }}
          onContextMenu={(event) => {
            event.preventDefault();
            showContextMenu(conversation, event.clientX, event.clientY, event.currentTarget);
          }}
          onKeyDown={(event) => {
            if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
              event.preventDefault();
              const rect = event.currentTarget.getBoundingClientRect();
              showContextMenu(conversation, rect.left + 12, rect.bottom, event.currentTarget);
            }
          }}
          disabled={loading || !!deletingId || !!movingId || projectBusy}
          aria-haspopup="menu"
          aria-expanded={contextMenu?.conversation.id === conversation.id}
          title={`${conversation.title} — ${conversation.project_id ? "nhấp chuột phải để mở tùy chọn" : "kéo vào Project hoặc nhấp chuột phải để mở tùy chọn"}`}>
          {conversation.title}
        </button>
        <button type="button" className="chat-conversation-options"
          onClick={(event) => {
            const rect = event.currentTarget.getBoundingClientRect();
            showContextMenu(conversation, rect.right, rect.bottom, event.currentTarget);
          }}
          disabled={loading || historyLoading || !!deletingId || !!movingId || projectBusy}
          aria-label={`Tùy chọn hội thoại ${conversation.title}`}
          aria-haspopup="menu" aria-expanded={contextMenu?.conversation.id === conversation.id}
          title={`Tùy chọn hội thoại ${conversation.title}`}>
          <MoreHorizontal size={18} aria-hidden="true" />
        </button>
      </div>
    );
  }

  return (
    <section className="chat-view" aria-label="NewsPulse chatbot">
      <div className="chat-sidebar chat-sidebar-tree glass-panel">
        <button type="button" className="chat-new-chat" onClick={() => {
          chooseProject("all");
          setChatSearch("");
          questionRef.current?.focus();
        }} disabled={loading || historyLoading || !!deletingId || !!movingId || projectBusy}>
          <SquarePen size={17} aria-hidden="true" /> New chat
        </button>
        <label htmlFor="chat-search" className="chat-visually-hidden">Tìm hội thoại</label>
        <input id="chat-search" className="chat-search" value={chatSearch} maxLength={120}
          onChange={(event) => setChatSearch(event.target.value)} placeholder="Tìm hội thoại..." />
        <div className="chat-projects">
          <div className="chat-project-heading">
            <h3>Projects</h3>
            <button type="button" onClick={() => { setProjectEditor({ id: null, title: "" }); setProjectMenuId(null); }}
              disabled={projectBusy || projects.length >= 100} aria-label="Tạo Project">+ Mới</button>
          </div>
          {projects.map((project) => (
            <div className={`chat-project-row ${draggedConversationId ? "drop-ready" : ""} ${dropProjectId === project.id ? "drop-target" : ""}`}
              key={project.id}
              onDragOver={(event) => {
                if (!draggedConversationId || movingId || projectBusy) return;
                event.preventDefault();
                event.dataTransfer.dropEffect = "move";
                setDropProjectId(project.id);
              }}
              onDragLeave={() => { if (dropProjectId === project.id) setDropProjectId(null); }}
              onDrop={(event) => {
                event.preventDefault();
                const conversation = conversations.find((item) => item.id === draggedConversationId && !item.project_id);
                endConversationDrag();
                if (conversation) void moveConversation(conversation, project.id);
              }}>
              <button type="button" className={selectedProject === project.id ? "chat-project-filter active" : "chat-project-filter"}
                onClick={() => toggleProject(project.id)} title={draggedConversationId ? `Thả hội thoại vào ${project.title}` : project.title}
                aria-expanded={expandedProjectIds.has(project.id)}>
                {expandedProjectIds.has(project.id) ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
                <Folder size={16} aria-hidden="true" /> <span>{project.title}</span>
              </button>
              <button type="button" className="chat-project-options" aria-label={`Tùy chọn Project ${project.title}`}
                aria-expanded={projectMenuId === project.id}
                onClick={() => setProjectMenuId((current) => current === project.id ? null : project.id)}>
                <MoreHorizontal size={16} aria-hidden="true" />
              </button>
              {projectMenuId === project.id && (
                <div className="chat-project-actions">
                  <button type="button" disabled={loading || historyLoading || !!movingId || projectBusy}
                    onClick={() => { chooseProject(project.id); setExpandedProjectIds((current) => new Set(current).add(project.id)); questionRef.current?.focus(); }}>
                    <SquarePen size={14} aria-hidden="true" /> Chat mới
                  </button>
                  <button type="button" onClick={() => { setProjectEditor({ id: project.id, title: project.title }); setProjectMenuId(null); }}>
                    <Pencil size={14} aria-hidden="true" /> Đổi tên
                  </button>
                  <button type="button" onClick={() => void deleteProject(project)}>
                    <Trash2 size={14} aria-hidden="true" /> Xóa Project
                  </button>
                </div>
              )}
              {expandedProjectIds.has(project.id) && (
                <div className="chat-project-children">
                  {projectConversations[project.id]?.map(renderConversation)}
                  {!projectConversations[project.id] && <p>Đang tải…</p>}
                  {projectConversations[project.id]?.length === 0 && <p>Chưa có hội thoại.</p>}
                  {(projectConversations[project.id]?.length ?? 0) >= 100 && <p>Hiển thị 100 chat gần nhất.</p>}
                </div>
              )}
            </div>
          ))}
          {projectEditor && (
            <form className="chat-project-editor" onSubmit={(event) => void saveProject(event)}>
              <label htmlFor="chat-project-title">Tên Project</label>
              <input id="chat-project-title" autoFocus maxLength={80} value={projectEditor.title}
                onChange={(event) => setProjectEditor({ ...projectEditor, title: event.target.value })}
                disabled={projectBusy} />
              <div>
                <button type="submit" disabled={projectBusy || !projectEditor.title.trim()}>Lưu</button>
                <button type="button" onClick={() => setProjectEditor(null)} disabled={projectBusy}>Hủy</button>
              </div>
            </form>
          )}
        </div>
        <div className="chat-sidebar-heading"><h2>Recents</h2></div>
        {visibleConversations.some((conversation) => !conversation.project_id) && projects.length > 0 && (
          <p className="chat-drag-hint">Kéo chat chưa phân loại vào một Project.</p>
        )}
        <div className="chat-conversation-list">
          {visibleConversations.map(renderConversation)}
          {listLoading && <p>Đang tìm hội thoại…</p>}
          {!listLoading && visibleConversations.length === 0 && <p>Chưa có hội thoại phù hợp.</p>}
          {conversations.length >= 100 && <p>Đang hiển thị 100 hội thoại gần nhất trong bộ lọc.</p>}
        </div>
      </div>
      <div className="chat-main glass-panel">
        <div className="chat-header">
          <div>
            <h2>NewsPulse Assistant</h2>
            <p>{!activeId && selectedProject !== "all"
              ? `Chat mới trong Project ${projects.find((project) => project.id === selectedProject)?.title ?? ""}.`
              : "Hỏi về bài viết, từ khóa, cảm xúc, thực thể và nguồn tin."}</p>
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
      {open && contextMenu && contextConversation && createPortal(
        <div ref={contextMenuRef} className="chat-context-menu" role="menu"
          aria-label="Tùy chọn hội thoại" style={{ left: contextMenu.x, top: contextMenu.y }}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.stopPropagation();
              setContextMenu(null);
              contextMenu.trigger.focus();
            }
          }}>
          <button type="button" role="menuitem"
            onClick={() => void deleteConversation(contextConversation)}>
            <Trash2 size={16} aria-hidden="true" /> Xóa hội thoại
          </button>
          <div className="chat-context-menu-label">Chuyển vào Project</div>
          <button type="button" role="menuitem" disabled={!contextConversation.project_id}
            onClick={() => void moveConversation(contextConversation, null)}>
            Chưa phân loại
          </button>
          {projects.map((project) => (
            <button type="button" role="menuitem" key={project.id}
              disabled={contextConversation.project_id === project.id}
              onClick={() => void moveConversation(contextConversation, project.id)}>
              {project.title}
            </button>
          ))}
        </div>, document.body
      )}
    </section>
  );
}

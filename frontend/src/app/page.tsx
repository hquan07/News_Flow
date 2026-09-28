"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Activity,
  BookOpen,
  Radio,
  ThumbsUp,
  Hash,
  MessageSquare,
  AlertTriangle,
  Share2,
  Download,
  Server,
} from "lucide-react";
import LandingHero from "@/components/LandingHero";
import AlertsPanel from "@/components/AlertsPanel";
import AdminView from "@/components/views/AdminView";
import DebatesView from "@/components/views/DebatesView";
import ForYouView from "@/components/views/ForYouView";
import StreamView from "@/components/views/StreamView";
import ArticlesView from "@/components/views/ArticlesView";
import NetworkView from "@/components/views/NetworkView";
import EntitiesView from "@/components/views/EntitiesView";
import SentimentView from "@/components/views/SentimentView";
import OverviewSocialView from "@/components/views/OverviewSocialView";
import OverviewNewsView from "@/components/views/OverviewNewsView";
import ArchitectureView from "@/components/views/ArchitectureView";
import { API_BASE, apiFetch } from "@/lib/api";
import { readCachedUser } from "@/lib/auth-storage";
import {
  EMPTY_ARTICLE_FILTERS,
  type ArticleFilters,
} from "@/lib/article-types";
import type {
  ArticleAlertFilter,
  SocialCrisisAlert,
  ViralPostAlertSummary,
} from "@/lib/alert-types";

type FeedEvent = {
  timestamp: string;
  type: string;
  message: string;
  data?: any;
};

type LiveSocialAlerts = {
  crisis: SocialCrisisAlert[];
  viral: ViralPostAlertSummary[];
};

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return `${diffSec}s ago`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} min ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay}d ago`;
}

async function safeFetch(url: string): Promise<any> {
  return apiFetch(url);
}

const TAB_FILTER_CAPABILITIES: Record<string, boolean> = {
  overview: true,
  sentiment: true,
  debates: true,
};

export default function Home() {
  const [activeTab, setActiveTab] = useState("overview");
  const [dashboardMode, setDashboardMode] = useState<
    "news" | "social" | "admin"
  >("news");
  const [selectedSource, setSelectedSource] = useState<string>("");
  const [feed, setFeed] = useState<FeedEvent[]>([]);
  const [isStreamPaused, setIsStreamPaused] = useState(false);
  const [bufferedFeed, setBufferedFeed] = useState<FeedEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const [overviewData, setOverviewData] = useState<any>(null);
  const [articles, setArticles] = useState<any[]>([]);
  const [articlesMeta, setArticlesMeta] = useState<any>({});
  const [page, setPage] = useState(1);
  const [articleSearchInput, setArticleSearchInput] = useState("");
  const [articleSearchQuery, setArticleSearchQuery] = useState("");
  const [articlesLoading, setArticlesLoading] = useState(false);
  const [articleAlertFilter, setArticleAlertFilter] =
    useState<ArticleAlertFilter | null>(null);
  const [articleFilters, setArticleFilters] = useState<ArticleFilters>({
    ...EMPTY_ARTICLE_FILTERS,
  });
  const [liveSocialAlerts, setLiveSocialAlerts] =
    useState<LiveSocialAlerts | null>(null);

  const [adminLatency, setAdminLatency] = useState<any>(null);
  const [adminClickbait, setAdminClickbait] = useState<any>(null);
  const [adminUsers, setAdminUsers] = useState<any>(null);
  const [adminHealth, setAdminHealth] = useState<any>(null);
  const [adminOperations, setAdminOperations] = useState<any>(null);
  const [dataUpdatedAt, setDataUpdatedAt] = useState<string | null>(null);

  const [sentimentDist, setSentimentDist] = useState<any[] | null>(null);
  const [sentimentTimeline, setSentimentTimeline] = useState<any[] | null>(null);
  const [sentimentSources, setSentimentSources] = useState<any[] | null>(null);
  const [sentimentCoverage, setSentimentCoverage] = useState<any>(null);
  const [entitiesData, setEntitiesData] = useState<any[] | null>(null);
  const [trendingKeywords, setTrendingKeywords] = useState<any[] | null>(null);
  const [entityTypeDist, setEntityTypeDist] = useState<any[] | null>(null);
  const [entitySentiment, setEntitySentiment] = useState<any[] | null>(null);
  const [knowledgeGraph, setKnowledgeGraph] = useState<any>({
    nodes: [],
    links: [],
  });

  const sseRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);
  const articlesAbortRef = useRef<AbortController | null>(null);
  const streamPausedRef = useRef(false);

  const [activeCard, setActiveCard] = useState<number | null>(null);
  const [user, setUser] = useState<any>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authName, setAuthName] = useState("");
  const [authModalError, setAuthModalError] = useState<string | null>(null);
  const [forYouArticles, setForYouArticles] = useState<any[]>([]);

  // Auth Functions
  const handleAuth = async (e: any) => {
    e.preventDefault();
    setAuthModalError(null);
    try {
      const url =
        authMode === "login"
          ? `${API_BASE}/auth/login`
          : `${API_BASE}/auth/register`;
      const body =
        authMode === "login"
          ? { email: authEmail, password: authPassword }
          : { email: authEmail, password: authPassword, full_name: authName };

      const data = await apiFetch<any>(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (authMode === "login") {
        localStorage.setItem("token", data.access_token);
        localStorage.setItem("user_cache", JSON.stringify(data.user));
        setUser(data.user);
      } else {
        setAuthMode("login");
        setAuthModalError("Registered successfully. Please login.");
      }
    } catch (err: any) {
      setAuthModalError(err.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user_cache");
    setUser(null);
    setActiveTab("overview");
  };

  const exportToCSV = (data: any[], filename: string) => {
    if (!data || !data.length) {
      alert("No data available to export");
      return;
    }
    const headers = Object.keys(data[0]).join(",");
    const rows = data.map((row) =>
      Object.values(row)
        .map((val) => `"${String(val).replace(/"/g, '""')}"`)
        .join(","),
    );
    const csvContent =
      "data:text/csv;charset=utf-8," + [headers, ...rows].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", filename);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const fetchForYou = useCallback(async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    try {
      const data = await apiFetch<any>(`${API_BASE}/recommendations/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setForYouArticles(data.articles || []);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const trackClick = async (article_hash: string) => {
    const token = localStorage.getItem("token");
    if (!token || !article_hash) return;
    try {
      await fetch(
        `${API_BASE}/recommendations/interact?article_hash=${article_hash}&interaction_type=click`,
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        },
      );
    } catch {}
  };

  // Load UI state on mount
  useEffect(() => {
    const savedMode = localStorage.getItem("newsFlowMode");
    const savedTab = localStorage.getItem("newsFlowTab");
    if (savedMode) setDashboardMode(savedMode as any);
    if (savedTab) setActiveTab(savedTab);
  }, []);

  // Save UI state on change
  useEffect(() => {
    localStorage.setItem("newsFlowMode", dashboardMode);
  }, [dashboardMode]);

  useEffect(() => {
    localStorage.setItem("newsFlowTab", activeTab);
  }, [activeTab]);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      setUser(readCachedUser());
    }
  }, []);

  // Smart fetch: only load data relevant to the active tab
  const fetchOverview = useCallback(async () => {
    const sourceParam = selectedSource ? `&source=${selectedSource}` : "";
    if (dashboardMode === "news") {
      const result = await safeFetch(
        `${API_BASE}/overview?time_range=all${sourceParam}`,
      );
      setOverviewData(result);
    } else if (dashboardMode === "social") {
      const result = await safeFetch(
        `${API_BASE}/social/overview?time_range=all${sourceParam}`,
      );
      setOverviewData(result);
    }
  }, [dashboardMode, selectedSource]);

  const fetchSentiment = useCallback(async () => {
    const sourceParam = selectedSource ? `?source=${selectedSource}` : "";
    if (dashboardMode === "news") {
      const results = await Promise.allSettled([
        safeFetch(`${API_BASE}/sentiment/distribution${sourceParam}`),
        safeFetch(`${API_BASE}/sentiment/timeline${sourceParam}`),
        safeFetch(`${API_BASE}/sentiment/sources${sourceParam}`),
        safeFetch(`${API_BASE}/sentiment/coverage`),
      ]);
      if (results[0].status === "fulfilled")
        setSentimentDist(results[0].value.data || []);
      if (results[1].status === "fulfilled")
        setSentimentTimeline(results[1].value.data || []);
      if (results[2].status === "fulfilled")
        setSentimentSources(results[2].value.data || []);
      if (results[3].status === "fulfilled")
        setSentimentCoverage(results[3].value);
    } else if (dashboardMode === "social") {
      const result = await safeFetch(
        `${API_BASE}/social/sentiment${sourceParam.replace("?", "&time_range=all&").replace(/^&/, "?")}`,
      );
      setSentimentDist(result.sentiment_distribution || []);
      setSentimentTimeline(result.sentiment_timeline || []);
      setSentimentSources(result.sentiment_by_source || []);
      setSentimentCoverage(null);
    }
  }, [dashboardMode, selectedSource]);

  const fetchDebates = useCallback(async () => {
    const sourceParam = selectedSource ? `&source=${selectedSource}` : "";
    if (dashboardMode === "social") {
      const result = await safeFetch(
        `${API_BASE}/social/debates?time_range=all${sourceParam}`,
      );
      setOverviewData((prev: any) => ({
        ...prev,
        top_debates: result.top_debates,
      }));
    }
  }, [dashboardMode, selectedSource]);

  const fetchAdmin = useCallback(async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };
    const [latencyRes, clickbaitRes, usersRes, healthRes, operationsRes] = await Promise.all([
      apiFetch(`${API_BASE}/admin/metrics/latency`, { headers }),
      apiFetch(`${API_BASE}/admin/metrics/volume`, { headers }),
      apiFetch(`${API_BASE}/admin/metrics/users`, { headers }),
      apiFetch(`${API_BASE}/admin/metrics/health`, { headers }),
      apiFetch(`${API_BASE}/admin/metrics/operations`, { headers }),
    ]);
    setAdminLatency(latencyRes);
    setAdminClickbait(clickbaitRes);
    setAdminUsers(usersRes);
    setAdminHealth(healthRes);
    setAdminOperations(operationsRes);
  }, []);

  const fetchEntities = useCallback(async () => {
    const results = await Promise.allSettled([
      safeFetch(`${API_BASE}/entities?limit=50`),
      safeFetch(`${API_BASE}/trending/keywords`),
      safeFetch(`${API_BASE}/entities/type-distribution`),
      safeFetch(`${API_BASE}/entities/sentiment?limit=50`),
    ]);
    if (results[0].status === "fulfilled")
      setEntitiesData(results[0].value || []);
    if (results[1].status === "fulfilled")
      setTrendingKeywords(results[1].value || []);
    if (results[2].status === "fulfilled")
      setEntityTypeDist(results[2].value || []);
    if (results[3].status === "fulfilled")
      setEntitySentiment(results[3].value || []);
  }, []);

  const fetchNetwork = useCallback(async () => {
    const result = await safeFetch(`${API_BASE}/entities/knowledge-graph?limit=100`);
    setKnowledgeGraph(result);
  }, []);

  const fetchArticles = useCallback(
    async (p: number) => {
      articlesAbortRef.current?.abort();
      const controller = new AbortController();
      articlesAbortRef.current = controller;
      setArticlesLoading(true);

      const params = new URLSearchParams({
        page: String(p),
        page_size: "20",
      });
      if (articleSearchQuery) params.set("q", articleSearchQuery);
      if (articleFilters.source) params.set("source", articleFilters.source);
      if (articleFilters.category) params.set("category", articleFilters.category);
      if (articleFilters.dateFrom) params.set("date_from", articleFilters.dateFrom);
      if (articleFilters.dateTo) params.set("date_to", articleFilters.dateTo);
      if (articleAlertFilter) {
        params.set("published_from", articleAlertFilter.publishedFrom);
        params.set("published_to", articleAlertFilter.publishedTo);
      }

      try {
        const result = await apiFetch<any>(
          `${API_BASE}/articles?${params.toString()}`,
          { signal: controller.signal },
        );
        if (!controller.signal.aborted) {
          setArticles(result.data || []);
          setArticlesMeta(result);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        throw error;
      } finally {
        if (articlesAbortRef.current === controller) {
          setArticlesLoading(false);
        }
      }
    },
    [articleAlertFilter, articleFilters, articleSearchQuery],
  );

  useEffect(() => {
    const timeout = setTimeout(() => {
      setPage(1);
      setArticleSearchQuery(articleSearchInput.trim());
    }, 350);
    return () => clearTimeout(timeout);
  }, [articleSearchInput]);

  useEffect(
    () => () => {
      articlesAbortRef.current?.abort();
    },
    [],
  );

  // Reset data when source changes
  useEffect(() => {
    setOverviewData(null);
    setSentimentDist(null);
    setSentimentTimeline(null);
    setSentimentSources(null);
    setEntitiesData(null);
    setTrendingKeywords(null);
    setEntityTypeDist(null);
    setEntitySentiment(null);
  }, [selectedSource, activeTab]);

  // Tab-aware polling
  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        if (activeTab === "overview") await fetchOverview();
        else if (activeTab === "sentiment") await fetchSentiment();
        else if (activeTab === "entities") await fetchEntities();
        else if (activeTab === "network") await fetchNetwork();
        else if (activeTab === "articles") await fetchArticles(page);
        else if (activeTab === "foryou") await fetchForYou();
        else if (activeTab === "debates") await fetchDebates();
        else if (activeTab === "admin_dashboard") await fetchAdmin();
        if (!cancelled) {
          setApiError(null);
          setDataUpdatedAt(new Date().toISOString());
        }
      } catch (error) {
        if (!cancelled) {
          const reason =
            error instanceof Error ? error.message : "Unknown API error";
          setApiError(`Unable to reach the API server: ${reason}`);
        }
      }
    };

    const pollWhenVisible = () => {
      if (document.visibilityState === "visible") void poll();
    };
    pollWhenVisible();
    const intervalId = setInterval(pollWhenVisible, 15000);
    document.addEventListener("visibilitychange", pollWhenVisible);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
      document.removeEventListener("visibilitychange", pollWhenVisible);
    };
  }, [
    activeTab,
    page,
    fetchOverview,
    fetchSentiment,
    fetchEntities,
    fetchNetwork,
    fetchArticles,
    fetchForYou,
    fetchDebates,
    fetchAdmin,
  ]);

  // One shared SSE connection for the debug feed and live alert cards.
  useEffect(() => {
    let disposed = false;

    const connectSSE = () => {
      if (disposed) return;
      if (sseRef.current) sseRef.current.close();

      const es = new EventSource(`${API_BASE}/stream`);
      sseRef.current = es;

      es.onopen = () => setIsConnected(true);
      es.addEventListener("update", () => {
        // Heartbeats prove the connection is alive but are intentionally not
        // rendered as business events in Live Stream Debug.
        setIsConnected(true);
      });
      es.addEventListener("alert", (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type !== "social_alerts") return;

          const crisis = Array.isArray(payload.crisis) ? payload.crisis : [];
          const viral = Array.isArray(payload.viral) ? payload.viral : [];
          setLiveSocialAlerts({ crisis, viral });
          const feedEvent: FeedEvent = {
            timestamp: payload.timestamp || new Date().toISOString(),
            type: "social_alerts",
            message: `${crisis.length} crisis alert${crisis.length === 1 ? "" : "s"} · ${viral.length} viral post${viral.length === 1 ? "" : "s"}`,
            data: { crisis, viral },
          };
          if (streamPausedRef.current) {
            setBufferedFeed((prev) => [feedEvent, ...prev].slice(0, 50));
          } else {
            setFeed((prev) => [feedEvent, ...prev].slice(0, 50));
          }
        } catch {}
      });
      es.onerror = () => {
        setIsConnected(false);
        es.close();
        if (!disposed && !reconnectTimer.current) {
          reconnectTimer.current = setTimeout(() => {
            reconnectTimer.current = null;
            connectSSE();
          }, 5000);
        }
      };
    };

    connectSSE();
    return () => {
      disposed = true;
      sseRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    };
  }, []);

  // Auto-hide error toast after 5 seconds
  useEffect(() => {
    if (!apiError) return;
    const t = setTimeout(() => setApiError(null), 5000);
    return () => clearTimeout(t);
  }, [apiError]);

  const chartData =
    overviewData?.articles_by_hour?.map((row: any) => ({
      time: `${row.hour}:00`,
      count: row.count,
    })) || [];

  const sourceData =
    overviewData?.category_distribution?.map((row: any) => ({
      name: row.category,
      count: row.count,
    })) || [];

  return (
    <div className="container">
      {user && (
        <header className="dashboard-header">
          <div>
            <h1>NewsPulse Intelligence</h1>
            <p className="subtitle">Real-time Data Pipeline Dashboard</p>
          </div>
          <div className="header-controls">
            <div
              className="mode-toggle"
              style={{
                display: "flex",
                background: "rgba(255,255,255,0.05)",
                borderRadius: "20px",
                padding: "4px",
                border: "1px solid rgba(255,255,255,0.1)",
              }}
            >
              <button
                onClick={() => {
                  setDashboardMode("news");
                  setSelectedSource("");
                  setActiveTab("overview");
                }}
                style={{
                  padding: "6px 16px",
                  border: "none",
                  background:
                    dashboardMode === "news" ? "#3b82f6" : "transparent",
                  color: "white",
                  borderRadius: "16px",
                  cursor: "pointer",
                  fontWeight: 600,
                  transition: "all 0.3s",
                }}
              >
                📰 Official News
              </button>
              <button
                onClick={() => {
                  setDashboardMode("social");
                  setSelectedSource("");
                  setActiveTab("overview");
                }}
                style={{
                  padding: "6px 16px",
                  border: "none",
                  background:
                    dashboardMode === "social" ? "#8b5cf6" : "transparent",
                  color: "white",
                  borderRadius: "16px",
                  cursor: "pointer",
                  fontWeight: 600,
                  transition: "all 0.3s",
                }}
              >
                💬 Social Media
              </button>
              {user?.role === "admin" && (
                <button
                  onClick={() => {
                    setDashboardMode("admin");
                    setSelectedSource("");
                    setActiveTab("admin_dashboard");
                  }}
                  style={{
                    padding: "6px 16px",
                    border: "none",
                    background:
                      dashboardMode === "admin" ? "#ef4444" : "transparent",
                    color: "white",
                    borderRadius: "16px",
                    cursor: "pointer",
                    fontWeight: 600,
                    transition: "all 0.3s",
                  }}
                >
                  ⚙️ Admin
                </button>
              )}
            </div>
            {TAB_FILTER_CAPABILITIES[activeTab] && (
              <select
                value={selectedSource}
                onChange={(e) => setSelectedSource(e.target.value)}
              style={{
                padding: "8px 16px",
                borderRadius: "8px",
                background: "rgba(15, 23, 42, 0.8)",
                color: "white",
                border: "1px solid rgba(255,255,255,0.2)",
                outline: "none",
                cursor: "pointer",
              }}
            >
              <option value="">All Sources</option>
              {dashboardMode === "news" ? (
                <>
                  <option value="vnexpress">VnExpress</option>
                  <option value="tuoitre">Tuổi Trẻ</option>
                  <option value="thanhnien">Thanh Niên</option>
                  <option value="dantri">Dân Trí</option>
                  <option value="laodong">Lao Động</option>
                  <option value="tienphong">Tiền Phong</option>
                </>
              ) : (
                <>
                  <option value="facebook">Facebook</option>
                  <option value="youtube">YouTube</option>
                  <option value="tiktok">TikTok</option>
                  <option value="twitter">Twitter</option>
                  <option value="voz">Voz Forum</option>
                  <option value="reddit_vn">Reddit VN</option>
                </>
              )}
              </select>
            )}
            <button
              onClick={() => window.print()}
              className="print-hide"
              style={{
                background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
                border: "none",
                padding: "6px 12px",
                borderRadius: "8px",
                color: "#fff",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "6px",
                fontWeight: 600,
              }}
            >
              <Download size={16} /> Export PDF
            </button>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                marginLeft: "10px",
                paddingLeft: "20px",
                borderLeft: "1px solid rgba(255,255,255,0.2)",
              }}
            >
              <div
                style={{
                  background: "#3b82f6",
                  borderRadius: "50%",
                  width: "32px",
                  height: "32px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontWeight: "bold",
                }}
              >
                {user.email[0].toUpperCase()}
              </div>
              <button
                onClick={handleLogout}
                className="print-hide"
                style={{
                  background: "transparent",
                  border: "1px solid rgba(255,255,255,0.2)",
                  padding: "6px 12px",
                  borderRadius: "8px",
                  color: "#fff",
                  cursor: "pointer",
                }}
              >
                Logout
              </button>
            </div>
          </div>
        </header>
      )}
      {!user ? (
        <LandingHero
          authMode={authMode}
          setAuthMode={setAuthMode}
          authName={authName}
          setAuthName={setAuthName}
          authEmail={authEmail}
          setAuthEmail={setAuthEmail}
          authPassword={authPassword}
          setAuthPassword={setAuthPassword}
          authModalError={authModalError}
          handleAuth={handleAuth}
        />
      ) : (
        <>
          <div
            className="tabs"
            role="tablist"
            aria-label="Dashboard sections"
            onKeyDown={(event) => {
              if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
              const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
              const currentIndex = tabs.indexOf(document.activeElement as HTMLButtonElement);
              if (currentIndex < 0) return;
              event.preventDefault();
              const offset = event.key === "ArrowRight" ? 1 : -1;
              const next = tabs[(currentIndex + offset + tabs.length) % tabs.length];
              next.focus();
              next.click();
            }}
          >
            {dashboardMode === "news" && (
              <>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "overview"}
                  className={`tab-btn ${activeTab === "overview" ? "active" : ""}`}
                  onClick={() => setActiveTab("overview")}
                >
                  <Activity size={18} /> Overview
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "sentiment"}
                  className={`tab-btn ${activeTab === "sentiment" ? "active" : ""}`}
                  onClick={() => setActiveTab("sentiment")}
                >
                  <ThumbsUp size={18} /> Sentiment
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "entities"}
                  className={`tab-btn ${activeTab === "entities" ? "active" : ""}`}
                  onClick={() => setActiveTab("entities")}
                >
                  <Hash size={18} /> Entities & NLP
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "network"}
                  className={`tab-btn ${activeTab === "network" ? "active" : ""}`}
                  onClick={() => setActiveTab("network")}
                >
                  <Share2 size={18} /> Network
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "articles"}
                  className={`tab-btn ${activeTab === "articles" ? "active" : ""}`}
                  onClick={() => {
                    setActiveTab("articles");
                    setPage(1);
                    setArticleAlertFilter(null);
                  }}
                >
                  <BookOpen size={18} /> Latest News
                </button>
                {user && (
                  <button
                    type="button"
                    role="tab"
                    aria-selected={activeTab === "foryou"}
                    className={`tab-btn ${activeTab === "foryou" ? "active" : ""}`}
                    onClick={() => setActiveTab("foryou")}
                    style={{
                      background: "linear-gradient(90deg, #8b5cf6, #3b82f6)",
                      color: "white",
                    }}
                  >
                    ✨ For You
                  </button>
                )}
              </>
            )}

            {dashboardMode === "social" && (
              <>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "overview"}
                  className={`tab-btn ${activeTab === "overview" ? "active" : ""}`}
                  onClick={() => setActiveTab("overview")}
                >
                  <Activity size={18} /> Overview
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "sentiment"}
                  className={`tab-btn ${activeTab === "sentiment" ? "active" : ""}`}
                  onClick={() => setActiveTab("sentiment")}
                >
                  <ThumbsUp size={18} /> Sentiment
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "debates"}
                  className={`tab-btn ${activeTab === "debates" ? "active" : ""}`}
                  onClick={() => setActiveTab("debates")}
                >
                  <MessageSquare size={18} /> Top Debates
                </button>
              </>
            )}

            {dashboardMode === "admin" && (
              <>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "admin_dashboard"}
                  className={`tab-btn ${activeTab === "admin_dashboard" ? "active" : ""}`}
                  onClick={() => setActiveTab("admin_dashboard")}
                >
                  <Activity size={18} /> Admin Dashboard
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "articles"}
                  className={`tab-btn ${activeTab === "articles" ? "active" : ""}`}
                  onClick={() => {
                    setActiveTab("articles");
                    setPage(1);
                    setArticleAlertFilter(null);
                  }}
                >
                  <BookOpen size={18} /> System Articles
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "stream"}
                  className={`tab-btn ${activeTab === "stream" ? "active" : ""}`}
                  onClick={() => setActiveTab("stream")}
                >
                  <Radio size={18} /> Live Stream Debug
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "alerts"}
                  className={`tab-btn ${activeTab === "alerts" ? "active" : ""}`}
                  onClick={() => setActiveTab("alerts")}
                >
                  <AlertTriangle size={18} /> System Alerts
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeTab === "architecture"}
                  className={`tab-btn ${activeTab === "architecture" ? "active" : ""}`}
                  onClick={() => setActiveTab("architecture")}
                >
                  <Server size={18} /> Architecture
                </button>
              </>
            )}
          </div>

          {activeTab === "overview" && dashboardMode === "news" && (
            <OverviewNewsView
              overviewData={overviewData}
              chartData={chartData}
              sourceData={sourceData}
              activeCard={activeCard}
              setActiveCard={setActiveCard}
              exportToCSV={exportToCSV}
              updatedAt={dataUpdatedAt}
            />
          )}
          {activeTab === "overview" && dashboardMode === "social" && (
            <OverviewSocialView
              overviewData={overviewData}
              activeCard={activeCard}
              setActiveCard={setActiveCard}
              updatedAt={dataUpdatedAt}
            />
          )}

          {activeTab === "sentiment" && (
            <SentimentView
              sentimentDist={sentimentDist}
              sentimentTimeline={sentimentTimeline}
              sentimentSources={sentimentSources}
              sentimentCoverage={sentimentCoverage}
              updatedAt={dataUpdatedAt}
            />
          )}

          {activeTab === "entities" && (
            <EntitiesView
              entitiesData={entitiesData}
              trendingKeywords={trendingKeywords}
              entityTypeDist={entityTypeDist}
              entitySentiment={entitySentiment}
              updatedAt={dataUpdatedAt}
            />
          )}

          {activeTab === "network" && (
            <NetworkView knowledgeGraph={knowledgeGraph} updatedAt={dataUpdatedAt} />
          )}

          {activeTab === "articles" && (
            <ArticlesView
              title={dashboardMode === "admin" ? "System Articles" : "Latest Articles"}
              articles={articles}
              articlesMeta={articlesMeta}
              page={page}
              setPage={setPage}
              searchQuery={articleSearchInput}
              setSearchQuery={setArticleSearchInput}
              loading={articlesLoading}
              filters={articleFilters}
              setFilters={(filters) => {
                setArticleFilters(filters);
                setPage(1);
              }}
              contextFilter={articleAlertFilter}
              clearContextFilter={() => {
                setArticleAlertFilter(null);
                setPage(1);
              }}
              trackClick={trackClick}
              timeAgo={timeAgo}
              exportToCSV={exportToCSV}
            />
          )}

          {activeTab === "stream" && (
            <StreamView
              feed={feed}
              isConnected={isConnected}
              isPaused={isStreamPaused}
              bufferedCount={bufferedFeed.length}
              onPause={() => {
                streamPausedRef.current = true;
                setIsStreamPaused(true);
              }}
              onResume={() => {
                streamPausedRef.current = false;
                setIsStreamPaused(false);
                setFeed((current) => [...bufferedFeed, ...current].slice(0, 50));
                setBufferedFeed([]);
              }}
            />
          )}

          {activeTab === "alerts" && (
            <AlertsPanel
              liveAlerts={liveSocialAlerts}
              onOpenArticles={(filter) => {
                setArticleAlertFilter(filter);
                setArticleSearchInput("");
                setArticleSearchQuery("");
                setArticleFilters({ ...EMPTY_ARTICLE_FILTERS });
                setPage(1);
                setDashboardMode("news");
                setActiveTab("articles");
              }}
            />
          )}

          {apiError && (
            <div className="error-toast">
              <AlertTriangle
                size={16}
                style={{
                  display: "inline",
                  verticalAlign: "middle",
                  marginRight: "0.5rem",
                }}
              />
              {apiError}
            </div>
          )}

          {activeTab === "foryou" && (
            <ForYouView
              forYouArticles={forYouArticles}
              trackClick={trackClick}
              timeAgo={timeAgo}
            />
          )}
          {activeTab === "admin_dashboard" && dashboardMode === "admin" && (
            <AdminView
              adminLatency={adminLatency}
              adminClickbait={adminClickbait}
              adminUsers={adminUsers}
              adminHealth={adminHealth}
              adminOperations={adminOperations}
              updatedAt={dataUpdatedAt}
            />
          )}
          {activeTab === "debates" && dashboardMode === "social" && (
            <DebatesView overviewData={overviewData} />
          )}
          {activeTab === "architecture" && dashboardMode === "admin" && (
            <ArchitectureView />
          )}
        </>
      )}
    </div>
  );
}

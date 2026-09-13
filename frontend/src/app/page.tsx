"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  AreaChart,
  Area,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import {
  Activity,
  BookOpen,
  BarChart2,
  Radio,
  ThumbsUp,
  Hash,
  Users,
  MessageSquare,
  AlertTriangle,
  Share2,
  Settings,
  Play,
  RefreshCw,
  Database,
  CheckCircle,
  XCircle,
  Clock,
  Loader,
  Download,
  FileText,
} from "lucide-react";
import LandingHero from "@/components/LandingHero";
import KnowledgeGraph from "@/components/KnowledgeGraph";
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

const API_BASE = "http://localhost:8001/api/v1";

type FeedEvent = {
  timestamp: string;
  type: string;
  message: string;
  data?: any;
};

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffSec = Math.floor((now - then) / 1000);
  if (diffSec < 60) return `${diffSec}s trước`;
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} phút trước`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr} giờ trước`;
  const diffDay = Math.floor(diffHr / 24);
  return `${diffDay} ngày trước`;
}

async function safeFetch(url: string): Promise<any> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export default function Home() {
  const [activeTab, setActiveTab] = useState("overview");
  const [dashboardMode, setDashboardMode] = useState<
    "news" | "social" | "admin"
  >("news");
  const [selectedSource, setSelectedSource] = useState<string>("");
  const [feed, setFeed] = useState<FeedEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const [overviewData, setOverviewData] = useState<any>(null);
  const [articles, setArticles] = useState<any[]>([]);
  const [articlesMeta, setArticlesMeta] = useState<any>({});
  const [page, setPage] = useState(1);

  const [adminLatency, setAdminLatency] = useState<any>(null);
  const [adminClickbait, setAdminClickbait] = useState<any>(null);
  const [adminUsers, setAdminUsers] = useState<any>(null);

  const [sentimentDist, setSentimentDist] = useState<any[]>([]);
  const [sentimentTimeline, setSentimentTimeline] = useState<any[]>([]);
  const [sentimentSources, setSentimentSources] = useState<any[]>([]);
  const [entitiesData, setEntitiesData] = useState<any[]>([]);
  const [trendingKeywords, setTrendingKeywords] = useState<any[]>([]);
  const [entityTypeDist, setEntityTypeDist] = useState<any[]>([]);
  const [entitySentiment, setEntitySentiment] = useState<any[]>([]);
  const [knowledgeGraph, setKnowledgeGraph] = useState<any>({
    nodes: [],
    links: [],
  });

  const sseRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);

  const [activeCard, setActiveCard] = useState<number | null>(null);
  const [user, setUser] = useState<any>(null);
  const [showAuth, setShowAuth] = useState(false);
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

      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Auth failed");

      if (authMode === "login") {
        localStorage.setItem("token", data.access_token);
        setUser(data.user);
        setShowAuth(false);
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
      const res = await fetch(`${API_BASE}/recommendations/`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      if (res.ok) setForYouArticles(data.articles || []);
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
    } catch (e) {}
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
      setUser(
        JSON.parse(
          localStorage.getItem("user_cache") || '{"email": "user@example.com"}',
        ),
      );
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
      ]);
      if (results[0].status === "fulfilled")
        setSentimentDist(results[0].value.data || []);
      if (results[1].status === "fulfilled")
        setSentimentTimeline(results[1].value.data || []);
      if (results[2].status === "fulfilled")
        setSentimentSources(results[2].value.data || []);
    } else if (dashboardMode === "social") {
      const result = await safeFetch(
        `${API_BASE}/social/sentiment${sourceParam.replace("?", "&time_range=all&").replace(/^&/, "?")}`,
      );
      setSentimentDist(result.sentiment_distribution || []);
      setSentimentTimeline(result.sentiment_timeline || []);
      setSentimentSources(result.sentiment_by_source || []);
    }
  }, [selectedSource, dashboardMode]);

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
  }, [selectedSource, dashboardMode]);

  const fetchAdmin = useCallback(async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };
    const [latencyRes, clickbaitRes, usersRes] = await Promise.all([
      fetch(`${API_BASE}/admin/metrics/latency`, { headers }).then((r) =>
        r.json(),
      ),
      fetch(`${API_BASE}/admin/metrics/volume`, { headers }).then((r) =>
        r.json(),
      ),
      fetch(`${API_BASE}/admin/metrics/users`, { headers }).then((r) =>
        r.json(),
      ),
    ]);
    setAdminLatency(latencyRes);
    setAdminClickbait(clickbaitRes);
    setAdminUsers(usersRes);
  }, []);

  const fetchEntities = useCallback(async () => {
    const results = await Promise.allSettled([
      safeFetch(`${API_BASE}/entities`),
      safeFetch(`${API_BASE}/trending/keywords`),
      safeFetch(`${API_BASE}/entities/type-distribution`),
      safeFetch(`${API_BASE}/entities/sentiment`),
    ]);
    if (results[0].status === "fulfilled")
      setEntitiesData(results[0].value || []);
    if (results[1].status === "fulfilled")
      setTrendingKeywords(results[1].value || []);
    if (results[2].status === "fulfilled")
      setEntityTypeDist(results[2].value || []);
    if (results[3].status === "fulfilled")
      setEntitySentiment(results[3].value || []);
  }, [selectedSource, dashboardMode]);

  const fetchNetwork = useCallback(async () => {
    const result = await safeFetch(`${API_BASE}/entities/knowledge-graph`);
    setKnowledgeGraph(result);
  }, [selectedSource, dashboardMode]);

  const fetchArticles = useCallback(
    async (p: number) => {
      const result = await safeFetch(
        `${API_BASE}/articles?page=${p}&page_size=20`,
      );
      setArticles(result.data || []);
      setArticlesMeta(result);
    },
    [selectedSource, dashboardMode],
  );

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
        if (!cancelled) setApiError(null);
      } catch (err: any) {
        if (!cancelled) setApiError("Mất kết nối tới API server");
      }
    };

    poll();
    const intervalId = setInterval(poll, 15000);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
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

  // SSE with auto-reconnect
  useEffect(() => {
    const connectSSE = () => {
      if (sseRef.current) sseRef.current.close();

      const es = new EventSource(`${API_BASE}/stream/`);
      sseRef.current = es;

      es.onopen = () => setIsConnected(true);
      es.addEventListener("update", (event) => {
        try {
          const newEvent = JSON.parse(event.data);
          setFeed((prev) => [newEvent, ...prev].slice(0, 50));
        } catch {}
      });
      es.onerror = () => {
        setIsConnected(false);
        es.close();
        reconnectTimer.current = setTimeout(connectSSE, 5000);
      };
    };

    connectSSE();
    return () => {
      sseRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [selectedSource, dashboardMode]);

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
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <h1>NewsPulse Intelligence</h1>
            <p className="subtitle">Real-time Data Pipeline Dashboard</p>
          </div>
          <div style={{ display: "flex", gap: "15px", alignItems: "center" }}>
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
          <div className="tabs">
            {dashboardMode === "news" && (
              <>
                <button
                  className={`tab-btn ${activeTab === "overview" ? "active" : ""}`}
                  onClick={() => setActiveTab("overview")}
                >
                  <Activity size={18} /> Overview
                </button>
                <button
                  className={`tab-btn ${activeTab === "sentiment" ? "active" : ""}`}
                  onClick={() => setActiveTab("sentiment")}
                >
                  <ThumbsUp size={18} /> Sentiment
                </button>
                <button
                  className={`tab-btn ${activeTab === "entities" ? "active" : ""}`}
                  onClick={() => setActiveTab("entities")}
                >
                  <Hash size={18} /> Entities & NLP
                </button>
                <button
                  className={`tab-btn ${activeTab === "network" ? "active" : ""}`}
                  onClick={() => setActiveTab("network")}
                >
                  <Share2 size={18} /> Network
                </button>
                <button
                  className={`tab-btn ${activeTab === "articles" ? "active" : ""}`}
                  onClick={() => {
                    setActiveTab("articles");
                    setPage(1);
                  }}
                >
                  <BookOpen size={18} /> Latest News
                </button>
                {user && (
                  <button
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
                  className={`tab-btn ${activeTab === "overview" ? "active" : ""}`}
                  onClick={() => setActiveTab("overview")}
                >
                  <Activity size={18} /> Overview
                </button>
                <button
                  className={`tab-btn ${activeTab === "sentiment" ? "active" : ""}`}
                  onClick={() => setActiveTab("sentiment")}
                >
                  <ThumbsUp size={18} /> Sentiment
                </button>
                <button
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
                  className={`tab-btn ${activeTab === "admin_dashboard" ? "active" : ""}`}
                  onClick={() => setActiveTab("admin_dashboard")}
                >
                  <Activity size={18} /> Admin Dashboard
                </button>
                <button
                  className={`tab-btn ${activeTab === "articles" ? "active" : ""}`}
                  onClick={() => {
                    setActiveTab("articles");
                    setPage(1);
                  }}
                >
                  <BookOpen size={18} /> System Articles
                </button>
                <button
                  className={`tab-btn ${activeTab === "stream" ? "active" : ""}`}
                  onClick={() => setActiveTab("stream")}
                >
                  <Radio size={18} /> Live Stream Debug
                </button>
                <button
                  className={`tab-btn ${activeTab === "alerts" ? "active" : ""}`}
                  onClick={() => setActiveTab("alerts")}
                >
                  <AlertTriangle size={18} /> System Alerts
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
            />
          )}
          {activeTab === "overview" && dashboardMode === "social" && (
            <OverviewSocialView
              overviewData={overviewData}
              activeCard={activeCard}
              setActiveCard={setActiveCard}
            />
          )}

          {activeTab === "sentiment" && (
            <SentimentView
              sentimentDist={sentimentDist}
              sentimentTimeline={sentimentTimeline}
              sentimentSources={sentimentSources}
            />
          )}

          {activeTab === "entities" && (
            <EntitiesView
              entitiesData={entitiesData}
              trendingKeywords={trendingKeywords}
              entityTypeDist={entityTypeDist}
              entitySentiment={entitySentiment}
            />
          )}

          {activeTab === "network" && (
            <NetworkView knowledgeGraph={knowledgeGraph} />
          )}

          {activeTab === "articles" && (
            <ArticlesView
              articles={articles}
              articlesMeta={articlesMeta}
              page={page}
              setPage={setPage}
              trackClick={trackClick}
              timeAgo={timeAgo}
              exportToCSV={exportToCSV}
            />
          )}

          {activeTab === "stream" && (
            <StreamView feed={feed} isConnected={isConnected} />
          )}

          {activeTab === "alerts" && <AlertsPanel />}

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
              articles={articles}
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
              timeAgo={timeAgo}
            />
          )}
          {activeTab === "debates" && dashboardMode === "social" && (
            <DebatesView overviewData={overviewData} feed={feed} />
          )}
        </>
      )}
    </div>
  );
}

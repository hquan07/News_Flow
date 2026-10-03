"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Image from "next/image";
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
  Users,
  DatabaseZap,
  UserCog,
  Newspaper,
  Settings,
  Sparkles,
  BellRing,
  Layers3,
  BarChart3,
  ClipboardList,
  HardDrive,
} from "lucide-react";
import LandingHero from "@/components/LandingHero";
import AccountAvatar from "@/components/AccountAvatar";
import DashboardSidebar, {
  type DashboardNavigationItem,
} from "@/components/DashboardSidebar";
import AlertsPanel from "@/components/AlertsPanel";
import AdminView from "@/components/views/AdminView";
import DebatesView from "@/components/views/DebatesView";
import ForYouView from "@/components/views/ForYouView";
import ChatView from "@/components/views/ChatView";
import StreamView from "@/components/views/StreamView";
import ArticlesView from "@/components/views/ArticlesView";
import NetworkView from "@/components/views/NetworkView";
import EntitiesView from "@/components/views/EntitiesView";
import SentimentView from "@/components/views/SentimentView";
import OverviewSocialView from "@/components/views/OverviewSocialView";
import OverviewNewsView from "@/components/views/OverviewNewsView";
import ArchitectureView from "@/components/views/ArchitectureView";
import CrawlerManagementView from "@/components/views/CrawlerManagementView";
import UserManagementView from "@/components/views/UserManagementView";
import IntelligenceView from "@/components/views/IntelligenceView";
import EventsView from "@/components/views/EventsView";
import InsightsView from "@/components/views/InsightsView";
import BriefingsView from "@/components/views/BriefingsView";
import DataOperationsView from "@/components/views/DataOperationsView";
import WorkspacesView from "@/components/views/WorkspacesView";
import SocialInfluencersView, {
  type SocialInfluencer,
} from "@/components/views/SocialInfluencersView";
import LiveSocialFeedView, {
  type LiveSocialPost,
} from "@/components/views/LiveSocialFeedView";
import { API_BASE, apiFetch } from "@/lib/api";
import { hasPermission, readCachedUser, type CachedUser } from "@/lib/auth-storage";
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
  timestamp: string;
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
  influencers: true,
};

export default function Home() {
  const [activeTab, setActiveTab] = useState("overview");
  const [chatOpen, setChatOpen] = useState(false);
  const [chatIntelligenceScope, setChatIntelligenceScope] = useState<{ event_id?: string; watchlist_id?: string; label: string } | null>(null);
  const chatLauncherRef = useRef<HTMLButtonElement>(null);
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
  const [socialInfluencers, setSocialInfluencers] =
    useState<SocialInfluencer[] | null>(null);
  const [liveSocialPosts, setLiveSocialPosts] = useState<LiveSocialPost[]>([]);

  const [adminLatency, setAdminLatency] = useState<any>(null);
  const [adminClickbait, setAdminClickbait] = useState<any>(null);
  const [adminUsers, setAdminUsers] = useState<any>(null);
  const [adminHealth, setAdminHealth] = useState<any>(null);
  const [adminOperations, setAdminOperations] = useState<any>(null);
  const [adminAlertMetrics, setAdminAlertMetrics] = useState<any>(null);
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
  const [user, setUser] = useState<CachedUser | null>(null);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authName, setAuthName] = useState("");
  const [authModalError, setAuthModalError] = useState<string | null>(null);
  const [forYouArticles, setForYouArticles] = useState<any[]>([]);
  const canAccessOperations = hasPermission(user, "system.read") || hasPermission(user, "crawler.read") || hasPermission(user, "alerts.read");
  const canManageAlerts = hasPermission(user, "alerts.manage");
  const canManageUsers = hasPermission(user, "users.manage");
  const canExportFull = hasPermission(user, "reports.export_full");

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
    void apiFetch(`${API_BASE}/auth/logout`, { method: "POST" }).catch(() => {});
    localStorage.removeItem("token");
    localStorage.removeItem("user_cache");
    setUser(null);
    setChatOpen(false);
    setActiveTab("overview");
  };

  const handleExportPdf = async () => {
    if (apiError) {
      alert("Dashboard data is not ready for export. Please resolve the API error and try again.");
      return;
    }

    if (document.querySelector('[aria-busy="true"]')) {
      alert("Dashboard data is still loading. Please wait a moment and try again.");
      return;
    }

    if (document.fonts?.ready) await document.fonts.ready;
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
    });
    window.print();
  };

  const exportToCSV = (data: any[], filename: string) => {
    if (!canExportFull) {
      alert("Full CSV export requires the Analyst or Admin role.");
      return;
    }
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
    const data = await apiFetch<any>(`${API_BASE}/recommendations`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    setForYouArticles(data.articles || []);
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

  const [isInitialized, setIsInitialized] = useState(false);

  // Load UI state on mount
  useEffect(() => {
    const savedMode = localStorage.getItem("newsFlowMode");
    const savedTab = localStorage.getItem("newsFlowTab");
    if (savedMode) setDashboardMode(savedMode as any);
    if (savedTab) setActiveTab(savedTab === "chat" ? "overview" : savedTab);
    setIsInitialized(true);
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
      const cachedUser = readCachedUser();
      setUser(cachedUser);
      void apiFetch<CachedUser>(`${API_BASE}/auth/me`)
        .then((freshUser) => {
          localStorage.setItem("user_cache", JSON.stringify(freshUser));
          setUser(freshUser);
        })
        .catch(() => {
          localStorage.removeItem("token");
          localStorage.removeItem("user_cache");
          setUser(null);
        });
    }
  }, []);

  useEffect(() => {
    if (user && dashboardMode === "admin" && !canAccessOperations) {
      setDashboardMode("news");
      setActiveTab("overview");
    }
  }, [canAccessOperations, dashboardMode, user]);

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

  const fetchInfluencers = useCallback(async () => {
    if (dashboardMode !== "social") return;
    const sourceParam = selectedSource
      ? `&source=${encodeURIComponent(selectedSource)}`
      : "";
    const result = await safeFetch(
      `${API_BASE}/social/influencers?time_range=all&limit=20${sourceParam}`,
    );
    setSocialInfluencers(result.influencers || []);
  }, [dashboardMode, selectedSource]);

  const fetchLiveSocialFeed = useCallback(async () => {
    if (dashboardMode !== "social") return;
    const result = await safeFetch(`${API_BASE}/social/feed?limit=50`);
    setLiveSocialPosts((current) => {
      const byId = new Map<string, LiveSocialPost>();
      for (const post of [...current, ...(result.posts || [])]) {
        if (post?.post_id) byId.set(post.post_id, post);
      }
      return Array.from(byId.values())
        .sort((left, right) =>
          String(right.publish_time || "").localeCompare(
            String(left.publish_time || ""),
          ),
        )
        .slice(0, 100);
    });
  }, [dashboardMode]);

  const fetchAdmin = useCallback(async () => {
    const token = localStorage.getItem("token");
    if (!token) return;
    const headers = { Authorization: `Bearer ${token}` };
    const [latencyRes, clickbaitRes, usersRes, healthRes, operationsRes, alertMetricsRes] = await Promise.all([
      apiFetch(`${API_BASE}/admin/metrics/latency`, { headers }),
      apiFetch(`${API_BASE}/admin/metrics/volume`, { headers }),
      apiFetch(`${API_BASE}/admin/metrics/users`, { headers }),
      apiFetch(`${API_BASE}/admin/metrics/health`, { headers }),
      apiFetch(`${API_BASE}/admin/metrics/operations`, { headers }),
      apiFetch(`${API_BASE}/alerts/metrics`, { headers }),
    ]);
    setAdminLatency(latencyRes);
    setAdminClickbait(clickbaitRes);
    setAdminUsers(usersRes);
    setAdminHealth(healthRes);
    setAdminOperations(operationsRes);
    setAdminAlertMetrics(alertMetricsRes);
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
      if (articleFilters.entity) params.set("entity", articleFilters.entity);
      if (articleFilters.keyword) params.set("keyword", articleFilters.keyword);
      if (articleFilters.sentiment) params.set("sentiment", articleFilters.sentiment);
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
    setSocialInfluencers(null);
  }, [selectedSource, activeTab]);

  // Tab-aware polling
  useEffect(() => {
    if (!isInitialized) return;
    
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
        else if (activeTab === "influencers") await fetchInfluencers();
        else if (activeTab === "live_social") await fetchLiveSocialFeed();
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
    fetchInfluencers,
    fetchLiveSocialFeed,
    fetchAdmin,
    isInitialized,
  ]);

  // One shared SSE connection for the debug feed and live alert cards.
  useEffect(() => {
    if (!hasPermission(user, "system.read")) {
      sseRef.current?.close();
      setIsConnected(false);
      return;
    }
    let disposed = false;

    const socialPostToFeedEvent = (post: LiveSocialPost, timestamp?: string): FeedEvent => {
      const headline =
        post.title?.trim() ||
        post.content?.trim().slice(0, 120) ||
        `New post from ${post.source}`;

      return {
        timestamp: timestamp || post.publish_time || new Date().toISOString(),
        type: "social_post",
        message: `${post.source} · ${post.author || "Unknown author"}: ${headline}`,
        data: post,
      };
    };

    const appendFeedEvent = (feedEvent: FeedEvent, dedupeId?: string) => {
      const append = (current: FeedEvent[]) => [
        feedEvent,
        ...current.filter(
          (item) =>
            !dedupeId ||
            item.type !== feedEvent.type ||
            item.data?.post_id !== dedupeId,
        ),
      ].slice(0, 50);

      if (streamPausedRef.current) {
        setBufferedFeed(append);
      } else {
        setFeed(append);
      }
    };

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
          setLiveSocialAlerts({
            crisis,
            viral,
            timestamp: payload.timestamp || new Date().toISOString(),
          });
          const feedEvent: FeedEvent = {
            timestamp: payload.timestamp || new Date().toISOString(),
            type: "social_alerts",
            message: `${crisis.length} crisis alert${crisis.length === 1 ? "" : "s"} · ${viral.length} viral post${viral.length === 1 ? "" : "s"}`,
            data: { crisis, viral },
          };
          appendFeedEvent(feedEvent);
        } catch {}
      });
      es.addEventListener("social_post", (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type !== "social_post" || !payload.post?.post_id) return;
          const post = payload.post as LiveSocialPost;
          setLiveSocialPosts((current) => {
            const withoutDuplicate = current.filter(
              (item) => item.post_id !== post.post_id,
            );
            return [post, ...withoutDuplicate].slice(0, 100);
          });

          appendFeedEvent(
            socialPostToFeedEvent(post, payload.timestamp),
            post.post_id,
          );
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
    void apiFetch<any>(`${API_BASE}/social/feed?limit=20`)
      .then((result) => {
        if (disposed || !Array.isArray(result.posts)) return;

        const snapshotEvents = result.posts
          .filter((post: LiveSocialPost) => post?.post_id)
          .map((post: LiveSocialPost) => socialPostToFeedEvent(post));

        setFeed((current) => {
          const existingPostIds = new Set(
            current
              .filter((item) => item.type === "social_post")
              .map((item) => item.data?.post_id)
              .filter(Boolean),
          );
          const unseenSnapshotEvents = snapshotEvents.filter(
            (item: FeedEvent) => !existingPostIds.has(item.data?.post_id),
          );
          return [...current, ...unseenSnapshotEvents].slice(0, 50);
        });
      })
      .catch(() => {
        // SSE remains the primary source; an unavailable snapshot must not
        // mark an otherwise healthy realtime connection as disconnected.
      });

    return () => {
      disposed = true;
      sseRef.current?.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    };
  }, [user]);

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

  const navigationItems: DashboardNavigationItem[] = dashboardMode === "news"
    ? [
        { id: "overview", label: "Overview", icon: <Activity size={18} /> },
        { id: "sentiment", label: "Sentiment", icon: <ThumbsUp size={18} /> },
        { id: "entities", label: "Entities & NLP", icon: <Hash size={18} /> },
        { id: "network", label: "Network", icon: <Share2 size={18} /> },
        { id: "articles", label: "Latest News", icon: <BookOpen size={18} /> },
        { id: "foryou", label: "For You", icon: <Sparkles size={18} />, featured: true },
        { id: "intelligence", label: "My Intelligence", icon: <BellRing size={18} />, featured: true },
        { id: "events", label: "Events", icon: <Layers3 size={18} /> },
        { id: "insights", label: "Advanced Insights", icon: <BarChart3 size={18} /> },
        { id: "briefings", label: "Briefings & Reports", icon: <ClipboardList size={18} /> },
        { id: "workspaces", label: "Team Workspaces", icon: <Users size={18} /> },
      ]
    : dashboardMode === "social"
      ? [
          { id: "overview", label: "Overview", icon: <Activity size={18} /> },
          { id: "sentiment", label: "Sentiment", icon: <ThumbsUp size={18} /> },
          { id: "debates", label: "Top Debates", icon: <MessageSquare size={18} /> },
          { id: "influencers", label: "Top Influencers", icon: <Users size={18} /> },
          { id: "live_social", label: "Live Feed", icon: <Radio size={18} /> },
        ]
      : [
          ...(hasPermission(user, "system.read") ? [
            { id: "admin_dashboard", label: "Admin Dashboard", icon: <Activity size={18} /> },
            { id: "articles", label: "System Articles", icon: <BookOpen size={18} /> },
            { id: "stream", label: "Live Stream Debug", icon: <Radio size={18} /> },
          ] : []),
          ...(hasPermission(user, "alerts.read") ? [
            { id: "alerts", label: "System Alerts", icon: <AlertTriangle size={18} /> },
          ] : []),
          ...(hasPermission(user, "crawler.read") ? [
            { id: "crawlers", label: "Crawlers", icon: <DatabaseZap size={18} /> },
          ] : []),
          ...(hasPermission(user, "system.read") ? [
            { id: "architecture", label: "Architecture", icon: <Server size={18} /> },
            { id: "data_operations", label: "Data Operations", icon: <HardDrive size={18} /> },
          ] : []),
          ...(canManageUsers ? [
            { id: "users", label: "User Access", icon: <UserCog size={18} /> },
          ] : []),
        ];

  const activeNavigationLabel = navigationItems.find((item) => item.id === activeTab)?.label ?? "Dashboard";
  const workspaceLabel = dashboardMode === "news" ? "Official News" : dashboardMode === "social" ? "Social Media" : "Operations";
  const canFilterCurrentView = dashboardMode !== "admin" && Boolean(TAB_FILTER_CAPABILITIES[activeTab]);

  const handleNavigationChange = (nextTab: string) => {
    setActiveTab(nextTab);
    if (nextTab === "articles") {
      setPage(1);
      setArticleAlertFilter(null);
    }
  };

  return (
    <div className="container">
      {user && (
        <header className="dashboard-header">
          <div>
            <h1>NewsPulse Intelligence</h1>
            <p className="subtitle">Real-time Data Pipeline Dashboard</p>
          </div>
          <div className="header-controls">
            <div className="mode-toggle" aria-label="Dashboard workspace">
              <button
                type="button"
                className={dashboardMode === "news" ? "active news" : ""}
                aria-pressed={dashboardMode === "news"}
                onClick={() => {
                  setDashboardMode("news");
                  setSelectedSource("");
                  setActiveTab("overview");
                }}
              >
                <Newspaper size={16} /> Official News
              </button>
              <button
                type="button"
                className={dashboardMode === "social" ? "active social" : ""}
                aria-pressed={dashboardMode === "social"}
                onClick={() => {
                  setDashboardMode("social");
                  setSelectedSource("");
                  setActiveTab("overview");
                }}
              >
                <MessageSquare size={16} /> Social Media
              </button>
              {canAccessOperations && (
                <button
                  type="button"
                  className={dashboardMode === "admin" ? "active operations" : ""}
                  aria-pressed={dashboardMode === "admin"}
                  onClick={() => {
                    setDashboardMode("admin");
                    setSelectedSource("");
                    setActiveTab(hasPermission(user, "system.read") ? "admin_dashboard" : hasPermission(user, "crawler.read") ? "crawlers" : "alerts");
                  }}
                >
                  <Settings size={16} /> Operations
                </button>
              )}
            </div>
            <div className="header-account print-hide">
              <AccountAvatar user={user} onChange={setUser} onLogout={handleLogout} />
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
          <section className="dashboard-toolbar" aria-label="Dashboard controls">
            <div className="toolbar-context">
              <span className={`workspace-indicator ${dashboardMode}`}>{workspaceLabel}</span>
              <h2>{activeNavigationLabel}</h2>
            </div>
            <div className="toolbar-actions print-hide">
              {dashboardMode === "admin" ? (
                <label className="toolbar-filter">
                  <span>View</span>
                  <select
                    aria-label="Operations view"
                    value={activeTab}
                    onChange={(event) => handleNavigationChange(event.target.value)}
                  >
                    {navigationItems.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                  </select>
                </label>
              ) : canFilterCurrentView ? (
                <label className="toolbar-filter">
                  <span>{dashboardMode === "news" ? "Source" : "Platform"}</span>
                  <select
                    aria-label={dashboardMode === "news" ? "News source" : "Social platform"}
                    value={selectedSource}
                    onChange={(event) => setSelectedSource(event.target.value)}
                  >
                    <option value="">All sources</option>
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
                </label>
              ) : null}
              <button type="button" className="export-button" onClick={() => void handleExportPdf()}>
                <Download size={16} /> Export PDF
              </button>
            </div>
          </section>

          {/* Admin sidebar layout */}
          {dashboardMode === "admin" && canAccessOperations && (
            <div className="admin-layout">
              <DashboardSidebar
                activeId={activeTab}
                ariaLabel="Admin navigation"
                items={navigationItems}
                onChange={handleNavigationChange}
              />
              <div className="admin-content">

          {activeTab === "admin_dashboard" && dashboardMode === "admin" && hasPermission(user, "system.read") && (
            <AdminView
              adminLatency={adminLatency}
              adminClickbait={adminClickbait}
              adminUsers={adminUsers}
              adminHealth={adminHealth}
              adminOperations={adminOperations}
              adminAlertMetrics={adminAlertMetrics}
              updatedAt={dataUpdatedAt}
            />
          )}

          {activeTab === "articles" && dashboardMode === "admin" && hasPermission(user, "system.read") && (
            <ArticlesView
              title="System Articles"
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
              canExportCSV={canExportFull}
            />
          )}

          {activeTab === "stream" && dashboardMode === "admin" && hasPermission(user, "system.read") && (
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

          {activeTab === "alerts" && dashboardMode === "admin" && hasPermission(user, "alerts.read") && (
            <AlertsPanel
              canManage={canManageAlerts}
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

          {activeTab === "crawlers" && dashboardMode === "admin" && hasPermission(user, "crawler.read") && (
            <CrawlerManagementView canRun={hasPermission(user, "crawler.run")} canCreateMock={hasPermission(user, "mock_data.create")} />
          )}

          {activeTab === "users" && dashboardMode === "admin" && canManageUsers && (
            <UserManagementView currentUserId={user?.id} />
          )}

          {activeTab === "architecture" && dashboardMode === "admin" && hasPermission(user, "system.read") && (
            <ArchitectureView />
          )}

          {activeTab === "data_operations" && dashboardMode === "admin" && hasPermission(user, "system.read") && (
            <DataOperationsView canMutate={hasPermission(user, "crawler.run")} />
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

              </div>
            </div>
          )}

          {/* News sidebar layout */}
          {dashboardMode === "news" && (
            <div className="admin-layout">
              <DashboardSidebar
                activeId={activeTab}
                ariaLabel="News navigation"
                items={navigationItems}
                onChange={handleNavigationChange}
              />
              <div className="admin-content">

          {activeTab === "overview" && dashboardMode === "news" && (
            <OverviewNewsView
              overviewData={overviewData}
              chartData={chartData}
              sourceData={sourceData}
              activeCard={activeCard}
              setActiveCard={setActiveCard}
              exportToCSV={exportToCSV}
              canExportCSV={canExportFull}
              updatedAt={dataUpdatedAt}
            />
          )}

          {activeTab === "sentiment" && dashboardMode === "news" && (
            <SentimentView
              sentimentDist={sentimentDist}
              sentimentTimeline={sentimentTimeline}
              sentimentSources={sentimentSources}
              sentimentCoverage={sentimentCoverage}
              updatedAt={dataUpdatedAt}
            />
          )}

          {activeTab === "entities" && dashboardMode === "news" && (
            <EntitiesView
              entitiesData={entitiesData}
              trendingKeywords={trendingKeywords}
              entityTypeDist={entityTypeDist}
              entitySentiment={entitySentiment}
              updatedAt={dataUpdatedAt}
            />
          )}

          {activeTab === "network" && dashboardMode === "news" && (
            <NetworkView knowledgeGraph={knowledgeGraph} updatedAt={dataUpdatedAt} />
          )}

          {activeTab === "articles" && dashboardMode === "news" && (
            <ArticlesView
              title="Latest Articles"
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
              canExportCSV={canExportFull}
            />
          )}

          {activeTab === "foryou" && dashboardMode === "news" && (
            <ForYouView
              forYouArticles={forYouArticles}
              trackClick={trackClick}
              timeAgo={timeAgo}
            />
          )}

          {activeTab === "intelligence" && dashboardMode === "news" && (
            <IntelligenceView onAskWatchlist={(item) => {
              setChatIntelligenceScope({ watchlist_id: item.id, label: item.name });
              setChatOpen(true);
            }} onRunQuery={(item) => {
              setArticleSearchInput(String(item.query || ""));
              setArticleSearchQuery(String(item.query || ""));
              setArticleFilters({
                ...EMPTY_ARTICLE_FILTERS,
                source: String(item.source || ""),
                category: String(item.category || ""),
                entity: String(item.entity || ""),
                keyword: String(item.keyword || ""),
                sentiment: String(item.sentiment || ""),
              });
              setPage(1);
              setActiveTab("articles");
            }} />
          )}

          {activeTab === "events" && dashboardMode === "news" && (
            <EventsView onAsk={(event) => {
              setChatIntelligenceScope({ event_id: event.event_id, label: event.title });
              setChatOpen(true);
            }} />
          )}

          {activeTab === "insights" && dashboardMode === "news" && <InsightsView />}
          {activeTab === "briefings" && dashboardMode === "news" && <BriefingsView />}
          {activeTab === "workspaces" && dashboardMode === "news" && <WorkspacesView currentEmail={user.email} />}

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

              </div>
            </div>
          )}

          {/* Social sidebar layout */}
          {dashboardMode === "social" && (
            <div className="admin-layout">
              <DashboardSidebar
                activeId={activeTab}
                ariaLabel="Social navigation"
                items={navigationItems}
                onChange={handleNavigationChange}
              />
              <div className="admin-content">

          {activeTab === "overview" && dashboardMode === "social" && (
            <OverviewSocialView
              overviewData={overviewData}
              activeCard={activeCard}
              setActiveCard={setActiveCard}
              updatedAt={dataUpdatedAt}
            />
          )}

          {activeTab === "sentiment" && dashboardMode === "social" && (
            <SentimentView
              sentimentDist={sentimentDist}
              sentimentTimeline={sentimentTimeline}
              sentimentSources={sentimentSources}
              sentimentCoverage={sentimentCoverage}
              updatedAt={dataUpdatedAt}
            />
          )}

          {activeTab === "debates" && dashboardMode === "social" && (
            <DebatesView overviewData={overviewData} />
          )}

          {activeTab === "influencers" && dashboardMode === "social" && (
            <SocialInfluencersView influencers={socialInfluencers} />
          )}

          {activeTab === "live_social" && dashboardMode === "social" && (
            <LiveSocialFeedView
              posts={liveSocialPosts}
              connected={isConnected}
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

              </div>
            </div>
          )}
          {hasPermission(user, "chat.use") && (
            <>
              <button
                ref={chatLauncherRef}
                type="button"
                className="chat-launcher"
                aria-label={chatOpen ? "Đóng Chat Assistant" : "Mở Chat Assistant"}
                aria-controls="chat-assistant-panel"
                aria-expanded={chatOpen}
                title={chatOpen ? "Đóng Chat Assistant" : "Mở Chat Assistant"}
                onClick={() => setChatOpen((current) => !current)}
              >
                <Image src="/chatbot-robot.png" alt="" width={40} height={40} aria-hidden="true" />
              </button>
              <div
                id="chat-assistant-panel"
                className="chat-drawer"
                role="dialog"
                aria-label="Chat Assistant"
                aria-modal="false"
                hidden={!chatOpen}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    setChatOpen(false);
                    chatLauncherRef.current?.focus();
                  }
                }}
              >
                <ChatView
                  open={chatOpen}
                  intelligenceScope={chatIntelligenceScope}
                  onClearScope={() => setChatIntelligenceScope(null)}
                  onClose={() => { setChatOpen(false); chatLauncherRef.current?.focus(); }}
                />
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell, Legend
} from 'recharts';
import { Activity, BookOpen, BarChart2, Radio, ThumbsUp, Hash, Users, MessageSquare, AlertTriangle, Share2 } from 'lucide-react';
import KnowledgeGraph from '@/components/KnowledgeGraph';
import AlertsPanel from '@/components/AlertsPanel';

const API_BASE = 'http://localhost:8001/api/v1';

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
  const [activeTab, setActiveTab] = useState('overview');
  const [dashboardMode, setDashboardMode] = useState<'news' | 'social' | 'admin'>('news');
  const [selectedSource, setSelectedSource] = useState<string>('');
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
  const [knowledgeGraph, setKnowledgeGraph] = useState<any>({nodes: [], links: []});

  const sseRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);

  const [activeCard, setActiveCard] = useState<number | null>(null);
  const [user, setUser] = useState<any>(null);
  const [showAuth, setShowAuth] = useState(false);
  const [authMode, setAuthMode] = useState<'login'|'register'>('login');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authName, setAuthName] = useState('');
  const [authModalError, setAuthModalError] = useState<string | null>(null);
  const [forYouArticles, setForYouArticles] = useState<any[]>([]);

  // Auth Functions
  const handleAuth = async (e: any) => {
    e.preventDefault();
    setAuthModalError(null);
    try {
      const url = authMode === 'login' ? `${API_BASE}/auth/login` : `${API_BASE}/auth/register`;
      const body = authMode === 'login' ? { email: authEmail, password: authPassword } : { email: authEmail, password: authPassword, full_name: authName };
      
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Auth failed');
      
      if (authMode === 'login') {
        localStorage.setItem('token', data.access_token);
        setUser(data.user);
        setShowAuth(false);
      } else {
        setAuthMode('login');
        setAuthModalError('Registered successfully. Please login.');
      }
    } catch (err: any) {
      setAuthModalError(err.message);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setUser(null);
    setActiveTab('overview');
  };

  const fetchForYou = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    try {
      const res = await fetch(`${API_BASE}/recommendations/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      if (res.ok) setForYouArticles(data.articles || []);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const trackClick = async (article_hash: string) => {
    const token = localStorage.getItem('token');
    if (!token || !article_hash) return;
    try {
      await fetch(`${API_BASE}/recommendations/interact?article_hash=${article_hash}&interaction_type=click`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
    } catch (e) {}
  };

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      setUser(JSON.parse(localStorage.getItem('user_cache') || '{"email": "user@example.com"}')); 
    }
  }, []);


  // Smart fetch: only load data relevant to the active tab
  const fetchOverview = useCallback(async () => {
    const sourceParam = selectedSource ? `&source=${selectedSource}` : '';
    if (dashboardMode === 'news') {
      const result = await safeFetch(`${API_BASE}/overview?time_range=all${sourceParam}`);
      setOverviewData(result);
    } else if (dashboardMode === 'social') {
      const result = await safeFetch(`${API_BASE}/social/overview?time_range=all${sourceParam}`);
      setOverviewData(result);
    }
  }, [dashboardMode, selectedSource]);

  const fetchSentiment = useCallback(async () => {
    const sourceParam = selectedSource ? `?source=${selectedSource}` : '';
    if (dashboardMode === 'news') {
      const results = await Promise.allSettled([
        safeFetch(`${API_BASE}/sentiment/distribution${sourceParam}`),
        safeFetch(`${API_BASE}/sentiment/timeline${sourceParam}`),
        safeFetch(`${API_BASE}/sentiment/sources${sourceParam}`),
      ]);
      if (results[0].status === 'fulfilled') setSentimentDist(results[0].value.data || []);
      if (results[1].status === 'fulfilled') setSentimentTimeline(results[1].value.data || []);
      if (results[2].status === 'fulfilled') setSentimentSources(results[2].value.data || []);
    } else if (dashboardMode === 'social') {
      const result = await safeFetch(`${API_BASE}/social/sentiment${sourceParam.replace('?', '&time_range=all&').replace(/^&/, '?')}`);
      setSentimentDist(result.sentiment_distribution || []);
      setSentimentTimeline(result.sentiment_timeline || []);
      setSentimentSources(result.sentiment_by_source || []);
    }
  }, [selectedSource, dashboardMode]);

  const fetchDebates = useCallback(async () => {
    const sourceParam = selectedSource ? `&source=${selectedSource}` : '';
    if (dashboardMode === 'social') {
      const result = await safeFetch(`${API_BASE}/social/debates?time_range=all${sourceParam}`);
      setOverviewData((prev: any) => ({ ...prev, top_debates: result.top_debates }));
    }
  }, [selectedSource, dashboardMode]);

  const fetchAdmin = useCallback(async () => {
    const token = localStorage.getItem('token');
    if (!token) return;
    const headers = { 'Authorization': `Bearer ${token}` };
    const [latencyRes, clickbaitRes, usersRes] = await Promise.all([
      fetch(`${API_BASE}/admin/metrics/latency`, { headers }).then(r => r.json()),
      fetch(`${API_BASE}/admin/metrics/volume`, { headers }).then(r => r.json()),
      fetch(`${API_BASE}/admin/metrics/users`, { headers }).then(r => r.json())
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
    if (results[0].status === 'fulfilled') setEntitiesData(results[0].value || []);
    if (results[1].status === 'fulfilled') setTrendingKeywords(results[1].value || []);
    if (results[2].status === 'fulfilled') setEntityTypeDist(results[2].value || []);
    if (results[3].status === 'fulfilled') setEntitySentiment(results[3].value || []);
  }, [selectedSource, dashboardMode]);

  const fetchNetwork = useCallback(async () => {
    const result = await safeFetch(`${API_BASE}/entities/knowledge-graph`);
    setKnowledgeGraph(result);
  }, [selectedSource, dashboardMode]);

  const fetchArticles = useCallback(async (p: number) => {
    const result = await safeFetch(`${API_BASE}/articles?page=${p}&page_size=20`);
    setArticles(result.data || []);
    setArticlesMeta(result);
  }, [selectedSource, dashboardMode]);

  // Tab-aware polling
  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        if (activeTab === 'overview') await fetchOverview();
        else if (activeTab === 'sentiment') await fetchSentiment();
        else if (activeTab === 'entities') await fetchEntities();
        else if (activeTab === 'network') await fetchNetwork();
        else if (activeTab === 'articles') await fetchArticles(page);
        else if (activeTab === 'foryou') await fetchForYou();
        else if (activeTab === 'debates') await fetchDebates();
        else if (activeTab === 'admin_dashboard') await fetchAdmin();
        if (!cancelled) setApiError(null);
      } catch (err: any) {
        if (!cancelled) setApiError('Mất kết nối tới API server');
      }
    };

    poll();
    const intervalId = setInterval(poll, 15000);
    return () => { cancelled = true; clearInterval(intervalId); };
  }, [activeTab, page, fetchOverview, fetchSentiment, fetchEntities, fetchNetwork, fetchArticles, fetchForYou, fetchDebates, fetchAdmin]);

  // SSE with auto-reconnect
  useEffect(() => {
    const connectSSE = () => {
      if (sseRef.current) sseRef.current.close();

      const es = new EventSource(`${API_BASE}/stream/`);
      sseRef.current = es;

      es.onopen = () => setIsConnected(true);
      es.addEventListener('update', (event) => {
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

  const chartData = overviewData?.articles_by_hour?.map((row: any) => ({
    time: `${row.hour}:00`,
    count: row.count
  })) || [];

  const sourceData = overviewData?.category_distribution?.map((row: any) => ({
    name: row.category,
    count: row.count
  })) || [];

  return (
    <div className="container">
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1>NewsPulse Intelligence</h1>
          <p className="subtitle">Real-time Data Pipeline Dashboard</p>
        </div>
        <div style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>
          <div className="mode-toggle" style={{ display: 'flex', background: 'rgba(255,255,255,0.05)', borderRadius: '20px', padding: '4px', border: '1px solid rgba(255,255,255,0.1)' }}>
            <button 
              onClick={() => { setDashboardMode('news'); setSelectedSource(''); setActiveTab('overview'); }}
              style={{ padding: '6px 16px', border: 'none', background: dashboardMode === 'news' ? '#3b82f6' : 'transparent', color: 'white', borderRadius: '16px', cursor: 'pointer', fontWeight: 600, transition: 'all 0.3s' }}
            >
              📰 Official News
            </button>
            <button 
              onClick={() => { setDashboardMode('social'); setSelectedSource(''); setActiveTab('overview'); }}
              style={{ padding: '6px 16px', border: 'none', background: dashboardMode === 'social' ? '#8b5cf6' : 'transparent', color: 'white', borderRadius: '16px', cursor: 'pointer', fontWeight: 600, transition: 'all 0.3s' }}
            >
              💬 Social Media
            </button>
            {user?.role === 'admin' && (
              <button 
                onClick={() => { setDashboardMode('admin'); setSelectedSource(''); setActiveTab('admin_dashboard'); }}
                style={{ padding: '6px 16px', border: 'none', background: dashboardMode === 'admin' ? '#ef4444' : 'transparent', color: 'white', borderRadius: '16px', cursor: 'pointer', fontWeight: 600, transition: 'all 0.3s' }}
              >
                ⚙️ Admin
              </button>
            )}
          </div>
          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ background: '#3b82f6', borderRadius: '50%', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
                {user.email[0].toUpperCase()}
              </div>
              <button onClick={handleLogout} style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', padding: '6px 12px', borderRadius: '8px', color: '#fff', cursor: 'pointer' }}>Logout</button>
            </div>
          ) : (
            <button onClick={() => setShowAuth(true)} style={{ background: '#3b82f6', border: 'none', padding: '8px 16px', borderRadius: '8px', color: '#fff', cursor: 'pointer', fontWeight: 600 }}>Login</button>
          )}
          <select 
            value={selectedSource} 
            onChange={(e) => setSelectedSource(e.target.value)}
            style={{ padding: '8px 16px', borderRadius: '8px', background: 'rgba(15, 23, 42, 0.8)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', outline: 'none', cursor: 'pointer' }}
          >
            <option value="">All Sources</option>
            {dashboardMode === 'news' ? (
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
        </div>
      </header>

      <div className="tabs">
        {dashboardMode === 'news' && (
          <>
            <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
              <Activity size={18} /> Overview
            </button>
            <button className={`tab-btn ${activeTab === 'sentiment' ? 'active' : ''}`} onClick={() => setActiveTab('sentiment')}>
              <ThumbsUp size={18} /> Sentiment
            </button>
            <button className={`tab-btn ${activeTab === 'entities' ? 'active' : ''}`} onClick={() => setActiveTab('entities')}>
              <Hash size={18} /> Entities & NLP
            </button>
            <button className={`tab-btn ${activeTab === 'network' ? 'active' : ''}`} onClick={() => setActiveTab('network')}>
              <Share2 size={18} /> Network
            </button>
            <button className={`tab-btn ${activeTab === 'articles' ? 'active' : ''}`} onClick={() => { setActiveTab('articles'); setPage(1); }}>
              <BookOpen size={18} /> Latest News
            </button>
            {user && (
              <button className={`tab-btn ${activeTab === 'foryou' ? 'active' : ''}`} onClick={() => setActiveTab('foryou')} style={{ background: 'linear-gradient(90deg, #8b5cf6, #3b82f6)', color: 'white' }}>
                ✨ For You
              </button>
            )}
          </>
        )}
        
        {dashboardMode === 'social' && (
          <>
            <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
              <Activity size={18} /> Overview
            </button>
            <button className={`tab-btn ${activeTab === 'sentiment' ? 'active' : ''}`} onClick={() => setActiveTab('sentiment')}>
              <ThumbsUp size={18} /> Sentiment
            </button>
            <button className={`tab-btn ${activeTab === 'debates' ? 'active' : ''}`} onClick={() => setActiveTab('debates')}>
              <MessageSquare size={18} /> Top Debates
            </button>
          </>
        )}

        {dashboardMode === 'admin' && (
          <>
            <button className={`tab-btn ${activeTab === 'admin_dashboard' ? 'active' : ''}`} onClick={() => setActiveTab('admin_dashboard')}>
              <Activity size={18} /> Admin Dashboard
            </button>
            <button className={`tab-btn ${activeTab === 'articles' ? 'active' : ''}`} onClick={() => { setActiveTab('articles'); setPage(1); }}>
              <BookOpen size={18} /> System Articles
            </button>
            <button className={`tab-btn ${activeTab === 'stream' ? 'active' : ''}`} onClick={() => setActiveTab('stream')}>
              <Radio size={18} /> Live Stream Debug
            </button>
            <button className={`tab-btn ${activeTab === 'alerts' ? 'active' : ''}`} onClick={() => setActiveTab('alerts')}>
              <AlertTriangle size={18} /> System Alerts
            </button>
          </>
        )}
      </div>

      {activeTab === 'overview' && dashboardMode === 'news' && (
        <>
          <div className="overview-grid">
            {overviewData?.kpi_cards?.map((kpi: any, i: number) => {
              let details = null;
              if (i === 0 && overviewData.source_speed) {
                details = (
                  <ul className="metric-details-list">
                    {overviewData.source_speed.map((s: any) => (
                      <li key={s.source}>
                        <span style={{ textTransform: 'capitalize' }}>{s.source}</span>
                        <strong>{s.article_count}</strong>
                      </li>
                    ))}
                  </ul>
                );
              } else if (i === 1 && overviewData.source_speed) {
                details = (
                  <ul className="metric-details-list">
                    {overviewData.source_speed.map((s: any) => (
                      <li key={s.source}>
                        <span style={{ textTransform: 'capitalize' }}>{s.source}</span>
                        <span style={{ color: 'var(--accent-green)', fontSize: '0.8rem' }}>● Hoạt động</span>
                      </li>
                    ))}
                  </ul>
                );
              } else if (i === 2 && overviewData.category_distribution) {
                const total = overviewData.category_distribution.reduce((acc: number, c: any) => acc + c.count, 0) || 1;
                details = (
                  <ul className="metric-details-list">
                    {overviewData.category_distribution.slice(0, 5).map((c: any) => (
                      <li key={c.category}>
                        <span style={{ textTransform: 'capitalize' }}>{c.category}</span>
                        <span>
                          <strong>{c.count}</strong>
                          <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: '6px' }}>
                            ({Math.round((c.count / total) * 100)}%)
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                );
              } else if (i === 3 && overviewData.source_speed) {
                details = (
                  <ul className="metric-details-list">
                    {overviewData.source_speed.filter((s: any) => s.avg_latency_min > 0).map((s: any) => (
                      <li key={s.source}>
                        <span style={{ textTransform: 'capitalize' }}>{s.source}</span>
                        <strong>{s.avg_latency_min.toFixed(1)} min</strong>
                      </li>
                    ))}
                  </ul>
                );
              }

              return (
                <div 
                  key={i} 
                  className={`glass-panel metric-card ${activeCard === i ? 'expanded' : ''}`}
                  onClick={() => setActiveCard(activeCard === i ? null : i)}
                >
                  <div className="metric-content" style={{ display: activeCard === i ? 'none' : 'block' }}>
                    <div className="metric-label">{kpi.label}</div>
                    <div className="metric-value">{kpi.value}</div>
                    <div className="metric-hint">Click để xem chi tiết</div>
                  </div>
                  {activeCard === i && (
                    <div className="metric-details">
                      <div className="metric-label" style={{ marginBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '4px' }}>
                        {kpi.label} (Chi tiết)
                      </div>
                      {details}
                    </div>
                  )}
                </div>
              );
            })}
            {!overviewData?.kpi_cards && (
              <div style={{ color: 'var(--text-muted)' }}>Loading metrics...</div>
            )}
          </div>

          <div className="charts-grid">
            <div className="glass-panel">
              <div className="panel-header">
                <div className="panel-title"><BarChart2 size={20} /> Publication Trend (24h)</div>
              </div>
              <div style={{ height: 300, width: '100%' }}>
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                      <defs>
                        <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} />
                      <YAxis stroke="#94a3b8" fontSize={12} />
                      <Tooltip
                        contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }}
                        itemStyle={{ color: '#fff' }}
                      />
                      <Area type="monotone" dataKey="count" stroke="#3b82f6" fillOpacity={1} fill="url(#colorCount)" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                    No trend data available
                  </div>
                )}
              </div>
            </div>

            <div className="glass-panel">
              <div className="panel-header">
                <div className="panel-title"><Activity size={20} /> Category Distribution</div>
              </div>
              <div style={{ height: 300, width: '100%' }}>
                {sourceData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={sourceData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} />
                      <YAxis stroke="#94a3b8" fontSize={12} />
                      <Tooltip
                        cursor={{fill: 'rgba(255,255,255,0.05)'}}
                        contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }}
                      />
                      <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                    No source data available
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}
      {activeTab === 'overview' && dashboardMode === 'social' && (
        <>
          <div className="overview-grid">
            {overviewData?.kpi_cards?.map((kpi: any, i: number) => {
              let details = null;
              if (i === 0 && overviewData.source_distribution) {
                details = (
                  <ul className="metric-details-list">
                    {overviewData.source_distribution.map((s: any) => (
                      <li key={s.source}>
                        <span style={{ textTransform: 'capitalize' }}>{s.source}</span>
                        <strong>{s.count}</strong>
                      </li>
                    ))}
                  </ul>
                );
              } else if (i === 1 && overviewData.likes_distribution) {
                details = (
                  <ul className="metric-details-list">
                    {overviewData.likes_distribution.map((s: any) => (
                      <li key={s.source}>
                        <span style={{ textTransform: 'capitalize' }}>{s.source}</span>
                        <strong>{s.count}</strong>
                      </li>
                    ))}
                  </ul>
                );
              } else if (i === 2 && overviewData.replies_distribution) {
                details = (
                  <ul className="metric-details-list">
                    {overviewData.replies_distribution.map((s: any) => (
                      <li key={s.source}>
                        <span style={{ textTransform: 'capitalize' }}>{s.source}</span>
                        <strong>{s.count}</strong>
                      </li>
                    ))}
                  </ul>
                );
              } else if (i === 3 && overviewData.source_distribution) {
                details = (
                  <ul className="metric-details-list">
                    {overviewData.source_distribution.map((s: any) => (
                      <li key={s.source}>
                        <span style={{ textTransform: 'capitalize' }}>{s.source}</span>
                        <span style={{ color: 'var(--accent-green)', fontSize: '0.8rem' }}>● Active</span>
                      </li>
                    ))}
                  </ul>
                );
              }
              
              return (
                <div 
                  key={i} 
                  className={`glass-panel metric-card ${activeCard === i + 20 ? 'expanded' : ''}`}
                  onClick={() => setActiveCard(activeCard === i + 20 ? null : i + 20)}
                >
                  <div className="metric-content" style={{ display: activeCard === i + 20 ? 'none' : 'block' }}>
                    <div className="metric-label">{kpi.label}</div>
                    <div className="metric-value">{kpi.value}</div>
                    <div className="metric-hint">Click để xem chi tiết</div>
                  </div>
                  {activeCard === i + 20 && (
                    <div className="metric-details">
                      <div className="metric-label" style={{ marginBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '4px' }}>
                        {kpi.label} (Chi tiết)
                      </div>
                      {details}
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="charts-grid">
            <div className="glass-panel" style={{ gridColumn: '1 / -1' }}>
              <div className="panel-header">
                <div className="panel-title"><Activity size={20} /> Engagement Timeline</div>
              </div>
              <div style={{ height: 300, width: '100%' }}>
                {overviewData?.engagement_timeline?.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={overviewData.engagement_timeline}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} />
                      <YAxis stroke="#94a3b8" fontSize={12} />
                      <Tooltip labelFormatter={(t) => new Date(t as string).toLocaleString()} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} />
                      <Legend />
                      <Line type="monotone" dataKey="Likes" stroke="#3b82f6" strokeWidth={2} dot={false} />
                      <Line type="monotone" dataKey="Replies" stroke="#ec4899" strokeWidth={2} dot={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                    No timeline data available
                  </div>
                )}
              </div>
            </div>
          </div>
        </>
      )}


      {activeTab === 'sentiment' && (
        <div className="charts-grid">
          <div className="glass-panel">
            <div className="panel-header">
              <div className="panel-title"><ThumbsUp size={20} /> Overall Sentiment</div>
            </div>
            <div style={{ height: 300, width: '100%' }}>
              {sentimentDist.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={sentimentDist} dataKey="count" nameKey="sentiment_label" cx="50%" cy="50%" outerRadius={100} label>
                      {sentimentDist.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.sentiment_label === 'Positive' ? 'var(--accent-green)' : entry.sentiment_label === 'Negative' ? '#ef4444' : '#94a3b8'} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} itemStyle={{ color: '#fff' }}/>
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                  No sentiment data available
                </div>
              )}
            </div>
          </div>

          <div className="glass-panel">
            <div className="panel-header">
              <div className="panel-title"><BarChart2 size={20} /> Sentiment by Source</div>
            </div>
            <div style={{ height: 300, width: '100%' }}>
              {sentimentSources.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={sentimentSources}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis dataKey="source" stroke="#94a3b8" fontSize={12} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} />
                    <Legend />
                    <Bar dataKey="Positive" stackId="a" fill="var(--accent-green)" />
                    <Bar dataKey="Neutral" stackId="a" fill="#94a3b8" />
                    <Bar dataKey="Negative" stackId="a" fill="#ef4444" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                  No source sentiment data available
                </div>
              )}
            </div>
          </div>

          <div className="glass-panel" style={{ gridColumn: '1 / -1' }}>
            <div className="panel-header">
              <div className="panel-title"><Activity size={20} /> Sentiment Timeline</div>
            </div>
            <div style={{ height: 300, width: '100%' }}>
              {sentimentTimeline.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={sentimentTimeline}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis dataKey="time" stroke="#94a3b8" fontSize={12} tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip labelFormatter={(t) => new Date(t as string).toLocaleString()} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} />
                    <Legend />
                    <Line type="monotone" dataKey="Positive" stroke="var(--accent-green)" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="Negative" stroke="#ef4444" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="Neutral" stroke="#94a3b8" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                  No timeline data available
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'entities' && (
        <div className="charts-grid" style={{ gridTemplateColumns: 'repeat(3, 1fr)' }}>
          <div className="glass-panel">
            <div className="panel-header">
              <div className="panel-title"><Users size={20} /> Top Entities</div>
            </div>
            <div style={{ height: 400, width: '100%' }}>
              {entitiesData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={entitiesData} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={true} vertical={false} />
                    <XAxis type="number" stroke="#94a3b8" fontSize={12} />
                    <YAxis type="category" dataKey="entity_name" stroke="#94a3b8" fontSize={11} width={150} />
                    <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} />
                    <Bar dataKey="mention_count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                  No entity data available
                </div>
              )}
            </div>
          </div>

          <div className="glass-panel">
            <div className="panel-header">
              <div className="panel-title"><MessageSquare size={20} /> Word Cloud</div>
            </div>
            <div style={{ height: 400, width: '100%', display: 'flex', flexWrap: 'wrap', alignContent: 'center', justifyContent: 'center', gap: '10px', padding: '1rem', overflow: 'hidden' }}>
              {trendingKeywords.length > 0 ? (() => {
                const maxCount = Math.max(...trendingKeywords.map(k => k.count)) || 1;
                const minCount = Math.min(...trendingKeywords.map(k => k.count)) || 0;
                const colors = ['#60a5fa', '#34d399', '#a78bfa', '#f472b6', '#fcd34d', '#38bdf8', '#818cf8'];
                
                return trendingKeywords.map((k, i) => {
                  const size = 12 + ((k.count - minCount) / (maxCount - minCount || 1)) * 32; // 12px to 44px
                  return (
                    <span 
                      key={i} 
                      style={{ 
                        fontSize: `${size}px`, 
                        color: colors[i % colors.length], 
                        fontWeight: size > 24 ? 700 : size > 18 ? 600 : 400,
                        lineHeight: 1,
                        opacity: 0.8 + Math.random() * 0.2,
                        transition: 'transform 0.2s',
                        cursor: 'default'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.1)'}
                      onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
                      title={`Xuất hiện ${k.count} lần`}
                    >
                      {k.keyword}
                    </span>
                  );
                });
              })() : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '100%', color: 'var(--text-muted)' }}>
                  No keyword data available
                </div>
              )}
            </div>
          </div>

          <div className="glass-panel">
            <div className="panel-header">
              <div className="panel-title"><MessageSquare size={20} /> Entity Types</div>
            </div>
            <div style={{ height: 400, width: '100%' }}>
              {entityTypeDist.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={entityTypeDist} dataKey="count" nameKey="entity_type" cx="50%" cy="50%" outerRadius={120} label>
                      {entityTypeDist.map((entry: any, index: number) => {
                        const colors = ['#8b5cf6', '#3b82f6', '#10b981', '#f59e0b', '#ef4444'];
                        return <Cell key={`cell-${index}`} fill={colors[index % colors.length]} />;
                      })}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} itemStyle={{ color: '#fff' }}/>
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                  No type data available
                </div>
              )}
            </div>
          </div>

          <div className="glass-panel" style={{ gridColumn: '1 / -1' }}>
            <div className="panel-header">
              <div className="panel-title"><ThumbsUp size={20} /> Sentiment by Entity</div>
            </div>
            <div style={{ height: 400, width: '100%' }}>
              {entitySentiment.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={entitySentiment} margin={{ bottom: 40 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                    <XAxis dataKey="entity" stroke="#94a3b8" fontSize={12} angle={-45} textAnchor="end" />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} />
                    <Legend verticalAlign="top" />
                    <Bar dataKey="Positive" stackId="a" fill="var(--accent-green)" />
                    <Bar dataKey="Neutral" stackId="a" fill="#94a3b8" />
                    <Bar dataKey="Negative" stackId="a" fill="#ef4444" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                  No entity sentiment data available
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'network' && (
        <div className="glass-panel" style={{ height: '700px', display: 'flex', flexDirection: 'column' }}>
          <div className="panel-header">
            <div className="panel-title"><Share2 size={20} /> Entity Knowledge Graph</div>
          </div>
          <div style={{ flex: 1, position: 'relative' }}>
            <KnowledgeGraph data={knowledgeGraph} />
          </div>
        </div>
      )}

      {activeTab === 'articles' && (
        <div className="glass-panel" style={{ minHeight: '600px' }}>
          <div className="panel-header">
            <div className="panel-title"><BookOpen size={20} /> Latest Articles</div>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Source</th>
                <th>Category</th>
                <th>Published</th>
                <th>Sentiment</th>
              </tr>
            </thead>
            <tbody>
              {articles.map((a, i) => (
                <tr key={i}>
                  <td>
                    <a href={a.url} target="_blank" rel="noreferrer" onClick={() => trackClick(a.url_hash)}>
                      {a.title}
                    </a>
                  </td>
                  <td>
                    <span className={`tag ${a.source?.toLowerCase()}`}>{a.source}</span>
                  </td>
                  <td>{a.category || '-'}</td>
                  <td>{a.publish_date ? timeAgo(a.publish_date) : '-'}</td>
                  <td>
                    <span style={{ color: a.sentiment_score > 0 ? 'var(--accent-green)' : a.sentiment_score < 0 ? '#ef4444' : 'var(--text-muted)' }}>
                      {a.sentiment_score?.toFixed(2) || '0.00'}
                    </span>
                  </td>
                </tr>
              ))}
              {articles.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                    No articles found in the database.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          {articlesMeta.total_pages > 1 && (
            <div className="pagination">
              <button disabled={page <= 1} onClick={() => setPage(p => p - 1)}>← Previous</button>
              <span className="page-info">Page {page} / {articlesMeta.total_pages}</span>
              <button disabled={page >= articlesMeta.total_pages} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          )}
        </div>
      )}

      {activeTab === 'stream' && (
        <div className="glass-panel" style={{ maxWidth: '800px', margin: '0 auto' }}>
          <div className="panel-header">
            <div className="panel-title"><Radio size={20} /> Live Data Feed</div>
            <div className="status-indicator">
              <div className="pulse-dot" style={{ backgroundColor: isConnected ? 'var(--accent-green)' : '#ef4444' }}></div>
              <span style={{ color: isConnected ? 'var(--accent-green)' : '#ef4444' }}>
                {isConnected ? 'Connected to Stream' : 'Reconnecting...'}
              </span>
            </div>
          </div>
          <div className="feed-list">
            {feed.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '4rem 0' }}>
                Waiting for incoming events from the pipeline...
              </div>
            ) : (
              feed.map((event, index) => (
                <div key={index} className="feed-item">
                  <div className="feed-time">
                    {new Date(event.timestamp).toLocaleTimeString()} - {event.type.toUpperCase()}
                  </div>
                  <div className="feed-title">{event.message}</div>
                  {event.data && (
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.5rem', background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '4px' }}>
                      <pre style={{ margin: 0 }}>{JSON.stringify(event.data, null, 2)}</pre>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}



      {activeTab === 'alerts' && (
        <AlertsPanel />
      )}

      {apiError && (
        <div className="error-toast">
          <AlertTriangle size={16} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '0.5rem' }} />
          {apiError}
        </div>
      )}

      {showAuth && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="glass-panel" style={{ width: '400px', padding: '2rem' }}>
            <h2 style={{ marginBottom: '1.5rem', textAlign: 'center' }}>{authMode === 'login' ? 'Welcome Back' : 'Create Account'}</h2>
            {authModalError && (
              <div style={{ padding: '10px', marginBottom: '1rem', background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', borderRadius: '8px', textAlign: 'center', border: '1px solid rgba(239, 68, 68, 0.5)' }}>
                {authModalError}
              </div>
            )}
            <form onSubmit={handleAuth} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {authMode === 'register' && (
                <input type="text" placeholder="Full Name" value={authName} onChange={e => setAuthName(e.target.value)} required style={{ padding: '10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', color: 'white' }} />
              )}
              <input type="email" placeholder="Email" value={authEmail} onChange={e => setAuthEmail(e.target.value)} required style={{ padding: '10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', color: 'white' }} />
              <input type="password" placeholder="Password" value={authPassword} onChange={e => setAuthPassword(e.target.value)} required style={{ padding: '10px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', color: 'white' }} />
              
              <button type="submit" style={{ padding: '10px', borderRadius: '8px', border: 'none', background: '#3b82f6', color: 'white', fontWeight: 'bold', cursor: 'pointer', marginTop: '10px' }}>
                {authMode === 'login' ? 'Login' : 'Register'}
              </button>
            </form>
            <div style={{ marginTop: '1rem', textAlign: 'center', fontSize: '0.9rem' }}>
              <span style={{ color: '#94a3b8', cursor: 'pointer' }} onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}>
                {authMode === 'login' ? "Don't have an account? Register" : "Already have an account? Login"}
              </span>
            </div>
            <button onClick={() => setShowAuth(false)} style={{ position: 'absolute', top: '10px', right: '15px', background: 'transparent', border: 'none', color: 'white', fontSize: '1.2rem', cursor: 'pointer' }}>×</button>
          </div>
        </div>
      )}

      {activeTab === 'foryou' && (
        <div className="glass-panel" style={{ minHeight: '600px' }}>
          <div className="panel-header" style={{ borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '1rem', marginBottom: '1rem' }}>
            <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '1.5rem' }}>
              ✨ Recommended For You
            </div>
            <div style={{ color: '#94a3b8', fontSize: '0.9rem' }}>Tailored news based on your reading history</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
            {forYouArticles.map((a: any, i: number) => (
              <a 
                key={i} 
                href={a.url} 
                target="_blank" 
                rel="noreferrer" 
                onClick={() => trackClick(a.url_hash)}
                style={{ display: 'block', padding: '15px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', textDecoration: 'none', color: 'inherit', border: '1px solid rgba(255,255,255,0.05)', transition: 'transform 0.2s, background 0.2s' }}
                onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.background = 'rgba(255,255,255,0.06)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span className={`tag ${a.source?.toLowerCase()}`}>{a.source}</span>
                  <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>{a.publish_time ? timeAgo(a.publish_time) : '-'}</span>
                </div>
                <h3 style={{ margin: '0 0 10px 0', fontSize: '1.2rem', color: '#fff', lineHeight: 1.4 }}>{a.title}</h3>
                {a.content && <p style={{ margin: 0, color: '#94a3b8', fontSize: '0.95rem', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{a.content}</p>}
              </a>
            ))}
            {forYouArticles.length === 0 && (
              <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
                No recommendations found yet. Read some articles to build your profile!
              </div>
            )}
          </div>
        </div>
      )}
      {activeTab === 'admin_dashboard' && dashboardMode === 'admin' && (
        <>
          <div className="overview-grid">
            <div className={`glass-panel metric-card ${activeCard === 10 ? 'expanded' : ''}`} onClick={() => setActiveCard(activeCard === 10 ? null : 10)}>
              <div className="metric-content" style={{ display: activeCard === 10 ? 'none' : 'block' }}>
                <div className="metric-label">Total Users</div>
                <div className="metric-value">{adminUsers?.total_users || 0}</div>
                <div className="metric-hint">Click để xem chi tiết</div>
              </div>
              {activeCard === 10 && (
                <div className="metric-details">
                  <div className="metric-label" style={{ marginBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '4px' }}>Total Users (Chi tiết)</div>
                  <ul className="metric-details-list">
                    <li><span>Standard Users</span><strong>{adminUsers?.standard_users || 0}</strong></li>
                    <li><span>Admin Users</span><strong style={{color: '#ef4444'}}>{adminUsers?.admin_users || 0}</strong></li>
                  </ul>
                </div>
              )}
            </div>

            <div className={`glass-panel metric-card ${activeCard === 11 ? 'expanded' : ''}`} onClick={() => setActiveCard(activeCard === 11 ? null : 11)}>
              <div className="metric-content" style={{ display: activeCard === 11 ? 'none' : 'block' }}>
                <div className="metric-label">Avg Crawl Latency</div>
                <div className="metric-value">{adminLatency?.avg_latency?.length ? (adminLatency.avg_latency.reduce((a:number,b:number)=>a+b,0)/adminLatency.avg_latency.length).toFixed(1) : 0} m</div>
                <div className="metric-hint">Click để xem chi tiết</div>
              </div>
              {activeCard === 11 && (
                <div className="metric-details">
                  <div className="metric-label" style={{ marginBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '4px' }}>Latency (Chi tiết)</div>
                  <ul className="metric-details-list">
                    {adminLatency?.sources?.slice(0, 5).map((s: string, i: number) => (
                      <li key={s}><span style={{ textTransform: 'capitalize' }}>{s}</span><strong>{adminLatency.avg_latency[i]} m</strong></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className={`glass-panel metric-card ${activeCard === 12 ? 'expanded' : ''}`} onClick={() => setActiveCard(activeCard === 12 ? null : 12)}>
              <div className="metric-content" style={{ display: activeCard === 12 ? 'none' : 'block' }}>
                <div className="metric-label">Total News Articles</div>
                <div className="metric-value">{adminClickbait?.news?.volumes?.length ? adminClickbait.news.volumes.reduce((a:number,b:number)=>a+b,0) : 0}</div>
                <div className="metric-hint">Click để xem chi tiết</div>
              </div>
              {activeCard === 12 && (
                <div className="metric-details">
                  <div className="metric-label" style={{ marginBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '4px' }}>News (Chi tiết)</div>
                  <ul className="metric-details-list">
                    {adminClickbait?.news?.sources?.slice(0, 5).map((s: string, i: number) => (
                      <li key={s}><span style={{ textTransform: 'capitalize' }}>{s}</span><strong>{adminClickbait.news.volumes[i]}</strong></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className={`glass-panel metric-card ${activeCard === 13 ? 'expanded' : ''}`} onClick={() => setActiveCard(activeCard === 13 ? null : 13)}>
              <div className="metric-content" style={{ display: activeCard === 13 ? 'none' : 'block' }}>
                <div className="metric-label">Total Social Posts</div>
                <div className="metric-value">{adminClickbait?.social?.volumes?.length ? adminClickbait.social.volumes.reduce((a:number,b:number)=>a+b,0) : 0}</div>
                <div className="metric-hint">Click để xem chi tiết</div>
              </div>
              {activeCard === 13 && (
                <div className="metric-details">
                  <div className="metric-label" style={{ marginBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '4px' }}>Social (Chi tiết)</div>
                  <ul className="metric-details-list">
                    {adminClickbait?.social?.sources?.slice(0, 5).map((s: string, i: number) => (
                      <li key={s}><span style={{ textTransform: 'capitalize' }}>{s}</span><strong>{adminClickbait.social.volumes[i]}</strong></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            
            <div className={`glass-panel metric-card`}>
              <div className="metric-content">
                <div className="metric-label">System Health</div>
                <div className="metric-value" style={{color: 'var(--accent-green)'}}>Healthy</div>
                <div className="metric-hint">All systems operational</div>
              </div>
            </div>

            <div className={`glass-panel metric-card`}>
              <div className="metric-content">
                <div className="metric-label">System Uptime</div>
                <div className="metric-value">99.9%</div>
                <div className="metric-hint">Hoạt động ổn định</div>
              </div>
            </div>

            <div className={`glass-panel metric-card ${activeCard === 15 ? 'expanded' : ''}`} onClick={() => setActiveCard(activeCard === 15 ? null : 15)}>
              <div className="metric-content" style={{ display: activeCard === 15 ? 'none' : 'block' }}>
                <div className="metric-label">Active News Sources</div>
                <div className="metric-value">{adminClickbait?.news?.sources?.length || 0}</div>
                <div className="metric-hint">Click để xem chi tiết</div>
              </div>
              {activeCard === 15 && (
                <div className="metric-details">
                  <div className="metric-label" style={{ marginBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '4px' }}>Các trang báo</div>
                  <ul className="metric-details-list">
                    {adminClickbait?.news?.sources?.slice(0, 5).map((s: string) => (
                      <li key={s}><span style={{ textTransform: 'capitalize' }}>{s}</span><strong style={{color: 'var(--accent-green)'}}>Active</strong></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className={`glass-panel metric-card ${activeCard === 16 ? 'expanded' : ''}`} onClick={() => setActiveCard(activeCard === 16 ? null : 16)}>
              <div className="metric-content" style={{ display: activeCard === 16 ? 'none' : 'block' }}>
                <div className="metric-label">Active Social Platforms</div>
                <div className="metric-value">{adminClickbait?.social?.sources?.length || 0}</div>
                <div className="metric-hint">Click để xem chi tiết</div>
              </div>
              {activeCard === 16 && (
                <div className="metric-details">
                  <div className="metric-label" style={{ marginBottom: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '4px' }}>Các MXH</div>
                  <ul className="metric-details-list">
                    {adminClickbait?.social?.sources?.slice(0, 5).map((s: string) => (
                      <li key={s}><span style={{ textTransform: 'capitalize' }}>{s}</span><strong style={{color: 'var(--accent-green)'}}>Active</strong></li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>

          <div className="charts-grid">
            <div className="glass-panel" style={{ gridColumn: '1 / -1' }}>
              <div className="panel-header">
                <div className="panel-title"><Activity size={20} /> Crawl Latency by Source</div>
              </div>
              <div style={{ height: 300, width: '100%' }}>
                {adminLatency?.sources?.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={adminLatency.sources.map((s: string, i: number) => ({ source: s, latency: adminLatency.avg_latency[i] }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis dataKey="source" stroke="#94a3b8" fontSize={12} />
                      <YAxis stroke="#94a3b8" fontSize={12} />
                      <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)' }} />
                      <Bar dataKey="latency" fill="#3b82f6" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>No Data</div>
                )}
              </div>
            </div>

            <div className="glass-panel">
              <div className="panel-header">
                <div className="panel-title"><BookOpen size={20} /> News Articles Volume</div>
              </div>
              <div style={{ height: 300, width: '100%' }}>
                {adminClickbait?.news?.sources?.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={adminClickbait.news.sources.map((s: string, i: number) => ({ source: s, total: adminClickbait.news.volumes[i] }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis dataKey="source" stroke="#94a3b8" fontSize={12} />
                      <YAxis stroke="#94a3b8" fontSize={12} />
                      <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)' }} />
                      <Bar dataKey="total" fill="#ef4444" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>No Data</div>
                )}
              </div>
            </div>

            <div className="glass-panel">
              <div className="panel-header">
                <div className="panel-title"><Share2 size={20} /> Social Posts Volume</div>
              </div>
              <div style={{ height: 300, width: '100%' }}>
                {adminClickbait?.social?.sources?.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={adminClickbait.social.sources.map((s: string, i: number) => ({ source: s, total: adminClickbait.social.volumes[i] }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                      <XAxis dataKey="source" stroke="#94a3b8" fontSize={12} />
                      <YAxis stroke="#94a3b8" fontSize={12} />
                      <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)' }} />
                      <Bar dataKey="total" fill="#8b5cf6" />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>No Data</div>
                )}
              </div>
            </div>
            
            <div className="glass-panel" style={{ gridColumn: '1 / -1' }}>
              <div className="panel-header">
                <div className="panel-title"><Users size={20} /> User Roles Distribution</div>
              </div>
              <div style={{ height: 300, width: '100%' }}>
                {adminUsers ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={[{name: 'Standard Users', count: adminUsers.standard_users}, {name: 'Admin Users', count: adminUsers.admin_users}]} dataKey="count" nameKey="name" cx="50%" cy="50%" outerRadius={100} label>
                        <Cell fill="#3b82f6" />
                        <Cell fill="#ef4444" />
                      </Pie>
                      <Tooltip contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} itemStyle={{ color: '#fff' }}/>
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>No Data</div>
                )}
              </div>
            </div>
          </div>
        </>
      )}

      {activeTab === 'debates' && dashboardMode === 'social' && (
        <div className="glass-panel" style={{ marginTop: '20px' }}>
          <div className="panel-header">
            <div className="panel-title"><MessageSquare size={20} /> Top Debates</div>
          </div>
          <div className="stream-container">
            {overviewData?.top_debates?.map((post: any) => (
              <div key={post.post_id} className="feed-item" style={{ borderLeft: `4px solid ${post.sentiment_score > 0.1 ? 'var(--accent-green)' : post.sentiment_score < -0.1 ? '#ef4444' : '#94a3b8'}` }}>
                <div className="feed-header">
                  <span className="feed-type" style={{background: 'rgba(139, 92, 246, 0.2)', color: '#a78bfa'}}>{post.source}</span>
                  <span className="feed-time">{new Date(post.publish_time).toLocaleString()}</span>
                </div>
                <div className="feed-message">
                  <strong>{post.title}</strong>
                  <p style={{ margin: '8px 0', fontSize: '0.9rem', color: '#cbd5e1' }}>{post.content.substring(0, 150)}...</p>
                </div>
                <div style={{ display: 'flex', gap: '15px', marginTop: '10px', fontSize: '0.85rem', color: '#94a3b8' }}>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><ThumbsUp size={14}/> {post.like_count}</span>
                  <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><MessageSquare size={14}/> {post.reply_count} replies</span>
                </div>
              </div>
            ))}
            {!overviewData?.top_debates?.length && (
              <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                No debate data available
              </div>
            )}
          </div>
        </div>
      )}

    </div>
  );
}

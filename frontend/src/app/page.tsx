'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell, Legend
} from 'recharts';
import { Activity, BookOpen, BarChart2, Radio, ThumbsUp, Hash, Users, MessageSquare, AlertTriangle } from 'lucide-react';

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
  const [feed, setFeed] = useState<FeedEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const [overviewData, setOverviewData] = useState<any>(null);
  const [articles, setArticles] = useState<any[]>([]);
  const [articlesMeta, setArticlesMeta] = useState<any>({});
  const [page, setPage] = useState(1);

  const [sentimentDist, setSentimentDist] = useState<any[]>([]);
  const [sentimentTimeline, setSentimentTimeline] = useState<any[]>([]);
  const [sentimentSources, setSentimentSources] = useState<any[]>([]);
  const [entitiesData, setEntitiesData] = useState<any[]>([]);
  const [trendingKeywords, setTrendingKeywords] = useState<any[]>([]);

  const sseRef = useRef<EventSource | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);

  const [activeCard, setActiveCard] = useState<number | null>(null);

  // Smart fetch: only load data relevant to the active tab
  const fetchOverview = useCallback(async () => {
    const result = await safeFetch(`${API_BASE}/overview`);
    setOverviewData(result);
  }, []);

  const fetchSentiment = useCallback(async () => {
    const results = await Promise.allSettled([
      safeFetch(`${API_BASE}/sentiment/distribution`),
      safeFetch(`${API_BASE}/sentiment/timeline`),
      safeFetch(`${API_BASE}/sentiment/sources`),
    ]);
    if (results[0].status === 'fulfilled') setSentimentDist(results[0].value.data || []);
    if (results[1].status === 'fulfilled') setSentimentTimeline(results[1].value.data || []);
    if (results[2].status === 'fulfilled') setSentimentSources(results[2].value.data || []);
  }, []);

  const fetchEntities = useCallback(async () => {
    const results = await Promise.allSettled([
      safeFetch(`${API_BASE}/entities`),
      safeFetch(`${API_BASE}/trending/keywords`),
    ]);
    if (results[0].status === 'fulfilled') setEntitiesData(results[0].value || []);
    if (results[1].status === 'fulfilled') setTrendingKeywords(results[1].value || []);
  }, []);

  const fetchArticles = useCallback(async (p: number) => {
    const result = await safeFetch(`${API_BASE}/articles?page=${p}&page_size=20`);
    setArticles(result.data || []);
    setArticlesMeta(result);
  }, []);

  // Tab-aware polling
  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        if (activeTab === 'overview') await fetchOverview();
        else if (activeTab === 'sentiment') await fetchSentiment();
        else if (activeTab === 'entities') await fetchEntities();
        else if (activeTab === 'articles') await fetchArticles(page);
        if (!cancelled) setApiError(null);
      } catch (err: any) {
        if (!cancelled) setApiError('Mất kết nối tới API server');
      }
    };

    poll();
    const intervalId = setInterval(poll, 15000);
    return () => { cancelled = true; clearInterval(intervalId); };
  }, [activeTab, page, fetchOverview, fetchSentiment, fetchEntities, fetchArticles]);

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
  }, []);

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
      <header>
        <h1>NewsPulse Intelligence</h1>
        <p className="subtitle">Real-time Data Pipeline Dashboard</p>
      </header>

      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
          <Activity size={18} /> Overview
        </button>
        <button className={`tab-btn ${activeTab === 'sentiment' ? 'active' : ''}`} onClick={() => setActiveTab('sentiment')}>
          <ThumbsUp size={18} /> Sentiment
        </button>
        <button className={`tab-btn ${activeTab === 'entities' ? 'active' : ''}`} onClick={() => setActiveTab('entities')}>
          <Hash size={18} /> Entities & NLP
        </button>
        <button className={`tab-btn ${activeTab === 'articles' ? 'active' : ''}`} onClick={() => { setActiveTab('articles'); setPage(1); }}>
          <BookOpen size={18} /> Articles
        </button>
        <button className={`tab-btn ${activeTab === 'stream' ? 'active' : ''}`} onClick={() => setActiveTab('stream')}>
          <Radio size={18} /> Live Stream
        </button>
      </div>

      {activeTab === 'overview' && (
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
                    <Tooltip labelFormatter={(t) => new Date(t).toLocaleString()} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} />
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
        <div className="charts-grid">
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
              <div className="panel-title"><MessageSquare size={20} /> Trending Keywords</div>
            </div>
            <div style={{ height: 400, width: '100%' }}>
              {trendingKeywords.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={trendingKeywords} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={true} vertical={false} />
                    <XAxis type="number" stroke="#94a3b8" fontSize={12} />
                    <YAxis type="category" dataKey="keyword" stroke="#94a3b8" fontSize={11} width={150} />
                    <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} />
                    <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                  No keyword data available
                </div>
              )}
            </div>
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
                    <a href={a.url} target="_blank" rel="noreferrer">
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

      {apiError && (
        <div className="error-toast">
          <AlertTriangle size={16} style={{ display: 'inline', verticalAlign: 'middle', marginRight: '0.5rem' }} />
          {apiError}
        </div>
      )}
    </div>
  );
}

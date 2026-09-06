'use client';

import { useEffect, useState } from 'react';
import { 
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell, Legend, CartesianAxis 
} from 'recharts';
import { Activity, BookOpen, BarChart2, Radio, Bell, ThumbsUp, Hash, Users, MessageSquare } from 'lucide-react';

const API_BASE = 'http://localhost:8001/api/v1';

type FeedEvent = {
  timestamp: string;
  type: string;
  message: string;
  data?: any;
};

export default function Home() {
  const [activeTab, setActiveTab] = useState('overview');
  const [feed, setFeed] = useState<FeedEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  const [overviewData, setOverviewData] = useState<any>(null);
  const [trendingData, setTrendingData] = useState<any>(null);
  const [articles, setArticles] = useState<any[]>([]);

  // ML Analytics State
  const [sentimentDist, setSentimentDist] = useState<any[]>([]);
  const [sentimentTimeline, setSentimentTimeline] = useState<any[]>([]);
  const [sentimentSources, setSentimentSources] = useState<any[]>([]);
  const [entitiesData, setEntitiesData] = useState<any[]>([]);
  const [trendingKeywords, setTrendingKeywords] = useState<any[]>([]);

  // Fetch REST API Data
  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        const [overview, trending, articlesRes, sentDist, sentTime, sentSrc, entRes, trendKw] = await Promise.all([
          fetch(`${API_BASE}/overview`).then(res => res.json()),
          fetch(`${API_BASE}/trending?time_range=24h`).then(res => res.json()),
          fetch(`${API_BASE}/articles?page_size=20`).then(res => res.json()),
          fetch(`${API_BASE}/sentiment/distribution`).then(res => res.json()),
          fetch(`${API_BASE}/sentiment/timeline`).then(res => res.json()),
          fetch(`${API_BASE}/sentiment/sources`).then(res => res.json()),
          fetch(`${API_BASE}/entities`).then(res => res.json()),
          fetch(`${API_BASE}/trending/keywords`).then(res => res.json())
        ]);
        
        setOverviewData(overview);
        setTrendingData(trending);
        setArticles(articlesRes.data || []);
        
        setSentimentDist(sentDist.data || []);
        setSentimentTimeline(sentTime.data || []);
        setSentimentSources(sentSrc.data || []);
        setEntitiesData(entRes || []);
        setTrendingKeywords(trendKw || []);
      } catch (error) {
        console.error("Error fetching REST data:", error);
      }
    };
    
    // Initial fetch
    fetchDashboardData();
    
    // Poll every 10 seconds
    const intervalId = setInterval(fetchDashboardData, 10000);
    return () => clearInterval(intervalId);
  }, []);

  // Connect to SSE Stream
  useEffect(() => {
    const eventSource = new EventSource(`${API_BASE}/stream/`);
    eventSource.onopen = () => setIsConnected(true);
    eventSource.addEventListener('update', (event) => {
      try {
        const newEvent = JSON.parse(event.data);
        setFeed((prev) => [newEvent, ...prev].slice(0, 50));
      } catch (error) {
        console.error('Failed to parse SSE data:', error);
      }
    });
    eventSource.onerror = (error) => {
      setIsConnected(false);
      eventSource.close();
    };
    return () => eventSource.close();
  }, []);

  // Format data for Recharts
  const chartData = overviewData?.articles_by_hour ? overviewData.articles_by_hour.map((row: any) => ({
    time: `${row.hour}:00`,
    count: row.count
  })) : [];

  const sourceData = overviewData?.category_distribution ? overviewData.category_distribution.map((row: any) => ({
    name: row.category, 
    count: row.count
  })) : [];

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
        <button className={`tab-btn ${activeTab === 'articles' ? 'active' : ''}`} onClick={() => setActiveTab('articles')}>
          <BookOpen size={18} /> Articles
        </button>
        <button className={`tab-btn ${activeTab === 'stream' ? 'active' : ''}`} onClick={() => setActiveTab('stream')}>
          <Radio size={18} /> Live Stream
        </button>
      </div>

      {activeTab === 'overview' && (
        <>
          <div className="overview-grid">
            {overviewData?.kpi_cards?.map((kpi: any, i: number) => (
              <div key={i} className="glass-panel metric-card">
                <div className="metric-label">{kpi.label}</div>
                <div className="metric-value">{kpi.value}</div>
              </div>
            ))}
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
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={sentimentDist} dataKey="count" nameKey="sentiment_label" cx="50%" cy="50%" outerRadius={100} label>
                    {sentimentDist.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.sentiment_label.toLowerCase() === 'positive' ? 'var(--accent-green)' : entry.sentiment_label.toLowerCase() === 'negative' ? '#ef4444' : '#94a3b8'} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} itemStyle={{ color: '#fff' }}/>
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
          
          <div className="glass-panel">
            <div className="panel-header">
              <div className="panel-title"><BarChart2 size={20} /> Sentiment by Source</div>
            </div>
            <div style={{ height: 300, width: '100%' }}>
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
            </div>
          </div>

          <div className="glass-panel" style={{ gridColumn: '1 / -1' }}>
            <div className="panel-header">
              <div className="panel-title"><Activity size={20} /> Sentiment Timeline</div>
            </div>
            <div style={{ height: 300, width: '100%' }}>
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
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={entitiesData} layout="vertical" margin={{ left: 50 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={true} vertical={false} />
                  <XAxis type="number" stroke="#94a3b8" fontSize={12} />
                  <YAxis type="category" dataKey="entity_name" stroke="#94a3b8" fontSize={12} width={100} />
                  <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} />
                  <Bar dataKey="mention_count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="glass-panel">
            <div className="panel-header">
              <div className="panel-title"><MessageSquare size={20} /> Trending Keywords</div>
            </div>
            <div style={{ height: 400, width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={trendingKeywords} layout="vertical" margin={{ left: 50 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={true} vertical={false} />
                  <XAxis type="number" stroke="#94a3b8" fontSize={12} />
                  <YAxis type="category" dataKey="keyword" stroke="#94a3b8" fontSize={12} width={100} />
                  <Tooltip cursor={{fill: 'rgba(255,255,255,0.05)'}} contentStyle={{ backgroundColor: 'rgba(30, 41, 59, 0.9)', border: '1px solid rgba(255,255,255,0.1)' }} />
                  <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
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
                <th>Published At</th>
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
                    <span className={`tag ${a.source.toLowerCase()}`}>{a.source}</span>
                  </td>
                  <td>{a.category || '-'}</td>
                  <td>{new Date(a.publish_date).toLocaleString()}</td>
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
        </div>
      )}

      {activeTab === 'stream' && (
        <div className="glass-panel" style={{ maxWidth: '800px', margin: '0 auto' }}>
          <div className="panel-header">
            <div className="panel-title"><Radio size={20} /> Live Data Feed</div>
            <div className="status-indicator">
              <div className="pulse-dot" style={{ backgroundColor: isConnected ? 'var(--accent-green)' : '#ef4444' }}></div>
              <span style={{ color: isConnected ? 'var(--accent-green)' : '#ef4444' }}>
                {isConnected ? 'Connected to Stream' : 'Disconnected'}
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
    </div>
  );
}

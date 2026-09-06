import re

with open("frontend/src/app/page.tsx", "r") as f:
    content = f.read()

# 1. Update imports
content = content.replace(
    "BarChart, Bar, AreaChart, Area",
    "BarChart, Bar, AreaChart, Area, PieChart, Pie, Cell, Legend, CartesianAxis"
)
content = content.replace(
    "Activity, BookOpen, BarChart2, Radio, Bell",
    "Activity, BookOpen, BarChart2, Radio, Bell, ThumbsUp, Hash, Users, MessageSquare"
)

# 2. Add state
state_block = """  const [overviewData, setOverviewData] = useState<any>(null);
  const [trendingData, setTrendingData] = useState<any>(null);
  const [articles, setArticles] = useState<any[]>([]);

  // ML Analytics State
  const [sentimentDist, setSentimentDist] = useState<any[]>([]);
  const [sentimentTimeline, setSentimentTimeline] = useState<any[]>([]);
  const [sentimentSources, setSentimentSources] = useState<any[]>([]);
  const [entitiesData, setEntitiesData] = useState<any[]>([]);
  const [trendingKeywords, setTrendingKeywords] = useState<any[]>([]);
"""
content = content.replace("  const [overviewData, setOverviewData] = useState<any>(null);\n  const [trendingData, setTrendingData] = useState<any>(null);\n  const [articles, setArticles] = useState<any[]>([]);\n", state_block)

# 3. Update fetch
fetch_block = """        const [overview, trending, articlesRes, sentDist, sentTime, sentSrc, entRes, trendKw] = await Promise.all([
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
        setTrendingKeywords(trendKw || []);"""

old_fetch = """        const [overview, trending, articlesRes] = await Promise.all([
          fetch(`${API_BASE}/overview`).then(res => res.json()),
          fetch(`${API_BASE}/trending?time_range=24h`).then(res => res.json()),
          fetch(`${API_BASE}/articles?page_size=20`).then(res => res.json())
        ]);
        
        setOverviewData(overview);
        setTrendingData(trending);
        setArticles(articlesRes.data || []);"""
        
content = content.replace(old_fetch, fetch_block)

# 4. Add Tab Buttons
tabs_block = """      <div className="tabs">
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
      </div>"""

old_tabs = """      <div className="tabs">
        <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
          <Activity size={18} /> Overview
        </button>
        <button className={`tab-btn ${activeTab === 'articles' ? 'active' : ''}`} onClick={() => setActiveTab('articles')}>
          <BookOpen size={18} /> Articles
        </button>
        <button className={`tab-btn ${activeTab === 'stream' ? 'active' : ''}`} onClick={() => setActiveTab('stream')}>
          <Radio size={18} /> Live Stream
        </button>
      </div>"""

content = content.replace(old_tabs, tabs_block)

# 5. Add Tab Contents
new_tabs_content = """      {activeTab === 'sentiment' && (
        <div className="charts-grid">
          <div className="glass-panel">
            <div className="panel-header">
              <div className="panel-title"><ThumbsUp size={20} /> Overall Sentiment</div>
            </div>
            <div style={{ height: 300, width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={sentimentDist} dataKey="count" nameKey="sentiment" cx="50%" cy="50%" outerRadius={100} label>
                    {sentimentDist.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.sentiment.toLowerCase() === 'positive' ? 'var(--accent-green)' : entry.sentiment.toLowerCase() === 'negative' ? '#ef4444' : '#94a3b8'} />
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

      {activeTab === 'articles' && ("""

content = content.replace("      {activeTab === 'articles' && (", new_tabs_content)

with open("frontend/src/app/page.tsx", "w") as f:
    f.write(content)

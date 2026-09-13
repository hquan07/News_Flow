import re

file_path = "frontend/src/app/page.tsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add Auth States and Functions
auth_states = """  const [user, setUser] = useState<any>(null);
  const [showAuth, setShowAuth] = useState(false);
  const [authMode, setAuthMode] = useState<'login'|'register'>('login');
  const [authEmail, setAuthEmail] = useState('');
  const [authPassword, setAuthPassword] = useState('');
  const [authName, setAuthName] = useState('');
  const [forYouArticles, setForYouArticles] = useState<any[]>([]);

  // Auth Functions
  const handleAuth = async (e: any) => {
    e.preventDefault();
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
        alert('Registered successfully. Please login.');
      }
    } catch (err: any) {
      alert(err.message);
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
      // In a real app we'd validate the token and get user info. 
      // For now we just mock a logged-in state if token exists.
      setUser({ email: 'user@example.com' }); 
    }
  }, []);
"""

content = content.replace("const [activeCard, setActiveCard] = useState<number | null>(null);", "const [activeCard, setActiveCard] = useState<number | null>(null);\n" + auth_states)

# 2. Add For You poll
content = content.replace(
    "else if (activeTab === 'articles') await fetchArticles(page);",
    "else if (activeTab === 'articles') await fetchArticles(page);\n        else if (activeTab === 'foryou') await fetchForYou();"
)
content = content.replace(
    "fetchOverview, fetchSentiment, fetchEntities, fetchNetwork, fetchArticles",
    "fetchOverview, fetchSentiment, fetchEntities, fetchNetwork, fetchArticles, fetchForYou"
)

# 3. Add Login Button and User Info to Header
header_controls = """          <select 
            value={selectedSource} 
            onChange={(e) => setSelectedSource(e.target.value)}
            style={{ padding: '8px 16px', borderRadius: '8px', background: 'rgba(15, 23, 42, 0.8)', color: 'white', border: '1px solid rgba(255,255,255,0.2)', outline: 'none', cursor: 'pointer' }}
          >"""
          
header_new_controls = """          {user ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ background: '#3b82f6', borderRadius: '50%', width: '32px', height: '32px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
                {user.email[0].toUpperCase()}
              </div>
              <button onClick={handleLogout} style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.2)', padding: '6px 12px', borderRadius: '8px', color: '#fff', cursor: 'pointer' }}>Logout</button>
            </div>
          ) : (
            <button onClick={() => setShowAuth(true)} style={{ background: '#3b82f6', border: 'none', padding: '8px 16px', borderRadius: '8px', color: '#fff', cursor: 'pointer', fontWeight: 600 }}>Login</button>
          )}
"""
content = content.replace(header_controls, header_new_controls + header_controls)


# 4. Add "For You" Tab Button
tabs_orig = """<button className={`tab-btn ${activeTab === 'alerts' ? 'active' : ''}`} onClick={() => setActiveTab('alerts')}>
          <AlertTriangle size={18} /> Alerts
        </button>"""
tabs_new = tabs_orig + """\n        {user && (
          <button className={`tab-btn ${activeTab === 'foryou' ? 'active' : ''}`} onClick={() => setActiveTab('foryou')} style={{ background: 'linear-gradient(90deg, #8b5cf6, #3b82f6)', color: 'white' }}>
            ✨ For You
          </button>
        )}"""
content = content.replace(tabs_orig, tabs_new)


# 5. Add Auth Modal UI
auth_modal_ui = """
      {showAuth && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="glass-panel" style={{ width: '400px', padding: '2rem' }}>
            <h2 style={{ marginBottom: '1.5rem', textAlign: 'center' }}>{authMode === 'login' ? 'Welcome Back' : 'Create Account'}</h2>
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
"""

# 6. Add For You Feed UI
foryou_ui = """
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
"""

content = content.replace("    </div>\n  );\n}\n", auth_modal_ui + foryou_ui + "    </div>\n  );\n}\n")

# 7. Add trackClick to Articles Table
content = content.replace(
    """<a href={a.url} target="_blank" rel="noreferrer">""",
    """<a href={a.url} target="_blank" rel="noreferrer" onClick={() => trackClick(a.url_hash)}>"""
)


with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("File rewritten successfully for Personalization Phase!")

import React, { useState, useEffect } from 'react';
import { Activity, Database, AlertTriangle } from 'lucide-react';

interface LandingHeroProps {
  authMode: 'login' | 'register';
  setAuthMode: (mode: 'login' | 'register') => void;
  authName: string;
  setAuthName: (val: string) => void;
  authEmail: string;
  setAuthEmail: (val: string) => void;
  authPassword: string;
  setAuthPassword: (val: string) => void;
  authModalError: string | null;
  handleAuth: (e: React.FormEvent) => void;
}

const LandingHero: React.FC<LandingHeroProps> = ({ 
  authMode, setAuthMode, authName, setAuthName, authEmail, setAuthEmail, authPassword, setAuthPassword, authModalError, handleAuth 
}) => {
  const [summary, setSummary] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('http://localhost:8001/api/v1/public/summary')
      .then(res => res.json())
      .then(data => {
        setSummary(data);
        setLoading(false);
      })
      .catch(() => {
        setSummary({ status: 'unavailable', articles_processed: 0 });
        setLoading(false);
      });
  }, []);

  const isHealthy = summary?.status === 'healthy';

  return (
    <div className="landing-layout">
      
      {/* Left Column: Hero Information */}
      <div className="landing-copy">
        <div style={{ background: isHealthy ? 'rgba(59, 130, 246, 0.1)' : 'rgba(239, 68, 68, 0.1)', border: `1px solid ${isHealthy ? 'rgba(59, 130, 246, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`, padding: '10px 20px', borderRadius: '30px', color: isHealthy ? '#60a5fa' : '#ef4444', fontWeight: 600, marginBottom: '24px', display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          {loading ? (
            <>Checking system...</>
          ) : isHealthy ? (
            <><Activity size={18} /> System Online & Processing</>
          ) : (
            <><AlertTriangle size={18} /> Status unavailable</>
          )}
        </div>
        
        <h1 className="landing-title">
          NewsPulse Intelligence
        </h1>
        
        <p style={{ fontSize: '1.2rem', color: '#94a3b8', margin: '0 0 40px 0', lineHeight: 1.6 }}>
          Real-time Data Pipeline Dashboard for large-scale News & Social Media analysis, powered by NLP and anomaly detection.
        </p>

        <div className="landing-stats">
          <div className="glass-panel" style={{ padding: '20px', borderRadius: '16px' }}>
            <Database size={32} color="#3b82f6" style={{ marginBottom: '10px' }} />
            <h3 style={{ fontSize: '1.5rem', margin: '0 0 5px 0' }}>
              {loading ? '...' : summary?.articles_processed > 0 ? `${(summary.articles_processed / 1000).toFixed(0)}K+` : '0'}
            </h3>
            <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.9rem' }}>Articles Processed</p>
          </div>
          <div className="glass-panel" style={{ padding: '20px', borderRadius: '16px' }}>
            <Activity size={32} color="#f43f5e" style={{ marginBottom: '10px' }} />
            <h3 style={{ fontSize: '1.5rem', margin: '0 0 5px 0' }}>
              {loading ? '...' : isHealthy ? 'Real-time' : 'Offline'}
            </h3>
            <p style={{ color: '#94a3b8', margin: 0, fontSize: '0.9rem' }}>Anomaly Alerts</p>
          </div>
        </div>
      </div>

      {/* Right Column: Login Form */}
      <div className="auth-card-container">
        <div className="glass-panel auth-card">
          <h2 style={{ marginBottom: '1.5rem', textAlign: 'center', fontSize: '2rem' }}>
            {authMode === 'login' ? 'Welcome Back' : 'Create Account'}
          </h2>
          {authModalError && (
            <div style={{ padding: '12px', marginBottom: '1.5rem', background: 'rgba(239, 68, 68, 0.2)', color: '#ef4444', borderRadius: '12px', textAlign: 'center', border: '1px solid rgba(239, 68, 68, 0.5)' }}>
              {authModalError}
            </div>
          )}
          <form onSubmit={handleAuth} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
            {authMode === 'register' && (
              <div>
                <label style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1', fontSize: '0.9rem' }}>Full Name</label>
                <input type="text" value={authName} onChange={e => setAuthName(e.target.value)} required style={{ width: '100%', padding: '14px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.3)', color: 'white', fontSize: '1rem' }} />
              </div>
            )}
            <div>
              <label style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1', fontSize: '0.9rem' }}>Email</label>
              <input type="email" value={authEmail} onChange={e => setAuthEmail(e.target.value)} required style={{ width: '100%', padding: '14px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.3)', color: 'white', fontSize: '1rem' }} />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '8px', color: '#cbd5e1', fontSize: '0.9rem' }}>Password</label>
              <input type="password" value={authPassword} onChange={e => setAuthPassword(e.target.value)} required style={{ width: '100%', padding: '14px', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.3)', color: 'white', fontSize: '1rem' }} />
            </div>

            <button type="submit" style={{ padding: '14px', borderRadius: '12px', border: 'none', background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)', color: 'white', fontWeight: 700, fontSize: '1.1rem', cursor: 'pointer', marginTop: '10px', boxShadow: '0 4px 15px rgba(59, 130, 246, 0.3)', transition: 'transform 0.2s' }} onMouseOver={e => e.currentTarget.style.transform = 'scale(1.02)'} onMouseOut={e => e.currentTarget.style.transform = 'scale(1)'}>
              {authMode === 'login' ? 'Login to Dashboard' : 'Register Account'}
            </button>
          </form>
          <div style={{ marginTop: '1.5rem', textAlign: 'center', fontSize: '0.95rem' }}>
            <span style={{ color: '#94a3b8', cursor: 'pointer', textDecoration: 'underline' }} onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}>
              {authMode === 'login' ? "Don't have an account? Register" : "Already have an account? Login"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LandingHero;

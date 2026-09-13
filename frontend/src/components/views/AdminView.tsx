import React, { useState } from "react";
import {
  Activity,
  Server,
  Clock,
  Users,
  CheckCircle,
  XCircle,
  RefreshCw,
  BookOpen,
  Share2,
} from "lucide-react";
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
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

export default function AdminView({
  adminLatency,
  adminClickbait,
  adminUsers,
  timeAgo,
}: any) {
  const [activeCard, setActiveCard] = useState<number | null>(null);
  return (
    <>
      <>
        <div className="overview-grid">
          <div
            className={`glass-panel metric-card ${activeCard === 10 ? "expanded" : ""}`}
            onClick={() => setActiveCard(activeCard === 10 ? null : 10)}
          >
            <div
              className="metric-content"
              style={{ display: activeCard === 10 ? "none" : "block" }}
            >
              <div className="metric-label">Total Users</div>
              <div className="metric-value">{adminUsers?.total_users || 0}</div>
              <div className="metric-hint">Click để xem chi tiết</div>
            </div>
            {activeCard === 10 && (
              <div className="metric-details">
                <div
                  className="metric-label"
                  style={{
                    marginBottom: "8px",
                    borderBottom: "1px solid rgba(255,255,255,0.1)",
                    paddingBottom: "4px",
                  }}
                >
                  Total Users (Chi tiết)
                </div>
                <ul className="metric-details-list">
                  <li>
                    <span>Standard Users</span>
                    <strong>{adminUsers?.standard_users || 0}</strong>
                  </li>
                  <li>
                    <span>Admin Users</span>
                    <strong style={{ color: "#ef4444" }}>
                      {adminUsers?.admin_users || 0}
                    </strong>
                  </li>
                </ul>
              </div>
            )}
          </div>

          <div
            className={`glass-panel metric-card ${activeCard === 11 ? "expanded" : ""}`}
            onClick={() => setActiveCard(activeCard === 11 ? null : 11)}
          >
            <div
              className="metric-content"
              style={{ display: activeCard === 11 ? "none" : "block" }}
            >
              <div className="metric-label">Avg Crawl Latency</div>
              <div className="metric-value">
                {adminLatency?.avg_latency?.length
                  ? (
                      adminLatency.avg_latency.reduce(
                        (a: number, b: number) => a + b,
                        0,
                      ) / adminLatency.avg_latency.length
                    ).toFixed(1)
                  : 0}{" "}
                m
              </div>
              <div className="metric-hint">Click để xem chi tiết</div>
            </div>
            {activeCard === 11 && (
              <div className="metric-details">
                <div
                  className="metric-label"
                  style={{
                    marginBottom: "8px",
                    borderBottom: "1px solid rgba(255,255,255,0.1)",
                    paddingBottom: "4px",
                  }}
                >
                  Latency (Chi tiết)
                </div>
                <ul className="metric-details-list">
                  {adminLatency?.sources
                    ?.slice(0, 5)
                    .map((s: string, i: number) => (
                      <li key={s}>
                        <span style={{ textTransform: "capitalize" }}>{s}</span>
                        <strong>{adminLatency.avg_latency[i]} m</strong>
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>

          <div
            className={`glass-panel metric-card ${activeCard === 12 ? "expanded" : ""}`}
            onClick={() => setActiveCard(activeCard === 12 ? null : 12)}
          >
            <div
              className="metric-content"
              style={{ display: activeCard === 12 ? "none" : "block" }}
            >
              <div className="metric-label">Total News Articles</div>
              <div className="metric-value">
                {adminClickbait?.news?.volumes?.length
                  ? adminClickbait.news.volumes.reduce(
                      (a: number, b: number) => a + b,
                      0,
                    )
                  : 0}
              </div>
              <div className="metric-hint">Click để xem chi tiết</div>
            </div>
            {activeCard === 12 && (
              <div className="metric-details">
                <div
                  className="metric-label"
                  style={{
                    marginBottom: "8px",
                    borderBottom: "1px solid rgba(255,255,255,0.1)",
                    paddingBottom: "4px",
                  }}
                >
                  News (Chi tiết)
                </div>
                <ul className="metric-details-list">
                  {adminClickbait?.news?.sources
                    ?.slice(0, 5)
                    .map((s: string, i: number) => (
                      <li key={s}>
                        <span style={{ textTransform: "capitalize" }}>{s}</span>
                        <strong>{adminClickbait.news.volumes[i]}</strong>
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>

          <div
            className={`glass-panel metric-card ${activeCard === 13 ? "expanded" : ""}`}
            onClick={() => setActiveCard(activeCard === 13 ? null : 13)}
          >
            <div
              className="metric-content"
              style={{ display: activeCard === 13 ? "none" : "block" }}
            >
              <div className="metric-label">Total Social Posts</div>
              <div className="metric-value">
                {adminClickbait?.social?.volumes?.length
                  ? adminClickbait.social.volumes.reduce(
                      (a: number, b: number) => a + b,
                      0,
                    )
                  : 0}
              </div>
              <div className="metric-hint">Click để xem chi tiết</div>
            </div>
            {activeCard === 13 && (
              <div className="metric-details">
                <div
                  className="metric-label"
                  style={{
                    marginBottom: "8px",
                    borderBottom: "1px solid rgba(255,255,255,0.1)",
                    paddingBottom: "4px",
                  }}
                >
                  Social (Chi tiết)
                </div>
                <ul className="metric-details-list">
                  {adminClickbait?.social?.sources
                    ?.slice(0, 5)
                    .map((s: string, i: number) => (
                      <li key={s}>
                        <span style={{ textTransform: "capitalize" }}>{s}</span>
                        <strong>{adminClickbait.social.volumes[i]}</strong>
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>

          <div className={`glass-panel metric-card`}>
            <div className="metric-content">
              <div className="metric-label">System Health</div>
              <div
                className="metric-value"
                style={{ color: "var(--accent-green)" }}
              >
                Healthy
              </div>
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

          <div
            className={`glass-panel metric-card ${activeCard === 15 ? "expanded" : ""}`}
            onClick={() => setActiveCard(activeCard === 15 ? null : 15)}
          >
            <div
              className="metric-content"
              style={{ display: activeCard === 15 ? "none" : "block" }}
            >
              <div className="metric-label">Active News Sources</div>
              <div className="metric-value">
                {adminClickbait?.news?.sources?.length || 0}
              </div>
              <div className="metric-hint">Click để xem chi tiết</div>
            </div>
            {activeCard === 15 && (
              <div className="metric-details">
                <div
                  className="metric-label"
                  style={{
                    marginBottom: "8px",
                    borderBottom: "1px solid rgba(255,255,255,0.1)",
                    paddingBottom: "4px",
                  }}
                >
                  Các trang báo
                </div>
                <ul className="metric-details-list">
                  {adminClickbait?.news?.sources
                    ?.slice(0, 5)
                    .map((s: string) => (
                      <li key={s}>
                        <span style={{ textTransform: "capitalize" }}>{s}</span>
                        <strong style={{ color: "var(--accent-green)" }}>
                          Active
                        </strong>
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>

          <div
            className={`glass-panel metric-card ${activeCard === 16 ? "expanded" : ""}`}
            onClick={() => setActiveCard(activeCard === 16 ? null : 16)}
          >
            <div
              className="metric-content"
              style={{ display: activeCard === 16 ? "none" : "block" }}
            >
              <div className="metric-label">Active Social Platforms</div>
              <div className="metric-value">
                {adminClickbait?.social?.sources?.length || 0}
              </div>
              <div className="metric-hint">Click để xem chi tiết</div>
            </div>
            {activeCard === 16 && (
              <div className="metric-details">
                <div
                  className="metric-label"
                  style={{
                    marginBottom: "8px",
                    borderBottom: "1px solid rgba(255,255,255,0.1)",
                    paddingBottom: "4px",
                  }}
                >
                  Các MXH
                </div>
                <ul className="metric-details-list">
                  {adminClickbait?.social?.sources
                    ?.slice(0, 5)
                    .map((s: string) => (
                      <li key={s}>
                        <span style={{ textTransform: "capitalize" }}>{s}</span>
                        <strong style={{ color: "var(--accent-green)" }}>
                          Active
                        </strong>
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>
        </div>

        <div className="charts-grid">
          <div className="glass-panel" style={{ gridColumn: "1 / -1" }}>
            <div className="panel-header">
              <div className="panel-title">
                <Activity size={20} /> Crawl Latency by Source
              </div>
            </div>
            <div style={{ height: 300, width: "100%" }}>
              {adminLatency?.sources?.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={adminLatency.sources.map((s: string, i: number) => ({
                      source: s,
                      latency: adminLatency.avg_latency[i],
                    }))}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.1)"
                    />
                    <XAxis dataKey="source" stroke="#94a3b8" fontSize={12} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip
                      cursor={{ fill: "rgba(255,255,255,0.05)" }}
                      contentStyle={{
                        backgroundColor: "rgba(30, 41, 59, 0.9)",
                      }}
                    />
                    <Bar dataKey="latency" fill="#3b82f6" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100%",
                    color: "var(--text-muted)",
                  }}
                >
                  No Data
                </div>
              )}
            </div>
          </div>

          <div className="glass-panel">
            <div className="panel-header">
              <div className="panel-title">
                <BookOpen size={20} /> News Articles Volume
              </div>
            </div>
            <div style={{ height: 300, width: "100%" }}>
              {adminClickbait?.news?.sources?.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={adminClickbait.news.sources.map(
                      (s: string, i: number) => ({
                        source: s,
                        total: adminClickbait.news.volumes[i],
                      }),
                    )}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.1)"
                    />
                    <XAxis dataKey="source" stroke="#94a3b8" fontSize={12} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip
                      cursor={{ fill: "rgba(255,255,255,0.05)" }}
                      contentStyle={{
                        backgroundColor: "rgba(30, 41, 59, 0.9)",
                      }}
                    />
                    <Bar dataKey="total" fill="#ef4444" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100%",
                    color: "var(--text-muted)",
                  }}
                >
                  No Data
                </div>
              )}
            </div>
          </div>

          <div className="glass-panel">
            <div className="panel-header">
              <div className="panel-title">
                <Share2 size={20} /> Social Posts Volume
              </div>
            </div>
            <div style={{ height: 300, width: "100%" }}>
              {adminClickbait?.social?.sources?.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={adminClickbait.social.sources.map(
                      (s: string, i: number) => ({
                        source: s,
                        total: adminClickbait.social.volumes[i],
                      }),
                    )}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="rgba(255,255,255,0.1)"
                    />
                    <XAxis dataKey="source" stroke="#94a3b8" fontSize={12} />
                    <YAxis stroke="#94a3b8" fontSize={12} />
                    <Tooltip
                      cursor={{ fill: "rgba(255,255,255,0.05)" }}
                      contentStyle={{
                        backgroundColor: "rgba(30, 41, 59, 0.9)",
                      }}
                    />
                    <Bar dataKey="total" fill="#8b5cf6" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100%",
                    color: "var(--text-muted)",
                  }}
                >
                  No Data
                </div>
              )}
            </div>
          </div>

          <div className="glass-panel" style={{ gridColumn: "1 / -1" }}>
            <div className="panel-header">
              <div className="panel-title">
                <Users size={20} /> User Roles Distribution
              </div>
            </div>
            <div style={{ height: 300, width: "100%" }}>
              {adminUsers ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={[
                        {
                          name: "Standard Users",
                          count: adminUsers.standard_users,
                        },
                        {
                          name: "Admin Users",
                          count: adminUsers.admin_users,
                        },
                      ]}
                      dataKey="count"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={100}
                      label
                    >
                      <Cell fill="#3b82f6" />
                      <Cell fill="#ef4444" />
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "rgba(30, 41, 59, 0.9)",
                        border: "1px solid rgba(255,255,255,0.1)",
                      }}
                      itemStyle={{ color: "#fff" }}
                    />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    height: "100%",
                    color: "var(--text-muted)",
                  }}
                >
                  No Data
                </div>
              )}
            </div>
          </div>
        </div>
      </>
      )
    </>
  );
}

"""Self-contained dashboard HTML served by the FastAPI app."""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Devin Issue Remediation — Dashboard</title>
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --surface2: #1c2129; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149; --yellow: #d29922; --purple: #bc8cff;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.5;
  }

  /* Layout */
  .sidebar {
    position: fixed; top: 0; left: 0; width: 220px; height: 100vh;
    background: var(--surface); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; z-index: 10;
  }
  .sidebar-brand {
    padding: 20px 16px; border-bottom: 1px solid var(--border);
  }
  .sidebar-brand h1 { font-size: 0.95rem; font-weight: 700; }
  .sidebar-brand .sub { color: var(--muted); font-size: 0.7rem; margin-top: 2px; }
  .sidebar-nav { flex: 1; padding: 12px 8px; }
  .nav-item {
    display: flex; align-items: center; gap: 10px; padding: 9px 12px;
    border-radius: 6px; cursor: pointer; font-size: 0.85rem;
    color: var(--muted); transition: all 0.15s; margin-bottom: 2px;
  }
  .nav-item:hover { background: rgba(88,166,255,0.06); color: var(--text); }
  .nav-item.active { background: rgba(88,166,255,0.1); color: var(--accent); }
  .nav-item svg { width: 16px; height: 16px; flex-shrink: 0; }
  .sidebar-footer {
    padding: 12px 16px; border-top: 1px solid var(--border); font-size: 0.75rem;
  }
  .health-row { display: flex; align-items: center; gap: 8px; }
  .health-dot {
    width: 8px; height: 8px; border-radius: 50%; background: var(--green);
    flex-shrink: 0;
  }
  .health-dot.down { background: var(--red); }

  .main { margin-left: 220px; padding: 24px 32px; min-height: 100vh; }

  /* Page visibility */
  .page { display: none; }
  .page.active { display: block; }

  /* Stat cards */
  .stats-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px; margin-bottom: 24px;
  }
  .stat-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 16px;
  }
  .stat-card .label {
    color: var(--muted); font-size: 0.75rem;
    text-transform: uppercase; font-weight: 600;
  }
  .stat-card .value { font-size: 1.75rem; font-weight: 700; margin-top: 4px; }
  .stat-card .value.accent { color: var(--accent); }
  .stat-card .value.green { color: var(--green); }
  .stat-card .value.red { color: var(--red); }
  .stat-card .value.yellow { color: var(--yellow); }
  .stat-card .value.purple { color: var(--purple); }

  /* Pipeline visualisation */
  .pipeline-section { margin-bottom: 28px; }
  .pipeline-section h2 { font-size: 1rem; margin-bottom: 12px; }
  .pipeline {
    display: flex; align-items: center; gap: 0;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 20px 24px; overflow-x: auto;
  }
  .pipeline-step {
    display: flex; flex-direction: column; align-items: center;
    min-width: 130px; text-align: center;
  }
  .pipeline-icon {
    width: 44px; height: 44px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem; margin-bottom: 8px; border: 2px solid var(--border);
    background: var(--surface2);
  }
  .pipeline-icon.blue { border-color: var(--accent); color: var(--accent); }
  .pipeline-icon.green { border-color: var(--green); color: var(--green); }
  .pipeline-icon.purple { border-color: var(--purple); color: var(--purple); }
  .pipeline-icon.yellow { border-color: var(--yellow); color: var(--yellow); }
  .pipeline-step .step-label { font-size: 0.8rem; font-weight: 600; }
  .pipeline-step .step-count {
    font-size: 0.7rem; color: var(--muted); margin-top: 2px;
  }
  .pipeline-arrow {
    flex-shrink: 0; color: var(--muted); font-size: 1.2rem;
    margin: 0 8px; padding-bottom: 20px;
  }

  /* Section headers */
  .section-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 12px;
  }
  .section-header h2 { font-size: 1rem; }
  .section-header .meta { color: var(--muted); font-size: 0.75rem; }

  /* Tables */
  table {
    width: 100%; border-collapse: collapse; background: var(--surface);
    border-radius: 8px; overflow: hidden; font-size: 0.83rem;
    border: 1px solid var(--border);
  }
  th, td {
    padding: 10px 14px; text-align: left;
    border-bottom: 1px solid var(--border);
  }
  th {
    color: var(--muted); font-weight: 600; font-size: 0.72rem;
    text-transform: uppercase; background: var(--surface2);
  }
  tr:last-child td { border-bottom: none; }
  tr:hover { background: rgba(88,166,255,0.04); }
  tr.clickable { cursor: pointer; }

  /* Badges */
  .badge {
    display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 0.72rem; font-weight: 600; white-space: nowrap;
  }
  .badge-green { background: rgba(63,185,80,0.15); color: var(--green); }
  .badge-red { background: rgba(248,81,73,0.15); color: var(--red); }
  .badge-yellow { background: rgba(210,153,34,0.15); color: var(--yellow); }
  .badge-blue { background: rgba(88,166,255,0.15); color: var(--accent); }
  .badge-purple { background: rgba(188,140,255,0.15); color: var(--purple); }
  .badge-muted { background: rgba(139,148,158,0.15); color: var(--muted); }

  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .empty { text-align: center; padding: 40px; color: var(--muted); }

  /* Refresh button */
  .refresh-btn {
    padding: 4px 10px; border-radius: 6px;
    border: 1px solid var(--border); background: var(--surface);
    color: var(--muted); font-size: 0.72rem; cursor: pointer;
    transition: all 0.15s; display: inline-flex; align-items: center; gap: 4px;
  }
  .refresh-btn:hover { border-color: var(--accent); color: var(--text); }
  .refresh-btn.spinning svg { animation: spin 0.6s linear; }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

  /* Activity feed */
  .activity-feed {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; max-height: 360px; overflow-y: auto;
  }
  .activity-item {
    display: flex; align-items: flex-start; gap: 12px;
    padding: 12px 16px; border-bottom: 1px solid var(--border);
  }
  .activity-item:last-child { border-bottom: none; }
  .activity-item.clickable { cursor: pointer; transition: background 0.15s; }
  .activity-item.clickable:hover { background: rgba(88,166,255,0.06); }
  .activity-dot {
    width: 8px; height: 8px; border-radius: 50%; margin-top: 6px;
    flex-shrink: 0;
  }
  .activity-dot.blue { background: var(--accent); }
  .activity-dot.green { background: var(--green); }
  .activity-dot.red { background: var(--red); }
  .activity-dot.yellow { background: var(--yellow); }
  .activity-dot.muted { background: var(--muted); }
  .activity-content { flex: 1; }
  .activity-content .title { font-size: 0.83rem; }
  .activity-content .time { font-size: 0.72rem; color: var(--muted); }

  /* Detail panel (slide-in) */
  .detail-overlay {
    display: none; position: fixed; top: 0; left: 0;
    width: 100%; height: 100%;
    background: rgba(0,0,0,0.5); z-index: 100;
  }
  .detail-overlay.open { display: flex; justify-content: flex-end; }
  .detail-panel {
    width: 560px; max-width: 90vw; height: 100vh;
    background: var(--surface);
    border-left: 1px solid var(--border);
    overflow-y: auto; padding: 24px;
  }
  .detail-panel .close-btn {
    float: right; background: none; border: none;
    color: var(--muted); font-size: 1.2rem;
    cursor: pointer; padding: 4px;
  }
  .detail-panel .close-btn:hover { color: var(--text); }
  .detail-panel h2 { font-size: 1.1rem; margin-bottom: 16px; }
  .detail-section { margin-bottom: 20px; }
  .detail-section h3 {
    font-size: 0.8rem; text-transform: uppercase;
    color: var(--muted); margin-bottom: 8px; font-weight: 600;
  }
  .detail-row {
    display: flex; gap: 8px; margin-bottom: 6px; font-size: 0.83rem;
  }
  .detail-row .key {
    color: var(--muted); min-width: 100px; flex-shrink: 0;
  }
  .detail-row .val { word-break: break-all; }

  /* Timeline */
  .timeline { position: relative; padding-left: 24px; }
  .timeline::before {
    content: ''; position: absolute; left: 7px;
    top: 4px; bottom: 4px;
    width: 2px; background: var(--border);
  }
  .timeline-item { position: relative; margin-bottom: 16px; }
  .timeline-item::before {
    content: ''; position: absolute; left: -20px; top: 5px;
    width: 10px; height: 10px; border-radius: 50%;
    background: var(--border); border: 2px solid var(--surface);
  }
  .timeline-item.blue::before { background: var(--accent); }
  .timeline-item.green::before { background: var(--green); }
  .timeline-item.red::before { background: var(--red); }
  .timeline-item.yellow::before { background: var(--yellow); }
  .timeline-item .tl-status { font-size: 0.83rem; font-weight: 600; }
  .timeline-item .tl-time { font-size: 0.72rem; color: var(--muted); }
  .timeline-item .tl-details {
    font-size: 0.75rem; color: var(--muted); margin-top: 4px;
  }

  /* Payload viewer */
  .payload-viewer {
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px; padding: 12px; max-height: 400px;
    overflow: auto; font-family: monospace;
    font-size: 0.75rem; white-space: pre-wrap; word-break: break-all;
  }

  /* Filters */
  .filters {
    display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap;
  }
  .filter-btn {
    padding: 5px 12px; border-radius: 16px;
    border: 1px solid var(--border);
    background: var(--surface); color: var(--muted);
    font-size: 0.75rem; cursor: pointer; transition: all 0.15s;
  }
  .filter-btn:hover { border-color: var(--accent); color: var(--text); }
  .filter-btn.active {
    border-color: var(--accent); background: rgba(88,166,255,0.1);
    color: var(--accent);
  }

  /* Repo pills */
  .repo-list { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px; }
  .repo-pill {
    font-size: 0.72rem; padding: 3px 10px; border-radius: 12px;
    background: rgba(188,140,255,0.12); color: var(--purple);
    border: 1px solid rgba(188,140,255,0.25);
  }

  /* Responsive */
  @media (max-width: 768px) {
    .sidebar { width: 60px; }
    .sidebar-brand h1, .sidebar-brand .sub,
    .nav-item span, .sidebar-footer span { display: none; }
    .nav-item { justify-content: center; padding: 12px; }
    .main { margin-left: 60px; padding: 16px; }
    .detail-panel { width: 100vw; }
  }
</style>
</head>
<body>

<!-- Sidebar -->
<nav class="sidebar">
  <div class="sidebar-brand">
    <h1>Devin Remediation</h1>
    <div class="sub">Diagnostic Dashboard</div>
  </div>
  <div class="sidebar-nav">
    <div class="nav-item active" data-page="overview">
      <svg viewBox="0 0 16 16" fill="currentColor"><path d="M0 1.75A.75.75 0 01.75 1h14.5a.75.75 0 010 1.5H.75A.75.75 0 010 1.75zM0 8a.75.75 0 01.75-.75h14.5a.75.75 0 010 1.5H.75A.75.75 0 010 8zm.75 5.5a.75.75 0 000 1.5h14.5a.75.75 0 000-1.5H.75z"/></svg>
      <span>Overview</span>
    </div>
    <div class="nav-item" data-page="events">
      <svg viewBox="0 0 16 16" fill="currentColor"><path d="M8.75 1.75a.75.75 0 00-1.5 0v5.69L5.03 5.22a.75.75 0 00-1.06 1.06l3.5 3.5a.75.75 0 001.06 0l3.5-3.5a.75.75 0 00-1.06-1.06L8.75 7.44V1.75zM1.5 10a.75.75 0 00-1.5 0v3.25c0 .966.784 1.75 1.75 1.75h12.5A1.75 1.75 0 0016 13.25V10a.75.75 0 00-1.5 0v3.25a.25.25 0 01-.25.25H1.75a.25.25 0 01-.25-.25V10z"/></svg>
      <span>Webhook Events</span>
    </div>
    <div class="nav-item" data-page="sessions">
      <svg viewBox="0 0 16 16" fill="currentColor"><path d="M1 2.75C1 1.784 1.784 1 2.75 1h10.5c.966 0 1.75.784 1.75 1.75v10.5A1.75 1.75 0 0113.25 15H2.75A1.75 1.75 0 011 13.25V2.75zm1.75-.25a.25.25 0 00-.25.25v10.5c0 .138.112.25.25.25h10.5a.25.25 0 00.25-.25V2.75a.25.25 0 00-.25-.25H2.75zM8 4a.75.75 0 01.75.75v2.5h2.5a.75.75 0 010 1.5h-2.5v2.5a.75.75 0 01-1.5 0v-2.5h-2.5a.75.75 0 010-1.5h2.5v-2.5A.75.75 0 018 4z"/></svg>
      <span>Sessions</span>
    </div>
  </div>
  <div class="sidebar-footer">
    <div class="health-row">
      <div class="health-dot" id="health-dot"></div>
      <span id="health-text">Checking...</span>
    </div>
  </div>
</nav>

<!-- Main content -->
<div class="main">

  <!-- ==================== OVERVIEW ==================== -->
  <div id="overview" class="page active">
    <h2 style="font-size:1.25rem; margin-bottom:4px;">System Overview</h2>
    <p style="color:var(--muted); font-size:0.83rem; margin-bottom:20px;">
      Real-time view of the webhook pipeline and remediation sessions
    </p>

    <div class="stats-grid" id="stats-grid">
      <div class="stat-card">
        <div class="label">Total Webhooks</div>
        <div class="value" id="st-total">-</div>
      </div>
      <div class="stat-card">
        <div class="label">Processed</div>
        <div class="value green" id="st-processed">-</div>
      </div>
      <div class="stat-card">
        <div class="label">Ignored</div>
        <div class="value" style="color:var(--muted)" id="st-ignored">-</div>
      </div>
      <div class="stat-card">
        <div class="label">Active Sessions</div>
        <div class="value accent" id="st-active">-</div>
      </div>
      <div class="stat-card">
        <div class="label">PR Created</div>
        <div class="value green" id="st-pr-created">-</div>
      </div>
      <div class="stat-card">
        <div class="label">Errors</div>
        <div class="value red" id="st-errors">-</div>
      </div>
    </div>

    <!-- Pipeline -->
    <div class="pipeline-section">
      <h2>Remediation Pipeline</h2>
      <div class="pipeline">
        <div class="pipeline-step">
          <div class="pipeline-icon blue">&#x2B07;</div>
          <div class="step-label">Webhook Received</div>
          <div class="step-count" id="pipe-received">-</div>
        </div>
        <div class="pipeline-arrow">&#x2192;</div>
        <div class="pipeline-step">
          <div class="pipeline-icon yellow">&#x1F50D;</div>
          <div class="step-label">Filter &amp; Validate</div>
          <div class="step-count">devin-fix label</div>
        </div>
        <div class="pipeline-arrow">&#x2192;</div>
        <div class="pipeline-step">
          <div class="pipeline-icon purple">&#x1F680;</div>
          <div class="step-label">Session Created</div>
          <div class="step-count" id="pipe-created">-</div>
        </div>
        <div class="pipeline-arrow">&#x2192;</div>
        <div class="pipeline-step">
          <div class="pipeline-icon blue">&#x23F3;</div>
          <div class="step-label">Polling</div>
          <div class="step-count" id="pipe-polling">-</div>
        </div>
        <div class="pipeline-arrow">&#x2192;</div>
        <div class="pipeline-step">
          <div class="pipeline-icon green">&#x2714;</div>
          <div class="step-label">PR Created</div>
          <div class="step-count" id="pipe-done">-</div>
        </div>
      </div>
    </div>

    <!-- Monitored repos -->
    <div class="detail-section">
      <h3>Monitored Repositories</h3>
      <div class="repo-list" id="repo-list">
        <span style="color:var(--muted); font-size:0.8rem;">
          No repositories seen yet
        </span>
      </div>
    </div>

    <!-- Recent activity -->
    <div class="section-header" style="margin-top:20px;">
      <h2>Recent Activity</h2>
      <div style="display:flex; align-items:center; gap:10px;">
        <div class="meta">Auto-refreshes every 5s</div>
        <button class="refresh-btn" id="refresh-btn" onclick="manualRefresh()">
          <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor"><path d="M8 3a5 5 0 104.546 2.914.5.5 0 01.908-.418A6 6 0 118 2v1z"/><path d="M8 4.466V.534a.25.25 0 01.41-.192l2.36 1.966a.25.25 0 010 .384L8.41 4.658A.25.25 0 018 4.466z"/></svg>
          Refresh
        </button>
      </div>
    </div>
    <div class="activity-feed" id="activity-feed">
      <div class="empty">Loading...</div>
    </div>
  </div>

  <!-- ==================== WEBHOOK EVENTS ==================== -->
  <div id="events" class="page">
    <div class="section-header">
      <h2>Webhook Events</h2>
      <div class="meta" id="events-count"></div>
    </div>
    <div class="filters" id="event-filters">
      <button class="filter-btn active" data-filter="all">All</button>
      <button class="filter-btn" data-filter="session_created">Processed</button>
      <button class="filter-btn" data-filter="ignored">Ignored</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>ID</th><th>Time</th><th>Event</th><th>Action</th>
          <th>Repository</th><th>Issue</th><th>Label</th><th>Status</th>
        </tr>
      </thead>
      <tbody id="events-body">
        <tr><td colspan="8" class="empty">Loading...</td></tr>
      </tbody>
    </table>
  </div>

  <!-- ==================== SESSIONS ==================== -->
  <div id="sessions" class="page">
    <div class="section-header">
      <h2>Devin Sessions</h2>
      <div class="meta" id="sessions-count"></div>
    </div>
    <div class="filters" id="session-filters">
      <button class="filter-btn active" data-filter="all">All</button>
      <button class="filter-btn" data-filter="active">Active</button>
      <button class="filter-btn" data-filter="pr_created">PR Created</button>
      <button class="filter-btn" data-filter="error">Errors</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>Session</th><th>Repository</th><th>Issue</th>
          <th>Status</th><th>Created</th><th>Duration</th>
        </tr>
      </thead>
      <tbody id="sessions-body">
        <tr><td colspan="6" class="empty">Loading...</td></tr>
      </tbody>
    </table>
  </div>

</div>

<!-- Detail overlay (slide-in panel) -->
<div class="detail-overlay" id="detail-overlay">
  <div class="detail-panel" id="detail-panel">
    <button class="close-btn" id="detail-close">&times;</button>
    <div id="detail-content"></div>
  </div>
</div>

<script>
/* ---------- Navigation ---------- */
document.querySelectorAll(".nav-item").forEach(function(item) {
  item.addEventListener("click", function() {
    document.querySelectorAll(".nav-item").forEach(function(n) {
      n.classList.remove("active");
    });
    document.querySelectorAll(".page").forEach(function(p) {
      p.classList.remove("active");
    });
    item.classList.add("active");
    document.getElementById(item.dataset.page).classList.add("active");
  });
});

/* ---------- Detail panel ---------- */
function openDetail(html) {
  document.getElementById("detail-content").innerHTML = html;
  document.getElementById("detail-overlay").classList.add("open");
}
function closeDetail() {
  document.getElementById("detail-overlay").classList.remove("open");
}
document.getElementById("detail-close").addEventListener("click", closeDetail);
document.getElementById("detail-overlay").addEventListener("click", function(e) {
  if (e.target === this) closeDetail();
});

/* ---------- Helpers ---------- */
function esc(s) {
  if (s == null) return "";
  var d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

function fmtTime(iso) {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleString();
}

function relTime(iso) {
  if (!iso) return "";
  var diff = Date.now() - new Date(iso).getTime();
  var s = Math.floor(diff / 1000);
  if (s < 60) return s + "s ago";
  var m = Math.floor(s / 60);
  if (m < 60) return m + "m ago";
  var h = Math.floor(m / 60);
  if (h < 24) return h + "h ago";
  return Math.floor(h / 24) + "d ago";
}

function duration(start, end) {
  if (!start) return "\u2014";
  var a = new Date(start).getTime();
  var b = end ? new Date(end).getTime() : Date.now();
  var s = Math.floor((b - a) / 1000);
  if (s < 60) return s + "s";
  var m = Math.floor(s / 60);
  if (m < 60) return m + "m " + (s % 60) + "s";
  var h = Math.floor(m / 60);
  return h + "h " + (m % 60) + "m";
}

function statusBadge(s) {
  var map = {
    pr_created: "badge-green",
    session_created: "badge-blue",
    running: "badge-blue", created: "badge-blue",
    error: "badge-red",
    ignored: "badge-muted"
  };
  var label = s === "pr_created" ? "PR created" : s;
  return '<span class="badge ' + (map[s] || "badge-muted") + '">'
    + esc(label) + "</span>";
}

function statusDotClass(s) {
  if (s === "pr_created" || s === "session_created") return "green";
  if (s === "error") return "red";
  if (s === "running" || s === "created") return "blue";
  return "muted";
}

var TERMINAL = new Set(["pr_created", "error"]);

/* ---------- Filter state ---------- */
var eventFilter = "all";
var sessionFilter = "all";
var allEvents = [];
var allSessions = [];

document.getElementById("event-filters")
  .addEventListener("click", function(e) {
    if (!e.target.classList.contains("filter-btn")) return;
    eventFilter = e.target.dataset.filter;
    this.querySelectorAll(".filter-btn").forEach(function(b) {
      b.classList.remove("active");
    });
    e.target.classList.add("active");
    renderEvents();
  });

document.getElementById("session-filters")
  .addEventListener("click", function(e) {
    if (!e.target.classList.contains("filter-btn")) return;
    sessionFilter = e.target.dataset.filter;
    this.querySelectorAll(".filter-btn").forEach(function(b) {
      b.classList.remove("active");
    });
    e.target.classList.add("active");
    renderSessions();
  });

/* ---------- Data loaders ---------- */
async function loadHealth() {
  try {
    var r = await fetch("/health");
    var d = await r.json();
    document.getElementById("health-dot").classList.remove("down");
    document.getElementById("health-text").textContent =
      "Online \u2014 " + d.active_sessions + " active";
  } catch(e) {
    document.getElementById("health-dot").classList.add("down");
    document.getElementById("health-text").textContent = "Offline";
  }
}

async function loadStats() {
  try {
    var r = await fetch("/api/stats");
    var d = await r.json();
    document.getElementById("st-total").textContent = d.total_events;
    document.getElementById("st-processed").textContent = d.processed_events;
    document.getElementById("st-ignored").textContent = d.ignored_events;
    document.getElementById("st-active").textContent = d.active_sessions;
    document.getElementById("st-pr-created").textContent = d.pr_created_sessions;
    document.getElementById("st-errors").textContent = d.errored_sessions;
    document.getElementById("pipe-received").textContent =
      d.total_events + " total";
    document.getElementById("pipe-created").textContent =
      d.total_sessions + " sessions";
    document.getElementById("pipe-polling").textContent =
      d.active_sessions + " active";
    document.getElementById("pipe-done").textContent =
      d.pr_created_sessions + " done";
    var rl = document.getElementById("repo-list");
    if (d.repos && d.repos.length) {
      rl.innerHTML = d.repos.map(function(r) {
        return '<span class="repo-pill">' + esc(r) + '</span>';
      }).join("");
    } else {
      rl.innerHTML =
        '<span style="color:var(--muted);font-size:0.8rem;">'
        + 'No repositories seen yet</span>';
    }
  } catch(e) { /* ignore */ }
}

async function loadEvents() {
  try {
    var r = await fetch("/api/events");
    allEvents = await r.json();
    renderEvents();
    renderActivity();
  } catch(e) { /* ignore */ }
}

function renderEvents() {
  var filtered = allEvents;
  if (eventFilter !== "all") {
    filtered = allEvents.filter(function(ev) {
      return ev.status === eventFilter;
    });
  }
  document.getElementById("events-count").textContent =
    filtered.length + " of " + allEvents.length + " events";
  var tbody = document.getElementById("events-body");
  if (!filtered.length) {
    tbody.innerHTML =
      '<tr><td colspan="8" class="empty">No events match the filter</td></tr>';
    return;
  }
  tbody.innerHTML = filtered.map(function(ev) {
    return '<tr class="clickable" onclick="showEventDetail(' + ev.id + ')">'
      + "<td>" + ev.id + "</td>"
      + "<td>" + fmtTime(ev.received_at) + "</td>"
      + "<td>" + esc(ev.event_type) + "</td>"
      + "<td>" + (ev.action ? esc(ev.action) : "\u2014") + "</td>"
      + "<td>" + (ev.repo ? esc(ev.repo) : "\u2014") + "</td>"
      + "<td>" + (ev.issue_number != null
          ? "#" + ev.issue_number : "\u2014") + "</td>"
      + "<td>" + (ev.label ? esc(ev.label) : "\u2014") + "</td>"
      + "<td>" + statusBadge(ev.status) + "</td>"
      + "</tr>";
  }).join("");
}

async function showEventDetail(id) {
  openDetail('<div class="empty">Loading event #' + id + '...</div>');
  try {
    var r = await fetch("/api/events/" + id);
    var ev = await r.json();
    var html = '<h2>Webhook Event #' + ev.id + '</h2>'
      + '<div class="detail-section">'
      + '<h3>Details</h3>'
      + '<div class="detail-row"><div class="key">Time</div>'
      + '<div class="val">' + fmtTime(ev.received_at) + '</div></div>'
      + '<div class="detail-row"><div class="key">Event Type</div>'
      + '<div class="val">' + esc(ev.event_type) + '</div></div>'
      + '<div class="detail-row"><div class="key">Action</div>'
      + '<div class="val">' + esc(ev.action || "\u2014") + '</div></div>'
      + '<div class="detail-row"><div class="key">Repository</div>'
      + '<div class="val">' + esc(ev.repo || "\u2014") + '</div></div>'
      + '<div class="detail-row"><div class="key">Issue</div>'
      + '<div class="val">'
      + (ev.issue_number != null ? "#" + ev.issue_number : "\u2014")
      + '</div></div>'
      + '<div class="detail-row"><div class="key">Label</div>'
      + '<div class="val">' + esc(ev.label || "\u2014") + '</div></div>'
      + '<div class="detail-row"><div class="key">Status</div>'
      + '<div class="val">' + statusBadge(ev.status) + '</div></div>'
      + '</div>';
    if (ev.payload) {
      html += '<div class="detail-section">'
        + '<h3>Payload</h3>'
        + '<div class="payload-viewer">'
        + esc(JSON.stringify(ev.payload, null, 2))
        + '</div></div>';
    } else {
      html += '<div class="detail-section">'
        + '<h3>Payload</h3>'
        + '<p style="color:var(--muted);font-size:0.83rem;">'
        + 'No payload recorded for this event</p></div>';
    }
    openDetail(html);
  } catch(e) {
    openDetail('<div class="empty">Failed to load event details</div>');
  }
}

async function loadSessions() {
  try {
    var r = await fetch("/api/sessions");
    allSessions = await r.json();
    renderSessions();
  } catch(e) { /* ignore */ }
}

function renderSessions() {
  var filtered = allSessions;
  if (sessionFilter === "active") {
    filtered = allSessions.filter(function(s) {
      return !TERMINAL.has(s.status);
    });
  } else if (sessionFilter === "pr_created") {
    filtered = allSessions.filter(function(s) {
      return s.status === "pr_created";
    });
  } else if (sessionFilter === "error") {
    filtered = allSessions.filter(function(s) {
      return s.status === "error";
    });
  }
  document.getElementById("sessions-count").textContent =
    filtered.length + " of " + allSessions.length + " sessions";
  var tbody = document.getElementById("sessions-body");
  if (!filtered.length) {
    tbody.innerHTML =
      '<tr><td colspan="6" class="empty">'
      + 'No sessions match the filter</td></tr>';
    return;
  }
  tbody.innerHTML = filtered.map(function(s) {
    var isTerminal = TERMINAL.has(s.status);
    var dur = duration(s.created_at, isTerminal ? s.updated_at : null);
    return '<tr class="clickable" onclick="showSessionDetail(\''
      + esc(s.session_id) + '\')">'
      + '<td><a href="' + esc(s.session_url)
      + '" target="_blank" onclick="event.stopPropagation()">'
      + esc(s.session_id.substring(0, 12)) + '...</a></td>'
      + "<td>" + esc(s.repo) + "</td>"
      + "<td>#" + s.issue_number
      + (s.issue_title ? " \u2014 " + esc(s.issue_title) : "")
      + "</td>"
      + "<td>" + statusBadge(s.status) + "</td>"
      + "<td>" + fmtTime(s.created_at) + "</td>"
      + "<td>" + dur
      + (isTerminal ? ""
          : ' <span style="color:var(--accent)">&#x25CF;</span>')
      + "</td></tr>";
  }).join("");
}

async function showSessionDetail(sessionId) {
  openDetail('<div class="empty">Loading session...</div>');
  var session = allSessions.find(function(s) {
    return s.session_id === sessionId;
  });
  if (!session) { closeDetail(); return; }

  try {
    var r = await fetch("/api/sessions/" + sessionId + "/updates");
    var updates = await r.json();
    var isTerminal = TERMINAL.has(session.status);
    var dur = duration(
      session.created_at, isTerminal ? session.updated_at : null);

    var html = '<h2>Session Detail</h2>'
      + '<div class="detail-section">'
      + '<h3>Information</h3>'
      + '<div class="detail-row"><div class="key">Session ID</div>'
      + '<div class="val"><a href="' + esc(session.session_url)
      + '" target="_blank">' + esc(session.session_id)
      + '</a></div></div>'
      + '<div class="detail-row"><div class="key">Repository</div>'
      + '<div class="val">' + esc(session.repo) + '</div></div>'
      + '<div class="detail-row"><div class="key">Issue</div>'
      + '<div class="val">#' + session.issue_number
      + (session.issue_title
          ? " \u2014 " + esc(session.issue_title) : "")
      + '</div></div>'
      + '<div class="detail-row"><div class="key">Status</div>'
      + '<div class="val">' + statusBadge(session.status) + '</div></div>'
      + '<div class="detail-row"><div class="key">Created</div>'
      + '<div class="val">' + fmtTime(session.created_at) + '</div></div>'
      + '<div class="detail-row"><div class="key">Last Update</div>'
      + '<div class="val">' + fmtTime(session.updated_at) + '</div></div>'
      + '<div class="detail-row"><div class="key">Duration</div>'
      + '<div class="val">' + dur + '</div></div>'
      + '</div>';

    html += '<div class="detail-section"><h3>Status Timeline</h3>';
    if (updates.length) {
      html += '<div class="timeline">';
      var sorted = updates.slice().reverse();
      sorted.forEach(function(u) {
        var cls = statusDotClass(u.status);
        html += '<div class="timeline-item ' + cls + '">'
          + '<div class="tl-status">' + esc(u.status) + '</div>'
          + '<div class="tl-time">' + fmtTime(u.recorded_at) + '</div>';
        if (u.details) {
          var parsed = typeof u.details === "string"
            ? JSON.parse(u.details) : u.details;
          if (parsed && parsed.pull_requests
              && parsed.pull_requests.length) {
            html += '<div class="tl-details">PRs: '
              + parsed.pull_requests.map(function(pr) {
                var url = pr.url || pr;
                return '<a href="' + esc(url)
                  + '" target="_blank">' + esc(url) + '</a>';
              }).join(", ") + '</div>';
          }
        }
        html += '</div>';
      });
      html += '</div>';
    } else {
      html += '<p style="color:var(--muted);font-size:0.83rem;">'
        + 'No status updates recorded yet</p>';
    }
    html += '</div>';
    openDetail(html);
  } catch(e) {
    openDetail(
      '<div class="empty">Failed to load session details</div>');
  }
}

/* ---------- Activity feed ---------- */
function navigateToPage(pageName) {
  document.querySelectorAll(".nav-item").forEach(function(n) {
    n.classList.remove("active");
    if (n.dataset.page === pageName) n.classList.add("active");
  });
  document.querySelectorAll(".page").forEach(function(p) {
    p.classList.remove("active");
  });
  document.getElementById(pageName).classList.add("active");
}

function onActivityClick(type, id) {
  if (type === "event") {
    navigateToPage("events");
    showEventDetail(id);
  } else if (type === "session") {
    navigateToPage("sessions");
    showSessionDetail(id);
  }
}

function manualRefresh() {
  var btn = document.getElementById("refresh-btn");
  btn.classList.add("spinning");
  refresh();
  setTimeout(function() { btn.classList.remove("spinning"); }, 600);
}

function renderActivity() {
  var feed = document.getElementById("activity-feed");
  if (!allEvents.length && !allSessions.length) {
    feed.innerHTML =
      '<div class="empty">No activity yet. Waiting for webhooks...</div>';
    return;
  }
  var items = [];
  allEvents.forEach(function(ev) {
    var desc;
    if (ev.status === "session_created") {
      desc = 'Webhook processed: <strong>'
        + esc(ev.repo) + '#' + ev.issue_number
        + '</strong> &mdash; session created';
    } else if (ev.status === "ignored") {
      desc = 'Webhook ignored: <strong>'
        + esc(ev.event_type) + '</strong>';
      if (ev.label) desc += ' (label: ' + esc(ev.label) + ')';
      if (ev.action) desc += ' (action: ' + esc(ev.action) + ')';
    } else {
      desc = 'Webhook event: <strong>'
        + esc(ev.event_type) + '</strong>';
    }
    items.push({
      time: ev.received_at,
      dot: statusDotClass(ev.status),
      html: desc,
      clickType: "event",
      clickId: ev.id
    });
  });
  allSessions.forEach(function(s) {
    if (TERMINAL.has(s.status)) {
      items.push({
        time: s.updated_at,
        dot: statusDotClass(s.status),
        html: 'Session ' + statusBadge(s.status)
          + ': <strong>' + esc(s.repo)
          + '#' + s.issue_number + '</strong>',
        clickType: "session",
        clickId: s.session_id
      });
    }
  });
  items.sort(function(a, b) {
    return new Date(b.time) - new Date(a.time);
  });
  items = items.slice(0, 30);
  if (!items.length) {
    feed.innerHTML = '<div class="empty">No activity yet</div>';
    return;
  }
  feed.innerHTML = items.map(function(it) {
    return '<div class="activity-item clickable" onclick="onActivityClick(\''
      + it.clickType + '\', \'' + esc(String(it.clickId)) + '\')">'
      + '<div class="activity-dot ' + it.dot + '"></div>'
      + '<div class="activity-content">'
      + '<div class="title">' + it.html + '</div>'
      + '<div class="time">' + relTime(it.time) + '</div>'
      + '</div></div>';
  }).join("");
}

/* ---------- Refresh loop ---------- */
function refresh() {
  loadHealth();
  loadStats();
  loadEvents();
  loadSessions();
}
refresh();
setInterval(refresh, 5000);
</script>
</body>
</html>
"""

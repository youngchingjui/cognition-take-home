"""Self-contained dashboard HTML served by the FastAPI app."""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Devin Issue Remediation — Dashboard</title>
<style>
  :root {
    --bg: #0d1117; --surface: #161b22; --border: #30363d;
    --text: #e6edf3; --muted: #8b949e; --accent: #58a6ff;
    --green: #3fb950; --red: #f85149; --yellow: #d29922;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.5; padding: 24px;
  }
  h1 { font-size: 1.5rem; margin-bottom: 8px; }
  .subtitle { color: var(--muted); margin-bottom: 24px; font-size: 0.875rem; }
  .tabs { display: flex; gap: 4px; margin-bottom: 16px; }
  .tab {
    padding: 8px 16px; border-radius: 6px 6px 0 0; cursor: pointer;
    background: var(--surface); border: 1px solid var(--border); border-bottom: none;
    color: var(--muted); font-size: 0.875rem; transition: all 0.15s;
  }
  .tab.active {
    color: var(--text); background: var(--bg); border-bottom: 2px solid var(--accent);
  }
  .panel { display: none; }
  .panel.active { display: block; }
  table {
    width: 100%; border-collapse: collapse; background: var(--surface);
    border-radius: 6px; overflow: hidden; font-size: 0.85rem;
  }
  th, td {
    padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border);
  }
  th {
    color: var(--muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase;
  }
  tr:last-child td { border-bottom: none; }
  tr:hover { background: rgba(88,166,255,0.04); }
  .badge {
    display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 0.75rem; font-weight: 600;
  }
  .badge-green { background: rgba(63,185,80,0.15); color: var(--green); }
  .badge-red { background: rgba(248,81,73,0.15); color: var(--red); }
  .badge-yellow { background: rgba(210,153,34,0.15); color: var(--yellow); }
  .badge-blue { background: rgba(88,166,255,0.15); color: var(--accent); }
  .badge-muted { background: rgba(139,148,158,0.15); color: var(--muted); }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .empty { text-align: center; padding: 40px; color: var(--muted); }
  .refresh-info { color: var(--muted); font-size: 0.75rem; margin-top: 12px; }
  .header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 24px;
  }
  .health { display: flex; align-items: center; gap: 8px; font-size: 0.85rem; }
  .health-dot {
    width: 8px; height: 8px; border-radius: 50%; background: var(--green);
  }
  .health-dot.down { background: var(--red); }
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>Devin Issue Remediation</h1>
    <div class="subtitle">Dashboard &mdash; webhook events and Devin session activity</div>
  </div>
  <div class="health">
    <span class="health-dot" id="health-dot"></span>
    <span id="health-text">Checking&hellip;</span>
  </div>
</div>

<div class="tabs">
  <div class="tab active" data-tab="sessions">Sessions</div>
  <div class="tab" data-tab="events">Webhook Events</div>
</div>

<div id="sessions" class="panel active">
  <table>
    <thead>
      <tr>
        <th>Session</th><th>Repository</th><th>Issue</th>
        <th>Status</th><th>Created</th><th>Updated</th>
      </tr>
    </thead>
    <tbody id="sessions-body">
      <tr><td colspan="6" class="empty">Loading&hellip;</td></tr>
    </tbody>
  </table>
</div>

<div id="events" class="panel">
  <table>
    <thead>
      <tr>
        <th>Time</th><th>Event</th><th>Action</th><th>Repository</th>
        <th>Issue</th><th>Label</th><th>Status</th>
      </tr>
    </thead>
    <tbody id="events-body">
      <tr><td colspan="7" class="empty">Loading&hellip;</td></tr>
    </tbody>
  </table>
</div>

<div class="refresh-info">Auto-refreshes every 10 seconds</div>

<script>
document.querySelectorAll(".tab").forEach(function(tab) {
  tab.addEventListener("click", function() {
    document.querySelectorAll(".tab").forEach(function(t) { t.classList.remove("active"); });
    document.querySelectorAll(".panel").forEach(function(p) { p.classList.remove("active"); });
    tab.classList.add("active");
    document.getElementById(tab.dataset.tab).classList.add("active");
  });
});

function statusBadge(s) {
  var map = {
    finished: "badge-green", completed: "badge-green", session_created: "badge-blue",
    running: "badge-blue", created: "badge-blue",
    error: "badge-red", stopped: "badge-red",
    timed_out: "badge-yellow", ignored: "badge-muted"
  };
  var cls = map[s] || "badge-muted";
  return '<span class="badge ' + cls + '">' + esc(s) + "</span>";
}

function fmtTime(iso) {
  if (!iso) return "\\u2014";
  return new Date(iso).toLocaleString();
}

function esc(s) {
  if (s == null) return "";
  var d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

async function loadHealth() {
  try {
    var r = await fetch("/health");
    var d = await r.json();
    document.getElementById("health-dot").classList.remove("down");
    document.getElementById("health-text").textContent =
      "Online \\u2014 " + d.active_sessions + " active session" +
      (d.active_sessions !== 1 ? "s" : "");
  } catch(e) {
    document.getElementById("health-dot").classList.add("down");
    document.getElementById("health-text").textContent = "Offline";
  }
}

async function loadSessions() {
  try {
    var r = await fetch("/api/sessions");
    var data = await r.json();
    var tbody = document.getElementById("sessions-body");
    if (!data.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty">No sessions yet</td></tr>';
      return;
    }
    tbody.innerHTML = data.map(function(s) {
      return "<tr>" +
        '<td><a href="' + esc(s.session_url) + '" target="_blank">' +
          esc(s.session_id) + "</a></td>" +
        "<td>" + esc(s.repo) + "</td>" +
        "<td>#" + s.issue_number +
          (s.issue_title ? " \\u2014 " + esc(s.issue_title) : "") + "</td>" +
        "<td>" + statusBadge(s.status) + "</td>" +
        "<td>" + fmtTime(s.created_at) + "</td>" +
        "<td>" + fmtTime(s.updated_at) + "</td>" +
      "</tr>";
    }).join("");
  } catch(e) { /* ignore */ }
}

async function loadEvents() {
  try {
    var r = await fetch("/api/events");
    var data = await r.json();
    var tbody = document.getElementById("events-body");
    if (!data.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">No events yet</td></tr>';
      return;
    }
    tbody.innerHTML = data.map(function(ev) {
      return "<tr>" +
        "<td>" + fmtTime(ev.received_at) + "</td>" +
        "<td>" + esc(ev.event_type) + "</td>" +
        "<td>" + (ev.action ? esc(ev.action) : "\\u2014") + "</td>" +
        "<td>" + (ev.repo ? esc(ev.repo) : "\\u2014") + "</td>" +
        "<td>" + (ev.issue_number != null ? "#" + ev.issue_number : "\\u2014") + "</td>" +
        "<td>" + (ev.label ? esc(ev.label) : "\\u2014") + "</td>" +
        "<td>" + statusBadge(ev.status) + "</td>" +
      "</tr>";
    }).join("");
  } catch(e) { /* ignore */ }
}

function refresh() { loadHealth(); loadSessions(); loadEvents(); }
refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""

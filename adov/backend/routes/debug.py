from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from services.activity_log import clear_events, get_events

router = APIRouter()

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Adov Activity Log</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0d1117;
    color: #c9d1d9;
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 13px;
    padding: 20px;
  }
  header {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 16px;
  }
  h1 { font-size: 16px; font-weight: 600; color: #f0f6fc; }
  #status {
    font-size: 11px;
    color: #3fb950;
    background: #1a2b1a;
    border: 1px solid #2ea043;
    border-radius: 10px;
    padding: 2px 8px;
  }
  button {
    margin-left: auto;
    background: #21262d;
    color: #8b949e;
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 4px 12px;
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
  }
  button:hover { background: #30363d; color: #c9d1d9; }
  table { width: 100%; border-collapse: collapse; }
  th {
    text-align: left;
    color: #8b949e;
    font-weight: 400;
    padding: 4px 8px;
    border-bottom: 1px solid #21262d;
    white-space: nowrap;
  }
  td {
    padding: 5px 8px;
    border-bottom: 1px solid #161b22;
    vertical-align: top;
  }
  tr:hover td { background: #161b22; }
  .ts { color: #8b949e; white-space: nowrap; }
  .event { white-space: nowrap; }
  .ev-preference_extracted { color: #79c0ff; }
  .ev-ai_reply            { color: #a5d6ff; }
  .ev-wishpool_added      { color: #56d364; }
  .ev-travel_content_parsed { color: #d2a8ff; }
  .ev-proposals_generated { color: #ffa657; }
  .ev-adov_mention        { color: #ff7b72; }
  .ev-image_uploaded      { color: #e3b341; }
  .ev-image_analyzed      { color: #f0883e; }
  .detail { color: #8b949e; word-break: break-word; }
  #empty { color: #484f58; padding: 20px 8px; }
</style>
</head>
<body>
<header>
  <h1>Adov Activity Log</h1>
  <span id="status">live &bull; refreshes every 2s</span>
  <button onclick="clearLog()">Clear</button>
</header>
<table>
  <thead>
    <tr><th>Time</th><th>Event</th><th>Details</th></tr>
  </thead>
  <tbody id="body"></tbody>
</table>
<div id="empty" style="display:none">No events yet. Start chatting to see activity.</div>

<script>
function fmt(ev) {
  const d = {...ev};
  delete d.ts; delete d.event;
  const parts = [];
  for (const [k, v] of Object.entries(d)) {
    if (v === null || v === undefined) continue;
    const val = typeof v === 'object' ? JSON.stringify(v) : v;
    parts.push(k + '=' + val);
  }
  return parts.join('  ');
}

async function refresh() {
  try {
    const r = await fetch('/api/debug/activity?limit=50');
    const events = await r.json();
    const tbody = document.getElementById('body');
    const empty = document.getElementById('empty');
    if (!events.length) {
      tbody.innerHTML = '';
      empty.style.display = 'block';
      return;
    }
    empty.style.display = 'none';
    tbody.innerHTML = events.map(ev => `
      <tr>
        <td class="ts">${ev.ts.slice(11, 19)}</td>
        <td class="event ev-${ev.event}">${ev.event}</td>
        <td class="detail">${fmt(ev)}</td>
      </tr>`).join('');
  } catch(e) { /* server restarting */ }
}

async function clearLog() {
  await fetch('/api/debug/activity', {method: 'DELETE'});
  refresh();
}

refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""


@router.get("/api/debug/activity")
def get_activity(limit: int = 50):
    return get_events(limit)


@router.delete("/api/debug/activity")
def delete_activity():
    clear_events()
    return {"ok": True}


@router.get("/debug", response_class=HTMLResponse)
def debug_page():
    return _HTML

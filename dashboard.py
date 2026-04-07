"""
dashboard.py — Crawler status хуудас
Ажиллуулах: python dashboard.py
Хандах: http://localhost:8080
"""
from flask import Flask, jsonify, render_template_string
from src.db import get_connection

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="mn">
<head>
  <meta charset="UTF-8">
  <title>ダッシュボード</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: sans-serif; background: #f4f4f4; padding: 24px; }
    h1 { margin-bottom: 20px; font-size: 22px; color: #333; }
    .cards { display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }
    .card { background: #fff; border-radius: 10px; padding: 20px 28px; min-width: 140px;
            box-shadow: 0 1px 4px rgba(0,0,0,.1); text-align: center; }
    .card .num { font-size: 36px; font-weight: bold; }
    .card .label { font-size: 13px; color: #888; margin-top: 4px; }
    .done { color: #22c55e; }
    .error { color: #ef4444; }
    .pending { color: #f59e0b; }
    .total { color: #3b82f6; }
    table { width: 100%; background: #fff; border-radius: 10px;
            box-shadow: 0 1px 4px rgba(0,0,0,.1); border-collapse: collapse; }
    th { background: #f8f8f8; text-align: left; padding: 10px 14px;
         font-size: 13px; color: #555; border-bottom: 1px solid #eee; }
    td { padding: 10px 14px; font-size: 13px; border-bottom: 1px solid #f0f0f0;
         max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    tr:last-child td { border-bottom: none; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 9px; font-size: 11px; font-weight: bold; }
    .badge-done { background: #dcfce7; color: #16a34a; }
    .badge-error { background: #fee2e2; color: #dc2626; }
    .badge-pending { background: #fef3c7; color: #d97706; }
    .updated { font-size: 12px; color: #aaa; margin-bottom: 16px; }
  </style>
</head>
<body>
  <h1>ダッシュボード</h1>
  <p class="updated" id="updated">更新中...</p>
  <div class="cards">
    <div class="card"><div class="num total" id="c-total">-</div><div class="label">合計</div></div>
    <div class="card"><div class="num done" id="c-done">-</div><div class="label">成功</div></div>
    <div class="card"><div class="num error" id="c-error">-</div><div class="label">エラー</div></div>
    <div class="card"><div class="num pending" id="c-pending">-</div><div class="label">処理待ち</div></div>
    <div class="card"><div class="num total" id="c-progress">-</div><div class="label">実行中</div></div>
  </div>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Prompt</th>
        <th>ChatGPT 回答 / エラー</th>
        <th>ステータス</th>
        <th>日付</th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>

  <script>
    let knownIds = new Set();

    function updateStats(stats) {
      document.getElementById('c-total').textContent = stats.total;
      document.getElementById('c-done').textContent = stats.done;
      document.getElementById('c-error').textContent = stats.error;
      document.getElementById('c-pending').textContent = stats.pending;
      document.getElementById('c-progress').textContent = stats.progress + '%';
    }

    function addRows(rows) {
      const tbody = document.getElementById('tbody');
      rows.forEach(r => {
        if (knownIds.has(r.sheet_row)) return;
        knownIds.add(r.sheet_row);
        const tr = document.createElement('tr');
        const prompt = r.prompt ? r.prompt.substring(0, 60) + (r.prompt.length > 60 ? '...' : '') : '';
        const display = r.status === 'error' ? (r.error_message || '') : (r.response || '');
        const displayShort = display.substring(0, 80) + (display.length > 80 ? '...' : '');
        const cellStyle = r.status === 'error' ? ' style="color:#dc2626"' : '';
        tr.innerHTML = `
          <td>${r.sheet_row}</td>
          <td title="${r.prompt || ''}">${prompt}</td>
          <td title="${display}"${cellStyle}>${displayShort}</td>
          <td><span class="badge badge-${r.status}">${r.status}</span></td>
          <td>${r.created_at || ''}</td>
        `;
        tbody.insertBefore(tr, tbody.firstChild);
      });
    }

    async function refresh() {
      try {
        const res = await fetch('/api/all');
        const data = await res.json();
        updateStats(data.stats);
        addRows(data.rows);
        const now = new Date().toLocaleTimeString();
        document.getElementById('updated').textContent = 'Сүүлд шинэчлэгдсэн: ' + now;
      } catch(e) {}
    }

    refresh();
    setInterval(refresh, 10000);
  </script>
</body>
</html>
"""


def get_data():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) as total FROM responses")
    total = cur.fetchone()["total"]
    cur.execute("SELECT status, COUNT(*) as cnt FROM responses GROUP BY status")
    counts = {r["status"]: r["cnt"] for r in cur.fetchall()}
    cur.execute("SELECT sheet_row, prompt, response, error_message, status, created_at FROM responses ORDER BY id DESC LIMIT 100")
    rows = cur.fetchall()
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = str(r["created_at"])
    cur.close()
    conn.close()
    done = counts.get("done", 0)
    error = counts.get("error", 0)
    pending = total - done - error
    progress = round(done / total * 100, 1) if total > 0 else 0
    stats = {"total": total, "done": done, "error": error, "pending": pending, "progress": progress}
    return stats, rows


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/all")
def api_all():
    stats, rows = get_data()
    return jsonify({"stats": stats, "rows": rows})


@app.route("/api/stats")
def api_stats():
    stats, _ = get_data()
    return jsonify(stats)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

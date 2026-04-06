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
  <meta http-equiv="refresh" content="10">
  <title>Crawler Dashboard</title>
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
  <h1>Crawler Dashboard</h1>
  <p class="updated">10 секунд тутам шинэчлэгдэнэ</p>
  <div class="cards">
    <div class="card"><div class="num total">{{ stats.total }}</div><div class="label">Нийт</div></div>
    <div class="card"><div class="num done">{{ stats.done }}</div><div class="label">Амжилттай</div></div>
    <div class="card"><div class="num error">{{ stats.error }}</div><div class="label">Алдаа</div></div>
    <div class="card"><div class="num pending">{{ stats.pending }}</div><div class="label">Хүлээгдэж буй</div></div>
    <div class="card"><div class="num total">{{ stats.progress }}%</div><div class="label">Гүйцэтгэл</div></div>
  </div>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Prompt</th>
        <th>ChatGPT хариулт</th>
        <th>Статус</th>
        <th>Огноо</th>
      </tr>
    </thead>
    <tbody>
      {% for r in rows %}
      <tr>
        <td>{{ r.sheet_row }}</td>
        <td title="{{ r.prompt }}">{{ r.prompt[:60] }}{% if r.prompt|length > 60 %}...{% endif %}</td>
        <td title="{{ r.response }}">{{ (r.response or '')[:80] }}{% if (r.response or '')|length > 80 %}...{% endif %}</td>
        <td><span class="badge badge-{{ r.status }}">{{ r.status }}</span></td>
        <td>{{ r.created_at }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""


def get_stats():
    conn = get_connection()
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) as total FROM responses")
    total = cur.fetchone()["total"]
    cur.execute("SELECT status, COUNT(*) as cnt FROM responses GROUP BY status")
    counts = {r["status"]: r["cnt"] for r in cur.fetchall()}
    cur.execute("SELECT sheet_row, prompt, response, status, created_at FROM responses ORDER BY id DESC LIMIT 50")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    done = counts.get("done", 0)
    error = counts.get("error", 0)
    pending = total - done - error
    progress = round(done / total * 100, 1) if total > 0 else 0
    return {"total": total, "done": done, "error": error, "pending": pending, "progress": progress}, rows


@app.route("/")
def index():
    stats, rows = get_stats()
    return render_template_string(HTML, stats=stats, rows=rows)


@app.route("/api/stats")
def api_stats():
    stats, _ = get_stats()
    return jsonify(stats)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

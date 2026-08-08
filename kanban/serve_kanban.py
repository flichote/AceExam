#!/usr/bin/env python3
"""AceExam 实时 kanban 看板服务。

- GET /            → 看板页面（HTML，内嵌 JS 每 30s 自动刷新）
- GET /api/board   → 看板数据 JSON（实时读 kanban.db）

用法: python serve_kanban.py [--port 8090]
"""
import argparse
import json
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DB = Path(r"E:\agents\hermes\kanban\boards\aceexam\kanban.db")

STATUS_META = {
    "todo": ("◻", "#6B7280"), "ready": ("▶", "#3B82F6"),
    "running": ("●", "#F59E0B"), "blocked": ("⊘", "#EF4444"),
    "done": ("✓", "#10B981"), "archived": ("🗄", "#9CA3AF"),
    "cancelled": ("✕", "#9CA3AF"),
}
ROLE_NAMES = {
    "ep-arch": "架构师", "ep-ai": "AI 工程师", "ep-backend": "后端",
    "ep-frontend": "前端", "ep-db": "数据库", "ep-qa": "测试",
}


def fmt_ts(ts):
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(ts).strftime("%m-%d %H:%M")
    except Exception:
        return "—"


def load_board():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, assignee, status, created_at, started_at, completed_at,
               last_failure_error, worker_pid
        FROM tasks WHERE status != 'archived' ORDER BY created_at
    """)
    rows = cur.fetchall()
    tasks = []
    for r in rows:
        cur.execute(
            "SELECT body, created_at FROM task_comments WHERE task_id=? ORDER BY created_at DESC LIMIT 2",
            (r["id"],),
        )
        comments = [{"text": c[0][:180], "ts": fmt_ts(c[1])} for c in cur.fetchall()]
        tasks.append({
            "id": r["id"], "title": r["title"],
            "assignee": r["assignee"], "role": ROLE_NAMES.get(r["assignee"], r["assignee"]),
            "status": r["status"], "created": fmt_ts(r["created_at"]),
            "started": fmt_ts(r["started_at"]), "completed": fmt_ts(r["completed_at"]),
            "err": (r["last_failure_error"] or "")[:120], "pid": r["worker_pid"],
            "comments": comments,
        })
    conn.close()
    return tasks


PAGE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>AceExam 开发看板（实时）</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Microsoft YaHei", sans-serif; background: #111827; color: #E5E7EB; padding: 16px; }
  h1 { font-size: 20px; margin-bottom: 4px; }
  .sub { color: #9CA3AF; font-size: 12px; margin-bottom: 16px; }
  .stats { display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }
  .stat { background: #1F2937; border-radius: 10px; padding: 10px 16px; min-width: 90px; }
  .stat .n { font-size: 24px; font-weight: 700; }
  .stat .l { font-size: 11px; color: #9CA3AF; }
  .progress { background: #1F2937; border-radius: 99px; height: 10px; margin-bottom: 18px; overflow: hidden; }
  .progress > div { height: 100%; background: linear-gradient(90deg,#F59E0B,#10B981); width: 0%; transition: width .5s; }
  .board { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
  .col { background: #1F2937; border-radius: 12px; overflow: hidden; }
  .col-head { padding: 10px 12px; font-weight: 700; font-size: 13px; border-bottom: 2px solid; background: #11182766; }
  .cnt { float: right; background: #374151; border-radius: 99px; padding: 1px 8px; font-size: 11px; }
  .col-body { padding: 8px; min-height: 120px; }
  .card { background: #111827; border-radius: 8px; padding: 10px; margin-bottom: 8px; border: 1px solid #374151; }
  .card.running { border-color: #F59E0B55; }
  .card.done { opacity: 0.75; }
  .card-head { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
  .badge { font-size: 11px; padding: 1px 8px; border-radius: 99px; color: #fff; font-weight: 600; }
  .role { font-size: 11px; background: #374151; padding: 1px 8px; border-radius: 99px; }
  .tid { font-size: 10px; color: #6B7280; margin-left: auto; }
  .title { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
  .meta { font-size: 10px; color: #9CA3AF; margin-bottom: 4px; }
  .err { font-size: 11px; color: #FCA5A5; background: #7F1D1D33; border-radius: 6px; padding: 4px 6px; margin: 4px 0; }
  .comments { border-top: 1px dashed #374151; padding-top: 4px; margin-top: 4px; }
  .cmt { font-size: 10px; color: #9CA3AF; }
  .muted { color: #4B5563; }
  .empty { color: #4B5563; text-align: center; padding: 20px 0; font-size: 12px; }
  @media (max-width: 1200px) { .board { grid-template-columns: repeat(2, 1fr); } }
</style>
</head>
<body>
<h1>📋 AceExam 开发看板 <span id="live" style="font-size:12px;color:#10B981">● LIVE</span></h1>
<div class="sub">M1 地基 → M2 五件套 → M3 增长 → M3.5 剩余功能 · 最后更新 <span id="ts">—</span> · 每 30s 自动刷新</div>
<div class="stats" id="stats"></div>
<div class="progress"><div id="bar"></div></div>
<div class="board" id="board"></div>
<script>
const STATUS = {todo:["◻","#6B7280"],ready:["▶","#3B82F6"],running:["●","#F59E0B"],blocked:["⊘","#EF4444"],done:["✓","#10B981"],archived:["🗄","#9CA3AF"],cancelled:["✕","#9CA3AF"]};
const ORDER = ["todo","ready","running","blocked","done"];
function esc(s){return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;");}
function card(t){
  const [sym,color] = STATUS[t.status]||["?","#999"];
  const err = t.err ? `<div class="err">⚠ ${esc(t.err)}</div>` : "";
  const cmts = (t.comments||[]).map(c=>`<div class="cmt"><b>${esc(c.ts)}</b> ${esc(c.text)}</div>`).join("") || `<div class="cmt muted">（无评论）</div>`;
  return `<div class="card ${t.status}">
    <div class="card-head"><span class="badge" style="background:${color}">${sym} ${t.status}</span>
    <span class="role">${esc(t.role)}</span><span class="tid">${t.id}</span></div>
    <div class="title">${esc(t.title)}</div>
    <div class="meta">创建 ${t.created} · 开始 ${t.started} · 完成 ${t.completed}${t.pid?` · pid ${t.pid}`:""}</div>
    ${err}<div class="comments">${cmts}</div></div>`;
}
async function refresh(){
  try{
    const r = await fetch("/api/board", {cache:"no-store"});
    const data = await r.json();
    const counts = {}; data.forEach(t=>counts[t.status]=(counts[t.status]||0)+1);
    const total = data.length, done = counts.done||0, pct = total?Math.round(done/total*100):0;
    document.getElementById("ts").textContent = new Date().toLocaleString("zh-CN");
    document.getElementById("bar").style.width = pct + "%";
    document.getElementById("stats").innerHTML =
      `<div class="stat"><div class="n" style="color:#10B981">${done}</div><div class="l">完成</div></div>`+
      `<div class="stat"><div class="n" style="color:#F59E0B">${counts.running||0}</div><div class="l">进行中</div></div>`+
      `<div class="stat"><div class="n" style="color:#EF4444">${counts.blocked||0}</div><div class="l">阻塞</div></div>`+
      `<div class="stat"><div class="n" style="color:#3B82F6">${counts.ready||0}</div><div class="l">待派发</div></div>`+
      `<div class="stat"><div class="n">${total}</div><div class="l">总数</div></div>`;
    document.getElementById("board").innerHTML = ORDER.map(s=>{
      const [sym,color] = STATUS[s];
      const cards = data.filter(t=>t.status===s).map(card).join("");
      return `<div class="col"><div class="col-head" style="border-color:${color}"><span style="color:${color}">${sym}</span> ${s.toUpperCase()} <span class="cnt">${counts[s]||0}</span></div><div class="col-body">${cards||'<div class="empty">—</div>'}</div></div>`;
    }).join("");
  }catch(e){ document.getElementById("ts").textContent = "刷新失败: "+e.message; }
}
refresh(); setInterval(refresh, 30000);
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/board":
            try:
                data = load_board()
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        else:
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # 静默访问日志


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8090)
    args = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"✅ 实时看板服务: http://127.0.0.1:{args.port}  (每 30s 自动刷新)")
    srv.serve_forever()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""AceExam kanban 看板生成器：读 kanban.db → 输出 HTML 看板（带自动刷新）。

用法: python gen_kanban_html.py  →  输出 kanban-dashboard.html
（可由 cron 定期重跑，或浏览器端 JS 定时 fetch 本地文件）
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB = Path(r"E:\agents\hermes\kanban\boards\aceexam\kanban.db")
OUT = Path(__file__).parent / "kanban-dashboard.html"

STATUS_META = {
    "todo":    ("◻", "#6B7280", "todo"),
    "ready":   ("▶", "#3B82F6", "ready"),
    "running": ("●", "#F59E0B", "running"),
    "blocked": ("⊘", "#EF4444", "blocked"),
    "done":    ("✓", "#10B981", "done"),
    "archived":("🗄", "#9CA3AF", "archived"),
    "cancelled":("✕", "#9CA3AF", "cancelled"),
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


def load_tasks():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, title, assignee, status, priority, created_at, started_at,
               completed_at, last_failure_error, worker_pid, session_id
        FROM tasks WHERE status != 'archived' ORDER BY created_at
    """)
    rows = cur.fetchall()
    # comments per task (latest 2)
    tasks = []
    for r in rows:
        tid, title, assignee, status, prio, created, started, completed, err, pid, sid = r
        cur.execute(
            "SELECT body, created_at FROM task_comments WHERE task_id=? ORDER BY created_at DESC LIMIT 2",
            (tid,),
        )
        comments = [{"text": c[0][:180], "ts": fmt_ts(c[1])} for c in cur.fetchall()]
        tasks.append({
            "id": tid, "title": title, "assignee": assignee,
            "role": ROLE_NAMES.get(assignee, assignee),
            "status": status, "created": fmt_ts(created),
            "started": fmt_ts(started), "completed": fmt_ts(completed),
            "err": (err or "")[:120], "pid": pid, "comments": comments,
        })
    conn.close()
    return tasks


def render(tasks):
    groups = {"todo": [], "ready": [], "running": [], "blocked": [], "done": []}
    for t in tasks:
        groups.setdefault(t["status"], []).append(t)
    counts = {k: len(v) for k, v in groups.items()}
    total = len(tasks)
    done = counts.get("done", 0)
    pct = round(done / total * 100) if total else 0

    def card(t):
        sym, color, _ = STATUS_META.get(t["status"], ("?", "#999", ""))
        err_html = f'<div class="err">⚠ {t["err"]}</div>' if t["err"] else ""
        comments = "".join(
            f'<div class="cmt"><b>{c["ts"]}</b> {c["text"]}</div>' for c in t["comments"]
        ) or '<div class="cmt muted">（无评论）</div>'
        return f"""
        <div class="card {t['status']}">
          <div class="card-head">
            <span class="badge" style="background:{color}">{sym} {t['status']}</span>
            <span class="role">{t['role']}</span>
            <span class="tid">{t['id']}</span>
          </div>
          <div class="title">{t['title']}</div>
          <div class="meta">
            创建 {t['created']} · 开始 {t['started']} · 完成 {t['completed']}
            {f' · pid {t["pid"]}' if t['pid'] else ''}
          </div>
          {err_html}
          <div class="comments">{comments}</div>
        </div>"""

    cols = ""
    for status in ["todo", "ready", "running", "blocked", "done"]:
        sym, color, _ = STATUS_META[status]
        cards = "".join(card(t) for t in groups.get(status, []))
        cols += f"""
        <div class="col">
          <div class="col-head" style="border-color:{color}">
            <span style="color:{color}">{sym}</span> {status.upper()}
            <span class="cnt">{counts.get(status, 0)}</span>
          </div>
          <div class="col-body">{cards or '<div class="empty">—</div>'}</div>
        </div>"""

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>AceExam 开发看板</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Microsoft YaHei", sans-serif; background: #111827; color: #E5E7EB; padding: 16px; }}
  h1 {{ font-size: 20px; margin-bottom: 4px; }}
  .sub {{ color: #9CA3AF; font-size: 12px; margin-bottom: 16px; }}
  .stats {{ display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
  .stat {{ background: #1F2937; border-radius: 10px; padding: 10px 16px; min-width: 90px; }}
  .stat .n {{ font-size: 24px; font-weight: 700; }}
  .stat .l {{ font-size: 11px; color: #9CA3AF; }}
  .progress {{ background: #1F2937; border-radius: 99px; height: 10px; margin-bottom: 18px; overflow: hidden; }}
  .progress > div {{ height: 100%; background: linear-gradient(90deg,#F59E0B,#10B981); width: {pct}%; }}
  .board {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }}
  .col {{ background: #1F2937; border-radius: 12px; overflow: hidden; }}
  .col-head {{ padding: 10px 12px; font-weight: 700; font-size: 13px; border-bottom: 2px solid; background: #11182766; }}
  .cnt {{ float: right; background: #374151; border-radius: 99px; padding: 1px 8px; font-size: 11px; }}
  .col-body {{ padding: 8px; min-height: 120px; }}
  .card {{ background: #111827; border-radius: 8px; padding: 10px; margin-bottom: 8px; border: 1px solid #374151; }}
  .card.running {{ border-color: #F59E0B55; }}
  .card.done {{ opacity: 0.75; }}
  .card-head {{ display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }}
  .badge {{ font-size: 11px; padding: 1px 8px; border-radius: 99px; color: #fff; font-weight: 600; }}
  .role {{ font-size: 11px; background: #374151; padding: 1px 8px; border-radius: 99px; }}
  .tid {{ font-size: 10px; color: #6B7280; margin-left: auto; }}
  .title {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; }}
  .meta {{ font-size: 10px; color: #9CA3AF; margin-bottom: 4px; }}
  .err {{ font-size: 11px; color: #FCA5A5; background: #7F1D1D33; border-radius: 6px; padding: 4px 6px; margin: 4px 0; }}
  .comments {{ border-top: 1px dashed #374151; padding-top: 4px; margin-top: 4px; }}
  .cmt {{ font-size: 10px; color: #9CA3AF; }}
  .muted {{ color: #4B5563; }}
  .empty {{ color: #4B5563; text-align: center; padding: 20px 0; font-size: 12px; }}
  @media (max-width: 1200px) {{ .board {{ grid-template-columns: repeat(2, 1fr); }} }}
</style>
</head>
<body>
<h1>📋 AceExam 开发看板</h1>
<div class="sub">M1 地基 + M2 MVP 五件套 · 更新于 {now} · 数据源 kanban.db</div>
<div class="stats">
  <div class="stat"><div class="n" style="color:#10B981">{done}</div><div class="l">完成</div></div>
  <div class="stat"><div class="n" style="color:#F59E0B">{counts.get('running', 0)}</div><div class="l">进行中</div></div>
  <div class="stat"><div class="n" style="color:#EF4444">{counts.get('blocked', 0)}</div><div class="l">阻塞</div></div>
  <div class="stat"><div class="n" style="color:#3B82F6">{counts.get('ready', 0)}</div><div class="l">待派发</div></div>
  <div class="stat"><div class="n">{total}</div><div class="l">总数</div></div>
</div>
<div class="progress"><div></div></div>
<div class="board">{cols}</div>
<script>
  // 每 60s 自动重载（本地文件场景：重新打开即可刷新；服务器场景可改为 fetch）
  setTimeout(() => location.reload(), 60000);
</script>
</body>
</html>"""


def main():
    tasks = load_tasks()
    OUT.write_text(render(tasks), encoding="utf-8")
    print(f"✅ 看板已生成: {OUT} ({len(tasks)} 任务)")


if __name__ == "__main__":
    main()

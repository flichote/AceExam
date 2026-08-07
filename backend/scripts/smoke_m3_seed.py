"""M3 seed 冒烟验证：临时 SQLite 库跑 seed，校验演示数据 + 连胜语义。

用法：cd backend && env -u PYTHONPATH .venv/Scripts/python.exe ../scripts/smoke_m3_seed.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path

BACKEND = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, BACKEND)

DB = str(Path(BACKEND) / "_seed_smoke.db")
if os.path.exists(DB):
    os.remove(DB)
URL = f"sqlite:///{DB}"

# SQLite 兼容（JSONB→JSON + UUID bind）
from app.db import sqlite_compat  # noqa: F401,E402
from app.db.base import Base  # noqa: E402
from app.db import models  # noqa: E402,F401
from app.db.seed import seed  # noqa: E402

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

engine = create_engine(URL)
Base.metadata.create_all(engine)
print("[smoke] create_all ok, tables:", len(Base.metadata.tables))

seed(URL, reset=True)

with Session(engine) as s:
    n_users = s.scalar(select(func.count()).select_from(models.User))
    n_plans = s.scalar(select(func.count()).select_from(models.Plan))
    n_sessions = s.scalar(select(func.count()).select_from(models.StudySession))
    n_ukstate = s.scalar(select(func.count()).select_from(models.UserKnowledgeState))
    n_sprint = s.scalar(select(func.count()).select_from(models.SprintSession))
    print(f"[smoke] users={n_users} plans={n_plans} study_sessions={n_sessions} ukstates={n_ukstate} sprint_sessions={n_sprint}")
    assert n_users == 3, n_users
    assert n_sprint == 1, n_sprint
    assert n_plans == 2, n_plans

    # 连胜语义校验（D7）：demo_student1 current=5 longest=8；demo_student2 current=14 longest=14
    from app.services.streak import compute_streak

    today = datetime.now().date()
    rows = s.execute(
        select(models.StudySession.session_date)
        .where(models.StudySession.user_id == models.User.id, models.User.username == "demo_student1", models.StudySession.checked_in.is_(True))
    ).scalars().all()
    cur, longest = compute_streak(sorted(rows), today=today)
    print(f"[smoke] demo_student1 checked_in_days={len(rows)} current={cur} longest={longest} (expect 5/8)")
    assert cur == 5 and longest == 8, (cur, longest)

    rows2 = s.execute(
        select(models.StudySession.session_date)
        .where(models.StudySession.user_id == models.User.id, models.User.username == "demo_student2", models.StudySession.checked_in.is_(True))
    ).scalars().all()
    cur2, longest2 = compute_streak(sorted(rows2), today=today)
    print(f"[smoke] demo_student2 checked_in_days={len(rows2)} current={cur2} longest={longest2} (expect 14/14)")
    assert cur2 == 14 and longest2 == 14, (cur2, longest2)

    # 排行榜口径：demo_student2 做题量 ≥30（进榜）；demo_free 做题量 <30（不进榜）
    stats = s.execute(
        select(models.User.username, func.coalesce(func.sum(models.StudySession.questions_practiced), 0))
        .join(models.StudySession, models.StudySession.user_id == models.User.id)
        .group_by(models.User.username)
    ).all()
    print("[smoke] per-user total questions:", dict(stats))

    # 突击会话快照字段
    sp = s.execute(select(models.SprintSession)).scalars().first()
    print(f"[smoke] sprint snapshot items={len(sp.question_snapshot)} high_freq_kps={len(sp.high_freq_kps or [])} status={sp.status} expires_at={sp.expires_at}")
    assert len(sp.question_snapshot) == 12
    assert sp.status == "active"

print("[smoke] OK")

"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import auth, chat, dashboard, diagnose, health, knowledge_graph, leaderboard, ocr, plans, questions, sprint, subjects, warnings, wrong_answers, admin, me, courses, ugc
from app.core.config import settings
from app.db import sqlite_compat  # noqa: F401  本地 SQLite 兼容 shim（PG 下无副作用）

sqlite_compat.apply_sqlite_compat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: nothing to do yet (DB engine created lazily)
    yield
    # Shutdown: nothing to clean up yet


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global exception handler ──
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "detail": str(exc) if settings.DEBUG else None,
        },
    )


# ── Routers ──
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(subjects.router, prefix="/api/v1")
app.include_router(questions.router, prefix="/api/v1")
app.include_router(wrong_answers.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(ocr.router, prefix="/api/v1")
app.include_router(diagnose.router, prefix="/api/v1")
app.include_router(plans.router, prefix="/api/v1")
app.include_router(knowledge_graph.router, prefix="/api/v1")
app.include_router(sprint.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(leaderboard.router, prefix="/api/v1")
app.include_router(warnings.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(me.router, prefix="/api/v1")
app.include_router(courses.router, prefix="/api/v1")
app.include_router(ugc.router, prefix="/api/v1")

"""
FastAPI WebApp for Mira Bot.
Настройки и статистика пользователя.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from webapp.api.routes import settings, stats

app = FastAPI(title="Mira Bot WebApp")

# CORS для Telegram WebApp
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://web.telegram.org"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роуты
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])

# Static files
webapp_dir = Path(__file__).parent.parent
app.mount("/static", StaticFiles(directory=str(webapp_dir / "frontend")), name="static")


@app.get("/")
async def index():
    """Главная страница WebApp."""
    return FileResponse(webapp_dir / "frontend" / "index.html")


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}

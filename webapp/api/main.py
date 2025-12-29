"""
FastAPI WebApp for Mira Bot.
Настройки и статистика пользователя.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from webapp.api.routes import settings, stats, referral, export, admin, programs, promo, moderators, admin_logs

app = FastAPI(title="Mira Bot WebApp")

# CORS для Telegram WebApp и админ-панели
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://web.telegram.org",
        "https://mira.uspeshnyy.ru",
        "http://mira.uspeshnyy.ru",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роуты
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(referral.router, prefix="/api/referral", tags=["referral"])
app.include_router(export.router, prefix="/api/export", tags=["export"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(programs.router, prefix="/api/programs", tags=["programs"])
app.include_router(promo.router, prefix="/api/promo", tags=["promo"])
app.include_router(moderators.router, prefix="/api", tags=["moderators"])
app.include_router(admin_logs.router, prefix="/api", tags=["admin-logs"])

# Static files
webapp_dir = Path(__file__).parent.parent
app.mount("/static", StaticFiles(directory=str(webapp_dir / "frontend")), name="static")


@app.get("/")
async def index():
    """Главная страница WebApp."""
    return FileResponse(webapp_dir / "frontend" / "index.html")


@app.get("/admin")
async def admin_panel():
    """Админ-панель."""
    return FileResponse(webapp_dir / "frontend" / "admin.html")


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}

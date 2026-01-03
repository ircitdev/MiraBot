"""
FastAPI WebApp for Mira Bot.
Настройки и статистика пользователя.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from webapp.api.routes import settings, stats, referral, export, admin, programs, promo, moderators, admin_logs, reports, api_costs, system_prompt, support, reviews

app = FastAPI(title="Mira Bot WebApp")

# CORS для Telegram WebApp и админ-панели
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://web.telegram.org",
        "https://miradrug.ru",
        "http://miradrug.ru",
        "https://www.miradrug.ru",
        "http://www.miradrug.ru",
        # Старый домен для обратной совместимости
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
app.include_router(reports.router, prefix="/api/admin", tags=["reports"])
app.include_router(api_costs.router, prefix="/api/admin", tags=["api-costs"])
app.include_router(system_prompt.router, prefix="/api/admin", tags=["system-prompt"])
app.include_router(support.router, prefix="/api/support", tags=["support"])
app.include_router(reviews.router, prefix="/api/support", tags=["reviews"])

# Static files
webapp_dir = Path(__file__).parent.parent
app.mount("/static", StaticFiles(directory=str(webapp_dir / "frontend")), name="static")


@app.get("/")
async def index():
    """Главная страница WebApp."""
    return FileResponse(
        webapp_dir / "frontend" / "index.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/admin")
async def admin_panel():
    """Админ-панель."""
    import time
    return FileResponse(
        webapp_dir / "frontend" / "admin.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Content-Type-Options": "nosniff",
            "ETag": f'"{int(time.time())}"'
        }
    )


@app.get("/CHANGELOG.md")
async def changelog():
    """CHANGELOG файл."""
    changelog_path = Path(__file__).parent.parent.parent / "CHANGELOG.md"
    return FileResponse(
        changelog_path,
        media_type="text/markdown",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )


@app.get("/docs/{date}/{filename}")
async def docs_file(date: str, filename: str):
    """TODO и другие документы."""
    docs_path = Path(__file__).parent.parent.parent / "docs" / date / filename
    if docs_path.exists() and docs_path.is_file():
        return FileResponse(
            docs_path,
            media_type="text/markdown",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"error": "File not found"}


@app.get("/docs/todo_plan/{filename}")
async def todo_plan_file(filename: str):
    """TODO roadmap файлы."""
    docs_path = Path(__file__).parent.parent.parent / "docs" / "todo_plan" / filename
    if docs_path.exists() and docs_path.is_file():
        return FileResponse(
            docs_path,
            media_type="text/markdown",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"error": "File not found"}


@app.get("/health")
async def health():
    """Health check."""
    return {"status": "ok"}

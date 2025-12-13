"""
Admin Panel FastAPI Application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from loguru import logger

from database import init_db, close_db
from admin.routers import dashboard, users, analytics, subscriptions, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management."""
    logger.info("Starting Admin API...")
    await init_db()
    yield
    logger.info("Shutting down Admin API...")
    await close_db()


app = FastAPI(
    title="Mira Bot Admin API",
    description="Административная панель для Mira Bot",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(subscriptions.router, prefix="/api/subscriptions", tags=["subscriptions"])


@app.get("/")
async def root():
    """Health check."""
    return {"status": "ok", "service": "Mira Bot Admin API"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}

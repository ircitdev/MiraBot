"""
Health check service.
HTTP эндпоинт для мониторинга состояния бота.
"""

import asyncio
from aiohttp import web
from datetime import datetime
from typing import Optional, Dict, Any
from loguru import logger

from config.settings import settings
from services.redis_client import redis_client
from database.session import async_session
from sqlalchemy import text


class HealthCheckServer:
    """HTTP сервер для health check."""

    def __init__(self, host: str = "0.0.0.0", port: Optional[int] = None):
        self.host = host
        port = port or settings.HEALTH_CHECK_PORT
        self.port = port
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._start_time: Optional[datetime] = None
        self._bot_running: bool = False

    async def start(self) -> None:
        """Запускает HTTP сервер."""
        self._app = web.Application()
        self._app.router.add_get("/health", self._health_handler)
        self._app.router.add_get("/ready", self._ready_handler)
        self._app.router.add_get("/live", self._live_handler)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()

        self._start_time = datetime.now()
        logger.info(f"Health check server started on http://{self.host}:{self.port}")

    async def stop(self) -> None:
        """Останавливает HTTP сервер."""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        logger.info("Health check server stopped")

    def set_bot_running(self, running: bool) -> None:
        """Устанавливает статус бота."""
        self._bot_running = running

    async def _health_handler(self, request: web.Request) -> web.Response:
        """
        Полная проверка здоровья системы.
        GET /health
        """
        checks: Dict[str, Any] = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": self._get_uptime(),
            "checks": {},
        }

        all_healthy = True

        # Проверка бота
        bot_status = "running" if self._bot_running else "stopped"
        checks["checks"]["bot"] = {
            "status": bot_status,
            "healthy": self._bot_running,
        }
        if not self._bot_running:
            all_healthy = False

        # Проверка Redis
        redis_healthy, redis_info = await self._check_redis()
        checks["checks"]["redis"] = {
            "status": "connected" if redis_healthy else "disconnected",
            "healthy": redis_healthy,
            **redis_info,
        }
        # Redis не критичен — есть fallback

        # Проверка БД
        db_healthy, db_info = await self._check_database()
        checks["checks"]["database"] = {
            "status": "connected" if db_healthy else "error",
            "healthy": db_healthy,
            **db_info,
        }
        if not db_healthy:
            all_healthy = False

        # Общий статус
        if not all_healthy:
            checks["status"] = "unhealthy"
            return web.json_response(checks, status=503)

        return web.json_response(checks)

    async def _ready_handler(self, request: web.Request) -> web.Response:
        """
        Проверка готовности к приёму запросов.
        GET /ready
        """
        if self._bot_running:
            return web.json_response({"status": "ready"})
        return web.json_response({"status": "not_ready"}, status=503)

    async def _live_handler(self, request: web.Request) -> web.Response:
        """
        Проверка живости процесса.
        GET /live
        """
        return web.json_response({
            "status": "alive",
            "uptime_seconds": self._get_uptime(),
        })

    def _get_uptime(self) -> float:
        """Возвращает uptime в секундах."""
        if not self._start_time:
            return 0.0
        return (datetime.now() - self._start_time).total_seconds()

    async def _check_redis(self) -> tuple[bool, Dict[str, Any]]:
        """Проверяет подключение к Redis."""
        try:
            if not redis_client.is_connected:
                return False, {"error": "not_connected"}

            # Пингуем Redis
            await redis_client._redis.ping()
            return True, {}

        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False, {"error": str(e)}

    async def _check_database(self) -> tuple[bool, Dict[str, Any]]:
        """Проверяет подключение к БД."""
        try:
            async with async_session() as session:
                # Простой запрос для проверки
                result = await session.execute(text("SELECT 1"))
                result.fetchone()
                return True, {}

        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False, {"error": str(e)}


# Глобальный экземпляр
health_server = HealthCheckServer()

"""
WebApp Server Launcher.
Запускает FastAPI сервер для Telegram WebApp.
"""

import uvicorn
from pathlib import Path
import sys

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings

if __name__ == "__main__":
    uvicorn.run(
        "webapp.api.main:app",
        host="0.0.0.0",
        port=settings.WEBAPP_PORT,
        reload=True,
        log_level="info",
    )

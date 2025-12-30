"""System prompt management endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

from webapp.api.middleware import get_current_admin, require_admin_role

router = APIRouter(prefix="/system-prompt", tags=["system-prompt"])


class SystemPromptUpdate(BaseModel):
    """System prompt update request."""
    content: str


def get_system_prompt_file_path() -> Path:
    """Get path to system prompt file."""
    return Path(__file__).parent.parent.parent.parent / "ai" / "prompts" / "system_prompt.py"


@router.get("/current")
async def get_current_system_prompt(
    admin_data=Depends(require_admin_role)
):
    """Get current system prompt."""
    system_prompt_file = get_system_prompt_file_path()

    if not system_prompt_file.exists():
        return {
            "version": "1.0",
            "content": "System prompt file not found",
            "updated_at": datetime.now().isoformat(),
        }

    # Read system prompt from file
    content = system_prompt_file.read_text(encoding='utf-8')

    # Get file modification time
    updated_at = datetime.fromtimestamp(system_prompt_file.stat().st_mtime).isoformat()

    return {
        "version": "1.0",
        "content": content,
        "updated_at": updated_at,
    }


@router.get("/history")
async def get_system_prompt_history(
    admin_data=Depends(require_admin_role)
):
    """Get system prompt version history."""
    # TODO: Implement version history storage in database
    # For now, return empty history
    history = []

    # Example structure:
    # history = [
    #     {
    #         "version": "1.1",
    #         "content": "...",
    #         "description": "Updated personality traits",
    #         "created_at": "2025-12-29T10:00:00",
    #     },
    #     {
    #         "version": "1.0",
    #         "content": "...",
    #         "description": "Initial version",
    #         "created_at": "2025-12-01T10:00:00",
    #     },
    # ]

    return {"history": history}


@router.get("/version/{version}")
async def get_system_prompt_version(
    version: str,
    admin_data=Depends(require_admin_role)
):
    """Get specific system prompt version."""
    # TODO: Implement version retrieval from database
    # For now, return current version
    system_prompt_file = get_system_prompt_file_path()

    if not system_prompt_file.exists():
        return {
            "version": version,
            "content": "System prompt file not found",
            "created_at": datetime.now().isoformat(),
            "description": "System prompt version " + version,
        }

    # Read system prompt from file
    content = system_prompt_file.read_text(encoding='utf-8')
    created_at = datetime.fromtimestamp(system_prompt_file.stat().st_mtime).isoformat()

    return {
        "version": version,
        "content": content,
        "created_at": created_at,
        "description": "System prompt version " + version,
    }


@router.post("/update")
async def update_system_prompt(
    data: SystemPromptUpdate,
    admin_data=Depends(require_admin_role)
):
    """Update system prompt."""
    import shutil
    from loguru import logger

    system_prompt_file = get_system_prompt_file_path()

    # Validate content
    if not data.content or len(data.content.strip()) == 0:
        raise HTTPException(status_code=400, detail="System prompt content cannot be empty")

    # Create backup of current version
    if system_prompt_file.exists():
        backup_dir = system_prompt_file.parent / "backups"
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"system_prompt_{timestamp}.py"

        try:
            shutil.copy2(system_prompt_file, backup_file)
            logger.info(f"Created backup: {backup_file}")
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise HTTPException(status_code=500, detail="Failed to create backup")

    # Write new content
    try:
        system_prompt_file.write_text(data.content, encoding='utf-8')
        logger.info(f"System prompt updated by admin: {admin_data.get('username', 'unknown')}")

        return {
            "success": True,
            "message": "System prompt updated successfully",
            "updated_at": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to update system prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to update system prompt")

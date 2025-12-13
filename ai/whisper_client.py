"""
OpenAI Whisper Client.
Сервис транскрибации голосовых сообщений.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI
from loguru import logger

from config.settings import settings


class WhisperClient:
    """Клиент для транскрибации аудио через OpenAI Whisper API."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.WHISPER_MODEL

    async def transcribe(
        self,
        audio_file_path: str,
        language: str = "ru",
    ) -> Optional[str]:
        """
        Транскрибирует аудиофайл в текст.

        Args:
            audio_file_path: Путь к аудиофайлу
            language: Язык аудио (по умолчанию русский)

        Returns:
            Транскрибированный текст или None при ошибке
        """
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcript = await self.client.audio.transcriptions.create(
                    model=self.model,
                    file=audio_file,
                    language=language,
                    response_format="text",
                )

            logger.info(f"Transcribed audio: {len(transcript)} chars")
            return transcript.strip() if transcript else None

        except Exception as e:
            logger.error(f"Whisper transcription error: {e}")
            return None

    async def transcribe_bytes(
        self,
        audio_bytes: bytes,
        file_extension: str = "ogg",
        language: str = "ru",
    ) -> Optional[str]:
        """
        Транскрибирует аудио из байтов.

        Args:
            audio_bytes: Байты аудиофайла
            file_extension: Расширение файла (ogg, mp3, wav и т.д.)
            language: Язык аудио

        Returns:
            Транскрибированный текст или None при ошибке
        """
        temp_file = None
        try:
            # Создаём временный файл
            temp_file = tempfile.NamedTemporaryFile(
                suffix=f".{file_extension}",
                delete=False,
            )
            temp_file.write(audio_bytes)
            temp_file.close()

            # Транскрибируем
            result = await self.transcribe(temp_file.name, language)
            return result

        except Exception as e:
            logger.error(f"Whisper transcription from bytes error: {e}")
            return None

        finally:
            # Удаляем временный файл
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except Exception:
                    pass


# Глобальный экземпляр клиента
whisper_client = WhisperClient()

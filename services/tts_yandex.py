"""
Yandex SpeechKit TTS Service.
Генерация голосовых сообщений для медитаций.
"""

import aiohttp
import asyncio
from pathlib import Path
from typing import Optional
from loguru import logger

from config.settings import settings


class YandexTTS:
    """Сервис синтеза речи через Yandex SpeechKit."""

    API_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"

    # Голоса для медитаций (женские, спокойные)
    VOICES = {
        "alena": "alena",  # Нейтральный женский
        "jane": "jane",  # Спокойный женский (рекомендуется для медитаций)
        "omazh": "omazh",  # Мягкий женский
        "zahar": "zahar",  # Мужской (если нужен)
    }

    # Эмоции
    EMOTIONS = {
        "neutral": "neutral",
        "good": "good",  # Доброжелательный
        "evil": "evil",
    }

    def __init__(self):
        self.api_key = getattr(settings, "YANDEX_API_KEY", None)
        self.folder_id = getattr(settings, "YANDEX_FOLDER_ID", None)

    async def synthesize(
        self,
        text: str,
        output_path: Path,
        voice: str = "jane",
        emotion: str = "neutral",
        speed: float = 0.9,  # Чуть медленнее для медитаций
        format: str = "oggopus",  # Формат для Telegram voice
    ) -> bool:
        """
        Синтезирует речь и сохраняет в файл.

        Args:
            text: Текст для озвучки
            output_path: Путь для сохранения
            voice: Голос (jane, alena, omazh)
            emotion: Эмоция (neutral, good)
            speed: Скорость речи (0.1-3.0, 1.0 = нормальная)
            format: Формат аудио (oggopus для Telegram)

        Returns:
            True если успешно
        """
        if not self.api_key or not self.folder_id:
            logger.error("Yandex API key or folder ID not configured")
            return False

        # Разбиваем текст на части (лимит 5000 символов)
        chunks = self._split_text(text, max_length=4500)

        audio_parts = []
        for i, chunk in enumerate(chunks):
            logger.debug(f"Synthesizing chunk {i+1}/{len(chunks)}")

            audio_data = await self._synthesize_chunk(
                chunk, voice, emotion, speed, format
            )

            if audio_data:
                audio_parts.append(audio_data)
            else:
                logger.error(f"Failed to synthesize chunk {i+1}")
                return False

        # Объединяем части
        if len(audio_parts) == 1:
            combined_audio = audio_parts[0]
        else:
            combined_audio = b"".join(audio_parts)

        # Сохраняем
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(combined_audio)
            logger.info(f"Saved audio to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")
            return False

    async def _synthesize_chunk(
        self,
        text: str,
        voice: str,
        emotion: str,
        speed: float,
        format: str,
    ) -> Optional[bytes]:
        """Синтезирует один фрагмент текста."""

        headers = {
            "Authorization": f"Api-Key {self.api_key}",
        }

        data = {
            "text": text,
            "lang": "ru-RU",
            "voice": voice,
            "emotion": emotion,
            "speed": str(speed),
            "format": format,
            "folderId": self.folder_id,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.API_URL,
                    headers=headers,
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"Yandex TTS error: {response.status} - {error_text}"
                        )
                        return None
        except Exception as e:
            logger.error(f"Yandex TTS request failed: {e}")
            return None

    def _split_text(self, text: str, max_length: int = 4500) -> list:
        """
        Разбивает текст на части по предложениям.
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        # Разбиваем по предложениям
        sentences = text.replace("\n\n", "\n").split(".")

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Добавляем точку обратно
            sentence_with_dot = sentence + "."

            if len(current_chunk) + len(sentence_with_dot) <= max_length:
                current_chunk += sentence_with_dot + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence_with_dot + " "

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    async def generate_meditation_audio(
        self,
        meditation_id: str,
        script: str,
        output_dir: Path,
    ) -> Optional[Path]:
        """
        Генерирует аудио для медитации.

        Args:
            meditation_id: ID медитации
            script: Текст медитации
            output_dir: Директория для сохранения

        Returns:
            Путь к файлу или None
        """
        output_path = output_dir / f"{meditation_id}.ogg"

        # Добавляем паузы через SSML-подобные маркеры
        # (Yandex SpeechKit понимает ... как паузу)
        script_with_pauses = self._add_pauses(script)

        success = await self.synthesize(
            text=script_with_pauses,
            output_path=output_path,
            voice="jane",  # Спокойный женский голос
            emotion="neutral",
            speed=0.85,  # Медленнее для медитации
        )

        return output_path if success else None

    def _add_pauses(self, text: str) -> str:
        """
        Добавляет паузы в текст медитации.
        Yandex понимает многоточие как паузу.
        """
        # Заменяем переносы строк на паузы
        text = text.replace("\n\n", "... ... ")
        text = text.replace("\n", "... ")

        # Увеличиваем паузы после ключевых слов
        pause_words = [
            "вдох", "выдох", "вдохни", "выдохни",
            "расслабь", "отпусти", "почувствуй",
        ]

        for word in pause_words:
            text = text.replace(f"{word}.", f"{word}... ")
            text = text.replace(f"{word},", f"{word}... ")

        return text


# Глобальный экземпляр
yandex_tts = YandexTTS()


async def generate_all_meditations():
    """
    Генерирует аудио для всех медитаций.
    Запускать отдельно для создания файлов.
    """
    from content.meditations import MEDITATIONS

    output_dir = Path(__file__).parent.parent / "data" / "meditations"
    output_dir.mkdir(parents=True, exist_ok=True)

    for meditation in MEDITATIONS:
        logger.info(f"Generating audio for: {meditation.name}")

        output_path = await yandex_tts.generate_meditation_audio(
            meditation_id=meditation.id,
            script=meditation.script,
            output_dir=output_dir,
        )

        if output_path:
            logger.info(f"✓ Created: {output_path}")
        else:
            logger.error(f"✗ Failed: {meditation.id}")

        # Пауза между запросами
        await asyncio.sleep(2)


if __name__ == "__main__":
    # Для ручного запуска генерации
    asyncio.run(generate_all_meditations())

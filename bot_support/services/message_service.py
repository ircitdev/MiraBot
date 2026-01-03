"""
Message Service.
Сервис для обработки и пересылки сообщений между пользователем и поддержкой.
"""

from typing import Optional
from telegram import Bot, Message
from telegram.error import TelegramError
from loguru import logger

from database.models import SupportUser
from database.repositories.support_message import SupportMessageRepository
from config.settings import settings


class MessageService:
    """Сервис для обработки сообщений в поддержке."""

    def __init__(self):
        self.message_repo = SupportMessageRepository()

    async def forward_to_support(
        self,
        bot: Bot,
        message: Message,
        user: SupportUser,
    ) -> bool:
        """
        Пересылает сообщение пользователя в топик поддержки.

        Args:
            bot: Экземпляр Telegram Bot
            message: Сообщение от пользователя
            user: Объект SupportUser

        Returns:
            bool: True если успешно
        """
        try:
            logger.info(
                f"Forwarding message from user {user.telegram_id} "
                f"to topic {user.topic_id}"
            )

            # Пересылаем сообщение в топик
            forwarded_message = await bot.forward_message(
                chat_id=settings.SUPPORT_GROUP_ID,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
                message_thread_id=user.topic_id,
            )

            # Определяем тип медиа и текст
            media_type, message_text, media_file_id = self._extract_message_content(message)

            # Сохраняем в БД
            await self.message_repo.create(
                user_id=user.id,
                sender_type="user",
                message_text=message_text,
                media_type=media_type,
                media_file_id=media_file_id,
                telegram_message_id=forwarded_message.message_id,
            )

            logger.info(
                f"Successfully forwarded message to topic {user.topic_id}"
            )

            return True

        except TelegramError as e:
            logger.error(
                f"Telegram error forwarding message from user {user.telegram_id}: {e}"
            )
            # Проверяем, не заблокировал ли пользователь бота
            if "bot was blocked" in str(e).lower():
                from database.repositories.support_user import SupportUserRepository
                user_repo = SupportUserRepository()
                await user_repo.mark_bot_blocked(user.id, True)

            return False

        except Exception as e:
            logger.error(
                f"Error forwarding message from user {user.telegram_id}: {e}",
                exc_info=True
            )
            return False

    async def forward_to_user(
        self,
        bot: Bot,
        message: Message,
        user: SupportUser,
    ) -> bool:
        """
        Пересылает ответ админа пользователю.

        Args:
            bot: Экземпляр Telegram Bot
            message: Сообщение от админа
            user: Объект SupportUser

        Returns:
            bool: True если успешно
        """
        try:
            logger.info(
                f"Forwarding admin reply to user {user.telegram_id}"
            )

            # Определяем тип сообщения и отправляем соответствующим методом
            sent_message = None

            if message.text:
                # Текстовое сообщение
                sent_message = await bot.send_message(
                    chat_id=user.telegram_id,
                    text=message.text,
                )

            elif message.photo:
                # Фото
                photo = message.photo[-1]  # Берём самое большое
                sent_message = await bot.send_photo(
                    chat_id=user.telegram_id,
                    photo=photo.file_id,
                    caption=message.caption,
                )

            elif message.video:
                # Видео
                sent_message = await bot.send_video(
                    chat_id=user.telegram_id,
                    video=message.video.file_id,
                    caption=message.caption,
                )

            elif message.document:
                # Документ
                sent_message = await bot.send_document(
                    chat_id=user.telegram_id,
                    document=message.document.file_id,
                    caption=message.caption,
                )

            elif message.voice:
                # Голосовое (админы не могут отправлять через Bot API, но на всякий случай)
                logger.warning("Admin tried to send voice message - not supported")
                return False

            elif message.sticker:
                # Стикер
                sent_message = await bot.send_sticker(
                    chat_id=user.telegram_id,
                    sticker=message.sticker.file_id,
                )

            else:
                logger.warning(f"Unsupported message type from admin")
                return False

            if not sent_message:
                return False

            # Определяем тип медиа и текст
            media_type, message_text, media_file_id = self._extract_message_content(message)

            # Сохраняем в БД
            await self.message_repo.create(
                user_id=user.id,
                sender_type="admin",
                message_text=message_text,
                media_type=media_type,
                media_file_id=media_file_id,
                telegram_message_id=sent_message.message_id,
            )

            logger.info(
                f"Successfully sent admin reply to user {user.telegram_id}"
            )

            return True

        except TelegramError as e:
            logger.error(
                f"Telegram error sending message to user {user.telegram_id}: {e}"
            )
            # Проверяем, не заблокировал ли пользователь бота
            if "bot was blocked" in str(e).lower() or "user not found" in str(e).lower():
                from database.repositories.support_user import SupportUserRepository
                user_repo = SupportUserRepository()
                await user_repo.mark_bot_blocked(user.id, True)

            return False

        except Exception as e:
            logger.error(
                f"Error sending message to user {user.telegram_id}: {e}",
                exc_info=True
            )
            return False

    def _extract_message_content(self, message: Message) -> tuple[str, Optional[str], Optional[str]]:
        """
        Извлекает тип медиа, текст и file_id из сообщения.

        Args:
            message: Объект Message

        Returns:
            tuple: (media_type, message_text, media_file_id)
        """
        media_type = "text"
        message_text = message.text or message.caption
        media_file_id = None

        if message.photo:
            media_type = "photo"
            photo = message.photo[-1]
            media_file_id = photo.file_id

        elif message.video:
            media_type = "video"
            media_file_id = message.video.file_id

        elif message.voice:
            media_type = "voice"
            media_file_id = message.voice.file_id

        elif message.video_note:
            media_type = "video_note"
            media_file_id = message.video_note.file_id

        elif message.document:
            media_type = "document"
            media_file_id = message.document.file_id

        elif message.sticker:
            media_type = "sticker"
            media_file_id = message.sticker.file_id

        return media_type, message_text, media_file_id

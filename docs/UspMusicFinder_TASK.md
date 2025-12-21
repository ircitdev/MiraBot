# Задание на доработку UspMusicFinder_bot

## Цель

Добавить обработку deep link параметров в команде `/start` для автоматического поиска и скачивания музыки при переходе из других ботов.

## Текущее поведение

При переходе по ссылке `https://t.me/UspMusicFinder_bot?start=Ocean%20Waves%20Relaxing`:
- Бот получает команду `/start Ocean Waves Relaxing`
- Сейчас: показывает обычное приветствие, игнорируя параметр

## Требуемое поведение

При переходе по deep link с параметром:
- Бот получает `/start <название_трека>`
- Автоматически выполняет поиск по `<название_трека>`
- Скачивает первый результат и отправляет пользователю
- Показывает краткое сообщение о том, что трек найден через интеграцию

## Пример реализации (aiogram 3.x)

```python
from aiogram import Router, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message

router = Router()

@router.message(CommandStart(deep_link=True))
async def start_with_deep_link(message: Message, command: CommandObject):
    """Обработка /start с deep link параметром."""
    query = command.args  # "Ocean Waves Relaxing"

    if query:
        # Отправляем сообщение о начале поиска
        status_msg = await message.answer(
            f"🔍 Ищу: **{query}**\n"
            f"_Запрос от интеграции с Mira Bot_",
            parse_mode="Markdown"
        )

        # Выполняем поиск и скачивание (используем существующую логику)
        try:
            result = await search_and_download_track(query)

            if result["success"]:
                # Отправляем аудио
                await message.answer_audio(
                    audio=result["file_id"],
                    title=result["title"],
                    performer=result["artist"],
                    caption=f"🎵 {result['title']}\n\n_Найдено через Mira Bot_",
                    parse_mode="Markdown"
                )
            else:
                await message.answer(
                    f"😔 Не удалось найти: {query}\n"
                    f"Попробуй написать название иначе."
                )

        except Exception as e:
            await message.answer(f"❌ Ошибка при поиске: {e}")

        # Удаляем статусное сообщение
        await status_msg.delete()
    else:
        # Обычный /start без параметра
        await show_welcome_message(message)


@router.message(CommandStart(deep_link=False))
async def start_without_deep_link(message: Message):
    """Обычный /start без параметров."""
    await show_welcome_message(message)
```

## Альтернатива (aiogram 2.x)

```python
from aiogram import types
from aiogram.dispatcher.filters import CommandStart

@dp.message_handler(CommandStart(deep_link=True))
async def start_with_param(message: types.Message):
    args = message.get_args()  # Получаем параметр после /start

    if args:
        query = args.replace("%20", " ")  # URL decode если нужно
        await search_and_send_music(message, query)
    else:
        await show_welcome(message)
```

## Формат deep link

URL формируется так:
```
https://t.me/UspMusicFinder_bot?start={encoded_track_name}
```

Где `encoded_track_name` — это URL-encoded название трека:
- `Ocean Waves Relaxing` → `Ocean%20Waves%20Relaxing`
- `Beethoven Moonlight Sonata` → `Beethoven%20Moonlight%20Sonata`
- `Dave Brubeck Take Five` → `Dave%20Brubeck%20Take%20Five`

## Интеграция

Эта доработка нужна для интеграции с **Mira Bot** (@mira_psychologist_bot):
1. Пользователь просит музыку в Mira Bot
2. Mira показывает трек с двумя кнопками:
   - "Слушать на YouTube" — открывает YouTube
   - "Скачать в Telegram" — deep link на UspMusicFinder
3. При нажатии "Скачать в Telegram" пользователь переходит в UspMusicFinder
4. UspMusicFinder автоматически ищет и отправляет трек

## Файлы для изменения

- `/root/uspmusic-bot/src/handlers/start.py` — добавить обработку deep link
- Или где находится текущий обработчик команды `/start`

## Сервер

- Сервер: `31.44.7.144`
- Путь: `/root/uspmusic-bot`
- Bot ID: `8409655187`
- Username: `@UspMusicFinder_bot`

## Тестирование

После доработки проверить:
1. Переход по `https://t.me/UspMusicFinder_bot?start=Coldplay%20Yellow`
2. Бот должен автоматически найти и отправить трек "Coldplay Yellow"
3. Обычный `/start` (без параметра) должен работать как раньше

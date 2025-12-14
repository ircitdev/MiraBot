# MIRA BOT Tests

Unit и интеграционные тесты для MIRA BOT.

## Структура тестов

```
tests/
├── __init__.py           # Пакет тестов
├── conftest.py           # Fixtures для pytest
├── test_text_parser.py   # Тесты парсинга имён
├── test_sanitizer.py     # Тесты санитизации
└── test_mood_analyzer.py # Тесты анализа настроения
```

## Запуск тестов

### Все тесты

```bash
pytest
```

### С покрытием кода

```bash
pytest --cov=. --cov-report=html
```

После этого откройте `htmlcov/index.html` в браузере.

### Только определённый файл

```bash
pytest tests/test_text_parser.py
```

### Только определённый тест

```bash
pytest tests/test_text_parser.py::TestExtractNameFromText::test_extract_simple_name
```

### С verbose выводом

```bash
pytest -v
```

### Только быстрые тесты (без DB и API)

```bash
pytest -m "not slow and not db and not api"
```

## Маркеры тестов

- `@pytest.mark.unit` — Unit тесты (изолированные функции)
- `@pytest.mark.integration` — Интеграционные тесты (взаимодействие компонентов)
- `@pytest.mark.slow` — Медленные тесты (> 1 сек)
- `@pytest.mark.db` — Тесты требующие БД
- `@pytest.mark.api` — Тесты требующие внешние API

## Fixtures

### mock_bot
Mock Telegram Bot instance для тестирования без реального бота.

```python
def test_something(mock_bot):
    await mock_bot.send_message(chat_id=123, text="test")
    mock_bot.send_message.assert_called_once()
```

### mock_update
Mock Telegram Update для тестирования handlers.

```python
def test_handler(mock_update):
    assert mock_update.effective_user.id == 12345
```

### mock_context
Mock Telegram Context.

```python
def test_with_context(mock_context):
    context.user_data["key"] = "value"
```

### sample_user_data
Пример данных пользователя.

```python
def test_user(sample_user_data):
    assert sample_user_data["persona"] == "mira"
```

## Покрытие кода

Цель: **80%+** покрытие критичных модулей.

Приоритетные модули для тестирования:
- ✅ `utils/text_parser.py` — парсинг имён
- ✅ `utils/sanitizer.py` — санитизация входных данных
- ✅ `ai/mood_analyzer.py` — анализ настроения
- 🔲 `ai/hint_generator.py` — генерация подсказок
- 🔲 `database/repositories/*` — работа с БД
- 🔲 `bot/handlers/*` — обработчики команд

## Continuous Integration

Тесты автоматически запускаются при push через GitHub Actions (будет настроено).

## Требования

```bash
pip install -r requirements.txt
```

Основные зависимости:
- pytest==7.4.4
- pytest-asyncio==0.23.3
- pytest-cov==4.1.0

## Отладка

### Запуск с pdb

```bash
pytest --pdb
```

### Вывод print statements

```bash
pytest -s
```

### Последний упавший тест

```bash
pytest --lf
```

### Останавливаться на первой ошибке

```bash
pytest -x
```

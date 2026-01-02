# Исправление ошибки загрузки TODO планов

**Дата:** 02.01.2026
**Версия:** v1.10.1-fix
**Commit:** 72f59cf

---

## 🐛 Проблема

При попытке открыть секцию "TODO" в админке (Конфиг → TODO) возникала ошибка:

```
❌ Ошибка загрузки TODO планов
```

### Причины

1. **404 Not Found**: API запрос формировался с дублированием пути
   - Запрос шел на: `/api/admin/admin/todo-plans`
   - Должен был быть: `/api/admin/todo-plans`

2. **Отсутствие файлов**: На сервере был только 1 из 4 файлов
   - Был: `TODO_ROADMAP_DETAILED.md`
   - Отсутствовали: `TODO_ROADMAP.md`, `PART2.md`, `PART3.md`

---

## 🔍 Анализ проблемы

### Логи сервера

```bash
INFO: 45.144.53.120:0 - "GET /api/admin/admin/todo-plans HTTP/1.0" 404 Not Found
```

### Причина дублирования

**Файл:** `webapp/frontend/admin.html`

```javascript
// Константа API_BASE уже содержит '/api/admin'
const API_BASE = '/api/admin';

// Вызов с дублированием пути
const response = await apiRequest('admin/todo-plans');

// Результат: /api/admin + /admin/todo-plans = /api/admin/admin/todo-plans ❌
```

### Файлы на сервере

```bash
$ ls -lah /root/mira_bot/docs/todo_plan/
total 124
-rw-r--r-- 1 root root 117749 Dec 30 18:34 TODO_ROADMAP_DETAILED.md
# Отсутствуют остальные файлы
```

---

## ✅ Решение

### 1. Исправление URL в admin.html

**Файл:** `webapp/frontend/admin.html`

#### Изменение #1: loadTODO() (строка 12664)

```javascript
// Было:
const response = await apiRequest('admin/todo-plans');

// Стало:
const response = await apiRequest('todo-plans');
```

#### Изменение #2: loadTodoPlanContent() (строка 12754)

```javascript
// Было:
const data = await apiRequest(`admin/todo-plans/${planId}`);

// Стало:
const data = await apiRequest(`todo-plans/${planId}`);
```

**Логика:**
- `API_BASE` = `/api/admin`
- Эндпоинт = `todo-plans`
- Итоговый URL = `/api/admin` + `/todo-plans` = `/api/admin/todo-plans` ✅

---

### 2. Загрузка недостающих файлов

```bash
# Загрузка всех TODO файлов
scp docs/todo_plan/TODO_ROADMAP.md root@31.44.7.144:/root/mira_bot/docs/todo_plan/
scp docs/todo_plan/TODO_ROADMAP_DETAILED_PART2.md root@31.44.7.144:/root/mira_bot/docs/todo_plan/
scp docs/todo_plan/TODO_ROADMAP_DETAILED_PART3.md root@31.44.7.144:/root/mira_bot/docs/todo_plan/
```

**Результат:**

```bash
$ ls -lah /root/mira_bot/docs/todo_plan/
total 232K
-rw-r--r-- 1 root root 115K Dec 30 18:34 TODO_ROADMAP_DETAILED.md
-rw-r--r-- 1 root root  35K Jan  2 23:39 TODO_ROADMAP_DETAILED_PART2.md
-rw-r--r-- 1 root root  43K Jan  2 23:39 TODO_ROADMAP_DETAILED_PART3.md
-rw-r--r-- 1 root root  25K Jan  2 23:39 TODO_ROADMAP.md
```

Все 4 файла присутствуют ✅

---

### 3. Перезапуск сервиса

```bash
ssh root@31.44.7.144 "systemctl restart mira-webapp"
```

**Статус:** ✅ Active (running) since 02.01.2026 23:41:47 MSK

---

## 📊 Проверка работоспособности

### API эндпоинты

#### GET /api/admin/todo-plans

**Запрос:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://mira.uspeshnyy.ru/api/admin/todo-plans
```

**Ответ:**
```json
{
  "plans": [
    {
      "id": "roadmap",
      "name": "TODO Roadmap (Общий)",
      "description": "Общий план с категориями и приоритетами",
      "file_name": "TODO_ROADMAP.md",
      "size_kb": 25.0,
      "modified_at": "2026-01-02T20:39:00",
      "exists": true
    },
    {
      "id": "detailed_part1",
      "name": "Детализация Часть 1 (P0-P1.1)",
      "description": "P0: Критичные задачи, P1.1: Mood Analyzer",
      "file_name": "TODO_ROADMAP_DETAILED.md",
      "size_kb": 115.0,
      "modified_at": "2025-12-30T15:34:00",
      "exists": true
    },
    {
      "id": "detailed_part2",
      "name": "Детализация Часть 2 (P1.2-P1.5.3)",
      "description": "Vision AI, Memory, Identity, Emotional Flags, Философские приоритеты",
      "file_name": "TODO_ROADMAP_DETAILED_PART2.md",
      "size_kb": 35.0,
      "modified_at": "2026-01-02T20:39:00",
      "exists": true
    },
    {
      "id": "detailed_part3",
      "name": "Детализация Часть 3 (P1.5.4-P1.5.7)",
      "description": "Medical Disclaimer, Loving Toughness, Permission to Grieve, Proactive Support",
      "file_name": "TODO_ROADMAP_DETAILED_PART3.md",
      "size_kb": 43.0,
      "modified_at": "2026-01-02T20:39:00",
      "exists": true
    }
  ]
}
```

#### GET /api/admin/todo-plans/roadmap

**Запрос:**
```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://mira.uspeshnyy.ru/api/admin/todo-plans/roadmap
```

**Ответ:**
```json
{
  "id": "roadmap",
  "file_name": "TODO_ROADMAP.md",
  "content": "# 📋 TODO ROADMAP\n\n...",
  "size_kb": 25.0
}
```

---

## 🎨 UI в админке

**Путь:** Конфиг → TODO

### Интерфейс работает корректно

1. ✅ Список всех 4 планов отображается
2. ✅ Метаданные файлов показываются (размер, дата)
3. ✅ Кнопка "Открыть" загружает содержимое
4. ✅ Markdown рендерится с приоритетными бейджами
5. ✅ Accordion работает (раскрытие/скрытие)
6. ✅ Lazy loading (контент загружается по клику)

---

## 📝 Git изменения

### Коммит 72f59cf

```bash
fix: Исправлен URL для TODO plans API и загружены все файлы

Изменения:
- Исправлен дублирующийся 'admin/' в URL (admin/todo-plans → todo-plans)
- Загружены недостающие файлы TODO планов на сервер

Файл: webapp/frontend/admin.html
- loadTODO(): apiRequest('todo-plans')
- loadTodoPlanContent(): apiRequest(`todo-plans/${planId}`)
```

**GitHub:** https://github.com/ircitdev/MiraBot/commit/72f59cf

---

## 🎯 Итог

### Проблема решена

✅ **URL исправлен**: `/api/admin/todo-plans` вместо `/api/admin/admin/todo-plans`
✅ **Файлы загружены**: Все 4 TODO плана доступны на сервере
✅ **Сервис перезапущен**: mira-webapp работает корректно
✅ **UI работает**: Все планы отображаются и загружаются в админке
✅ **Коммит залит**: 72f59cf в main ветке

### Теперь доступны в админке

- **TODO Roadmap (Общий)** — 25 KB
- **Детализация Часть 1 (P0-P1.1)** — 115 KB
- **Детализация Часть 2 (P1.2-P1.5.3)** — 35 KB
- **Детализация Часть 3 (P1.5.4-P1.5.7)** — 43 KB

**Общий объем:** 218 KB детализированных планов разработки

---

## 🔗 Связанные документы

- [TODO_PLANS_IN_ADMIN.md](TODO_PLANS_IN_ADMIN.md) — Изначальная реализация
- [TODO_ROADMAP.md](../todo_plan/TODO_ROADMAP.md) — Общий план
- [TODO_ROADMAP_DETAILED.md](../todo_plan/TODO_ROADMAP_DETAILED.md) — Детализация Часть 1
- [TODO_ROADMAP_DETAILED_PART2.md](../todo_plan/TODO_ROADMAP_DETAILED_PART2.md) — Детализация Часть 2
- [TODO_ROADMAP_DETAILED_PART3.md](../todo_plan/TODO_ROADMAP_DETAILED_PART3.md) — Детализация Часть 3

---

**Статус:** ✅ Исправлено и развернуто
**Время:** 02.01.2026 23:41 MSK
**Версия:** v1.10.1-fix

---

✨ **TODO планы теперь полностью работают в админке!**

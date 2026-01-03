# Улучшение отображения API расходов на дашборде

**Дата:** 30.12.2025
**Задача:** Изменить карточку API расходов для более наглядного отображения

## Изменения

### Было:
```
┌─────────────────┐
│      $-         │  <- Большая цифра (сегодня)
│  API расходы    │
│ $0 за неделю •  │
│ $0 за месяц     │
└─────────────────┘
```

### Стало:
```
┌─────────────────┐
│  API расходы    │
│                 │
│ За день:    $-  │
│ За неделю:  $-  │
│ За месяц:   $-  │
└─────────────────┘
```

## Преимущества нового формата

1. **Более структурированно** - все три периода равнозначны и хорошо видны
2. **Легче сравнивать** - значения выровнены по правому краю
3. **Больше места** - каждый период на отдельной строке
4. **Понятнее** - явные метки для каждого периода

## Технические детали

### Структура HTML (строки 3837-3853):

```html
<div class="stat-card">
    <div class="stat-label" style="margin-bottom: 12px;">API расходы</div>
    <div style="display: flex; flex-direction: column; gap: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 14px; color: var(--md-sys-color-on-surface-variant);">За день:</span>
            <span id="api-cost-today" style="font-size: 18px; font-weight: 600; color: var(--md-sys-color-primary);">$-</span>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 14px; color: var(--md-sys-color-on-surface-variant);">За неделю:</span>
            <span id="api-cost-week" style="font-size: 18px; font-weight: 600; color: var(--md-sys-color-primary);">$-</span>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 14px; color: var(--md-sys-color-on-surface-variant);">За месяц:</span>
            <span id="api-cost-month" style="font-size: 18px; font-weight: 600; color: var(--md-sys-color-primary);">$-</span>
        </div>
    </div>
</div>
```

### Стили:
- **Заголовок:** `stat-label` с отступом снизу 12px
- **Контейнер строк:** `flex-direction: column` с отступом между строками 8px
- **Каждая строка:** `justify-content: space-between` для выравнивания по краям
- **Метки:** 14px, серый цвет
- **Значения:** 18px, жирный шрифт, основной цвет темы

### JavaScript (без изменений):
Обновление значений происходит через те же элементы:
```javascript
document.getElementById('api-cost-today').textContent = `$${costToday.toFixed(2)}`;
document.getElementById('api-cost-week').textContent = `$${costWeek.toFixed(2)}`;
document.getElementById('api-cost-month').textContent = `$${costMonth.toFixed(2)}`;
```

## Файлы изменений

- `webapp/frontend/admin.html` (строки 3837-3853) - обновлена структура карточки

## Визуальный результат

Карточка теперь показывает три отдельных строки с расходами:

```
API расходы
─────────────────────
За день:        $0.12
За неделю:      $1.45
За месяц:       $5.67
```

Все значения обновляются автоматически при загрузке дашборда.

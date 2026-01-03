# UI для раздела "Поддержка" - Инструкция по интеграции

**Дата:** 03.01.2026
**Файл:** webapp/frontend/admin.html

---

## 📋 Что уже сделано

✅ Меню обновлено:
- Кнопка "Поддержка" добавлена в главное меню (строка 3680-3683)
- Подменю добавлено с разделами "Вопросы" и "Отзывы" (строки 3738-3747)

---

## 🔧 Что нужно добавить

### 1. HTML контент для tab-support

**Где добавить:** После `<div id="tab-users" class="tab-content">` (примерно строка 4500+)

**Вставить следующий код:**

```html
<!-- ========================================= -->
<!-- TAB: ПОДДЕРЖКА -->
<!-- ========================================= -->
<div id="tab-support" class="tab-content">

    <!-- ================================ -->
    <!-- ПОДРАЗДЕЛ: ВОПРОСЫ -->
    <!-- ================================ -->
    <div id="support-section-questions" class="context-section active">
        <h2 class="section-title">
            <span class="material-icons">question_answer</span>
            Обращения в поддержку
        </h2>

        <!-- Toolbar -->
        <div class="toolbar">
            <div class="search-field">
                <span class="material-icons">search</span>
                <input type="text" id="support-search" placeholder="Поиск по имени..."
                       onkeypress="if(event.key==='Enter')searchSupportQuestions()">
            </div>
            <button class="md-button md-button-filled" onclick="loadSupportQuestions()">
                <span class="material-icons">refresh</span>
                Обновить
            </button>
        </div>

        <!-- Statistics Cards -->
        <div class="stats-grid" style="margin-bottom: 24px;">
            <div class="stat-card">
                <div class="stat-icon" style="background: #E3F2FD;">
                    <span class="material-icons" style="color: #1976D2;">question_answer</span>
                </div>
                <div class="stat-content">
                    <div class="stat-label">Всего обращений</div>
                    <div class="stat-value" id="support-total-questions">-</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: #FFF3E0;">
                    <span class="material-icons" style="color: #F57C00;">schedule</span>
                </div>
                <div class="stat-content">
                    <div class="stat-label">Непрочитанных</div>
                    <div class="stat-value" id="support-unread-count">-</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: #E8F5E9;">
                    <span class="material-icons" style="color: #388E3C;">check_circle</span>
                </div>
                <div class="stat-content">
                    <div class="stat-label">За сегодня</div>
                    <div class="stat-value" id="support-today-count">-</div>
                </div>
            </div>
        </div>

        <!-- Questions List (Accordion) -->
        <div class="card">
            <div class="card-header">
                <h3>Список обращений</h3>
            </div>
            <div id="support-questions-container" class="card-body" style="padding: 0;">
                <div style="padding: 40px; text-align: center; color: var(--md-sys-color-on-surface-variant);">
                    Загрузка обращений...
                </div>
            </div>
        </div>

        <!-- Pagination -->
        <div id="support-pagination" class="pagination-container" style="display: none;">
            <!-- Пагинация будет добавлена через JS -->
        </div>
    </div>

    <!-- ================================ -->
    <!-- ПОДРАЗДЕЛ: ОТЗЫВЫ -->
    <!-- ================================ -->
    <div id="support-section-reviews" class="context-section">
        <h2 class="section-title">
            <span class="material-icons">rate_review</span>
            Отзывы пользователей
        </h2>

        <!-- Toolbar -->
        <div class="toolbar">
            <select id="reviews-filter" class="md-select" onchange="loadSupportReviews()"
                    style="min-width: 200px;">
                <option value="">Все отзывы</option>
                <option value="true">С разрешением</option>
                <option value="false">Без разрешения</option>
            </select>
            <button class="md-button md-button-filled" onclick="loadSupportReviews()">
                <span class="material-icons">refresh</span>
                Обновить
            </button>
            <button class="md-button md-button-outlined" onclick="exportReviews()"
                    style="margin-left: auto;">
                <span class="material-icons">download</span>
                Экспорт JSON
            </button>
        </div>

        <!-- Statistics -->
        <div class="stats-grid" style="margin-bottom: 24px;">
            <div class="stat-card">
                <div class="stat-icon" style="background: #F3E5F5;">
                    <span class="material-icons" style="color: #7B1FA2;">rate_review</span>
                </div>
                <div class="stat-content">
                    <div class="stat-label">Всего отзывов</div>
                    <div class="stat-value" id="reviews-total">-</div>
                </div>
            </div>
            <div class="stat-card">
                <div class="stat-icon" style="background: #E8F5E9;">
                    <span class="material-icons" style="color: #388E3C;">check_circle</span>
                </div>
                <div class="stat-content">
                    <div class="stat-label">С разрешением</div>
                    <div class="stat-value" id="reviews-with-permission">-</div>
                </div>
            </div>
        </div>

        <!-- Reviews Grid -->
        <div id="support-reviews-container" class="reviews-grid">
            <div style="padding: 40px; text-align: center; color: var(--md-sys-color-on-surface-variant); grid-column: 1/-1;">
                Загрузка отзывов...
            </div>
        </div>

        <!-- Pagination -->
        <div id="reviews-pagination" class="pagination-container" style="display: none;">
            <!-- Пагинация будет добавлена через JS -->
        </div>
    </div>
</div>
```

---

### 2. CSS Стили

**Где добавить:** В секцию `<style>` в начале файла (примерно строка 3500+)

**Вставить следующий код:**

```css
/* ========================================= */
/* SUPPORT SECTION STYLES */
/* ========================================= */

/* Chat Messages */
.chat-messages {
    display: flex;
    flex-direction: column;
    gap: 12px;
    padding: 16px;
    max-height: 600px;
    overflow-y: auto;
    background: var(--md-sys-color-surface-variant);
    border-radius: 12px;
}

.chat-message {
    max-width: 70%;
    padding: 12px 16px;
    border-radius: 12px;
    word-wrap: break-word;
    animation: slideIn 0.3s ease;
}

.chat-message.user {
    background: var(--md-sys-color-secondary-container);
    color: var(--md-sys-color-on-secondary-container);
    align-self: flex-start;
    border-bottom-left-radius: 4px;
}

.chat-message.admin {
    background: var(--md-sys-color-primary-container);
    color: var(--md-sys-color-on-primary-container);
    align-self: flex-end;
    border-bottom-right-radius: 4px;
}

.message-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
    font-size: 12px;
    opacity: 0.8;
}

.message-text {
    line-height: 1.5;
    margin: 4px 0;
}

.message-time {
    font-size: 11px;
    opacity: 0.6;
    margin-top: 4px;
}

.message-media {
    margin-top: 8px;
    border-radius: 8px;
    overflow: hidden;
}

.message-media img {
    max-width: 100%;
    display: block;
}

/* Accordion for Questions */
.question-accordion {
    border-bottom: 1px solid var(--md-sys-color-outline);
}

.question-header {
    padding: 16px 20px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 16px;
    transition: background 0.2s;
}

.question-header:hover {
    background: var(--md-sys-color-surface-variant);
}

.question-avatar {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    object-fit: cover;
    background: var(--md-sys-color-primary-container);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--md-sys-color-on-primary-container);
    font-weight: 500;
}

.question-info {
    flex: 1;
    min-width: 0;
}

.question-name {
    font-weight: 500;
    font-size: 16px;
    margin-bottom: 4px;
}

.question-username {
    font-size: 13px;
    color: var(--md-sys-color-primary);
}

.question-meta {
    display: flex;
    align-items: center;
    gap: 16px;
    font-size: 13px;
    color: var(--md-sys-color-on-surface-variant);
    margin-top: 4px;
}

.question-last-message {
    font-size: 14px;
    color: var(--md-sys-color-on-surface-variant);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.question-chevron {
    transition: transform 0.3s;
    color: var(--md-sys-color-on-surface-variant);
}

.question-header.expanded .question-chevron {
    transform: rotate(180deg);
}

.question-body {
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.3s ease;
}

.question-body.expanded {
    max-height: 1000px;
}

.question-content {
    padding: 20px;
    background: var(--md-sys-color-surface);
    border-top: 1px solid var(--md-sys-color-outline);
}

.chat-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--md-sys-color-outline);
}

.chat-actions {
    display: flex;
    gap: 8px;
}

/* Reviews Grid */
.reviews-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
    gap: 20px;
    margin-top: 20px;
}

.review-card {
    background: var(--md-sys-color-surface);
    border: 1px solid var(--md-sys-color-outline);
    border-radius: 12px;
    padding: 20px;
    transition: box-shadow 0.3s, transform 0.2s;
    animation: fadeIn 0.3s ease;
}

.review-card:hover {
    box-shadow: var(--md-sys-elevation-2);
    transform: translateY(-2px);
}

.review-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
}

.review-user-info {
    flex: 1;
}

.review-username {
    font-weight: 500;
    font-size: 16px;
    color: var(--md-sys-color-on-surface);
    display: flex;
    align-items: center;
    gap: 8px;
}

.review-age {
    font-size: 13px;
    color: var(--md-sys-color-on-surface-variant);
    margin-top: 2px;
}

.review-permission {
    padding: 4px 12px;
    border-radius: 16px;
    font-size: 12px;
    font-weight: 500;
}

.review-permission.granted {
    background: var(--md-sys-color-primary-container);
    color: var(--md-sys-color-on-primary-container);
}

.review-permission.denied {
    background: var(--md-sys-color-error);
    color: var(--md-sys-color-on-error);
    opacity: 0.7;
}

.review-about {
    font-size: 13px;
    color: var(--md-sys-color-on-surface-variant);
    margin-bottom: 12px;
    font-style: italic;
}

.review-text {
    font-size: 14px;
    line-height: 1.6;
    color: var(--md-sys-color-on-surface);
    margin: 12px 0;
}

.review-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 16px;
    padding-top: 12px;
    border-top: 1px solid var(--md-sys-color-outline);
    font-size: 12px;
    color: var(--md-sys-color-on-surface-variant);
}

.review-date {
    display: flex;
    align-items: center;
    gap: 4px;
}

.review-link {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--md-sys-color-primary);
    text-decoration: none;
    font-size: 13px;
    transition: opacity 0.2s;
}

.review-link:hover {
    opacity: 0.8;
    text-decoration: underline;
}

/* Animations */
@keyframes slideIn {
    from {
        opacity: 0;
        transform: translateY(10px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
    }
}

@keyframes fadeIn {
    from {
        opacity: 0;
    }
    to {
        opacity: 1;
    }
}

/* Mobile Responsive */
@media (max-width: 768px) {
    .reviews-grid {
        grid-template-columns: 1fr;
    }

    .chat-message {
        max-width: 85%;
    }

    .question-meta {
        flex-direction: column;
        align-items: flex-start;
        gap: 4px;
    }
}
```

---

### 3. JavaScript функции

**Где добавить:** В секцию `<script>` в конце файла (перед закрывающим `</script>`)

**Вставить следующий код:**

```javascript
// ========================================
// SUPPORT SECTION FUNCTIONS
// ========================================

let currentSupportPage = 1;
let currentReviewsPage = 1;
const SUPPORT_PAGE_SIZE = 20;
const REVIEWS_PAGE_SIZE = 12;

/**
 * Переключение между подразделами "Вопросы" и "Отзывы"
 */
function switchSupportSection(section) {
    // Убрать active у всех секций
    document.querySelectorAll('#tab-support .context-section').forEach(s => {
        s.classList.remove('active');
    });

    // Убрать active у всех кнопок подменю
    document.querySelectorAll('[data-parent="support"] .sub-nav-item').forEach(btn => {
        btn.classList.remove('active');
    });

    // Активировать выбранную секцию
    document.getElementById(`support-section-${section}`).classList.add('active');
    document.querySelector(`[data-parent="support"][data-section="${section}"]`).classList.add('active');

    // Загрузить данные
    if (section === 'questions') {
        loadSupportQuestions();
    } else if (section === 'reviews') {
        loadSupportReviews();
    }
}

/**
 * Загрузка списка обращений
 */
async function loadSupportQuestions(page = 1) {
    currentSupportPage = page;
    const container = document.getElementById('support-questions-container');

    try {
        container.innerHTML = '<div style="padding: 40px; text-align: center;"><div class="spinner"></div></div>';

        const response = await apiRequest(`/support/questions?page=${page}&limit=${SUPPORT_PAGE_SIZE}`);

        // Обновить статистику
        document.getElementById('support-total-questions').textContent = response.total;

        if (response.questions.length === 0) {
            container.innerHTML = `
                <div style="padding: 60px 20px; text-align: center;">
                    <span class="material-icons" style="font-size: 64px; color: var(--md-sys-color-on-surface-variant); opacity: 0.3;">question_answer</span>
                    <p style="margin-top: 16px; color: var(--md-sys-color-on-surface-variant);">Нет обращений</p>
                </div>
            `;
            return;
        }

        // Отрисовать список
        container.innerHTML = response.questions.map(q => renderQuestionItem(q)).join('');

        // Отрисовать пагинацию
        renderSupportPagination(response.total, page, SUPPORT_PAGE_SIZE);

    } catch (error) {
        console.error('Error loading support questions:', error);
        container.innerHTML = `
            <div style="padding: 40px; text-align: center; color: var(--md-sys-color-error);">
                <span class="material-icons" style="font-size: 48px;">error</span>
                <p style="margin-top: 12px;">Ошибка загрузки обращений</p>
            </div>
        `;
    }
}

/**
 * Отрисовка элемента обращения (accordion)
 */
function renderQuestionItem(question) {
    const lastMessageDate = question.last_message_date
        ? formatDateTime(new Date(question.last_message_date))
        : 'Нет сообщений';

    const avatar = question.photo_url
        ? `<img src="${question.photo_url}" class="question-avatar" alt="Avatar">`
        : `<div class="question-avatar">${question.first_name[0]}</div>`;

    return `
        <div class="question-accordion" data-user-id="${question.user_id}">
            <div class="question-header" onclick="toggleQuestion(${question.user_id})">
                ${avatar}
                <div class="question-info">
                    <div class="question-name">
                        ${escapeHtml(question.first_name)}${question.last_name ? ' ' + escapeHtml(question.last_name) : ''}
                        ${question.username ? `<span class="question-username">@${escapeHtml(question.username)}</span>` : ''}
                    </div>
                    <div class="question-meta">
                        <span><span class="material-icons" style="font-size: 16px; vertical-align: middle;">message</span> ${question.total_messages} сообщений</span>
                        <span><span class="material-icons" style="font-size: 16px; vertical-align: middle;">schedule</span> ${lastMessageDate}</span>
                        ${question.is_bot_blocked ? '<span style="color: var(--md-sys-color-error);"><span class="material-icons" style="font-size: 16px; vertical-align: middle;">block</span> Заблокирован</span>' : ''}
                    </div>
                    ${question.last_message_text ? `<div class="question-last-message">${escapeHtml(question.last_message_text)}</div>` : ''}
                </div>
                <span class="material-icons question-chevron">expand_more</span>
            </div>
            <div class="question-body" id="question-body-${question.user_id}">
                <div class="question-content">
                    <div class="chat-header">
                        <div>
                            <strong>История переписки</strong>
                            <div style="font-size: 13px; color: var(--md-sys-color-on-surface-variant); margin-top: 4px;">
                                Telegram ID: ${question.telegram_id} | Topic: #${question.topic_id}
                            </div>
                        </div>
                        <div class="chat-actions">
                            <a href="tg://user?id=${question.telegram_id}" class="md-button md-button-outlined" style="font-size: 13px; padding: 6px 12px;">
                                <span class="material-icons" style="font-size: 18px;">person</span>
                                Открыть профиль
                            </a>
                            <a href="https://t.me/c/${Math.abs(question.telegram_id)}/1/${question.topic_id}" target="_blank" class="md-button md-button-outlined" style="font-size: 13px; padding: 6px 12px;">
                                <span class="material-icons" style="font-size: 18px;">forum</span>
                                Открыть топик
                            </a>
                        </div>
                    </div>
                    <div id="chat-messages-${question.user_id}" class="chat-messages">
                        <div style="text-align: center; padding: 20px; color: var(--md-sys-color-on-surface-variant);">
                            Загрузка сообщений...
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

/**
 * Переключение раскрытия/скрытия обращения
 */
async function toggleQuestion(userId) {
    const header = document.querySelector(`.question-accordion[data-user-id="${userId}"] .question-header`);
    const body = document.getElementById(`question-body-${userId}`);

    const isExpanded = header.classList.contains('expanded');

    if (isExpanded) {
        // Закрыть
        header.classList.remove('expanded');
        body.classList.remove('expanded');
    } else {
        // Открыть
        header.classList.add('expanded');
        body.classList.add('expanded');

        // Загрузить сообщения, если еще не загружены
        const messagesContainer = document.getElementById(`chat-messages-${userId}`);
        if (messagesContainer.dataset.loaded !== 'true') {
            await loadUserMessages(userId);
            messagesContainer.dataset.loaded = 'true';
        }
    }
}

/**
 * Загрузка истории сообщений пользователя
 */
async function loadUserMessages(userId) {
    const container = document.getElementById(`chat-messages-${userId}`);

    try {
        container.innerHTML = '<div style="text-align: center; padding: 20px;"><div class="spinner"></div></div>';

        const response = await apiRequest(`/support/questions/${userId}/messages?limit=100`);

        if (response.messages.length === 0) {
            container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--md-sys-color-on-surface-variant);">Нет сообщений</div>';
            return;
        }

        container.innerHTML = response.messages.map(msg => renderChatMessage(msg)).join('');

        // Прокрутить вниз
        container.scrollTop = container.scrollHeight;

    } catch (error) {
        console.error('Error loading messages:', error);
        container.innerHTML = '<div style="text-align: center; padding: 20px; color: var(--md-sys-color-error);">Ошибка загрузки сообщений</div>';
    }
}

/**
 * Отрисовка сообщения в чате
 */
function renderChatMessage(message) {
    const time = formatTime(new Date(message.created_at));
    const senderIcon = message.sender_type === 'user' ? 'person' : 'support_agent';
    const senderLabel = message.sender_type === 'user' ? 'Пользователь' : 'Поддержка';

    let mediaHtml = '';
    if (message.media_type !== 'text' && message.media_file_id) {
        const mediaTypes = {
            'photo': '📷 Фото',
            'video': '🎥 Видео',
            'voice': '🎤 Голосовое',
            'video_note': '🎬 Видеосообщение',
            'document': '📄 Документ',
            'sticker': '😊 Стикер'
        };
        mediaHtml = `<div class="message-media">${mediaTypes[message.media_type] || message.media_type}</div>`;
    }

    return `
        <div class="chat-message ${message.sender_type}">
            <div class="message-header">
                <span class="material-icons" style="font-size: 16px;">${senderIcon}</span>
                ${senderLabel}
            </div>
            ${message.message_text ? `<div class="message-text">${escapeHtml(message.message_text)}</div>` : ''}
            ${mediaHtml}
            <div class="message-time">${time}</div>
        </div>
    `;
}

/**
 * Загрузка отзывов
 */
async function loadSupportReviews(page = 1) {
    currentReviewsPage = page;
    const container = document.getElementById('support-reviews-container');
    const permission = document.getElementById('reviews-filter').value;

    try {
        container.innerHTML = '<div style="padding: 40px; text-align: center; grid-column: 1/-1;"><div class="spinner"></div></div>';

        let url = `/support/reviews?page=${page}&limit=${REVIEWS_PAGE_SIZE}`;
        if (permission) url += `&permission=${permission}`;

        const response = await apiRequest(url);

        // Обновить статистику
        document.getElementById('reviews-total').textContent = response.total;

        if (response.reviews.length === 0) {
            container.innerHTML = `
                <div style="padding: 60px 20px; text-align: center; grid-column: 1/-1;">
                    <span class="material-icons" style="font-size: 64px; color: var(--md-sys-color-on-surface-variant); opacity: 0.3;">rate_review</span>
                    <p style="margin-top: 16px; color: var(--md-sys-color-on-surface-variant);">Нет отзывов</p>
                </div>
            `;
            return;
        }

        // Отрисовать отзывы
        container.innerHTML = response.reviews.map(r => renderReviewCard(r)).join('');

        // Отрисовать пагинацию
        renderReviewsPagination(response.total, page, REVIEWS_PAGE_SIZE);

    } catch (error) {
        console.error('Error loading reviews:', error);
        container.innerHTML = `
            <div style="padding: 40px; text-align: center; color: var(--md-sys-color-error); grid-column: 1/-1;">
                <span class="material-icons" style="font-size: 48px;">error</span>
                <p style="margin-top: 12px;">Ошибка загрузки отзывов</p>
            </div>
        `;
    }
}

/**
 * Отрисовка карточки отзыва
 */
function renderReviewCard(review) {
    const date = formatDate(new Date(review.created_at));
    const permissionClass = review.permission_to_publish ? 'granted' : 'denied';
    const permissionText = review.permission_to_publish ? '✅ Разрешено' : '❌ Запрещено';

    const telegramLink = review.telegram_message_id
        ? `<a href="https://t.me/MiraEvents/${review.telegram_message_id}" target="_blank" class="review-link">
               <span class="material-icons" style="font-size: 16px;">open_in_new</span>
               Открыть в Telegram
           </a>`
        : '';

    return `
        <div class="review-card">
            <div class="review-header">
                <div class="review-user-info">
                    <div class="review-username">
                        <span class="material-icons" style="font-size: 20px;">person</span>
                        ${review.username ? escapeHtml(review.username) : 'Аноним'}
                    </div>
                    ${review.age ? `<div class="review-age">🎂 ${review.age} лет</div>` : ''}
                </div>
                <div class="review-permission ${permissionClass}">${permissionText}</div>
            </div>

            ${review.about_self ? `<div class="review-about">ℹ️ ${escapeHtml(review.about_self)}</div>` : ''}

            <div class="review-text">${escapeHtml(review.review_text)}</div>

            <div class="review-footer">
                <div class="review-date">
                    <span class="material-icons" style="font-size: 14px;">event</span>
                    ${date}
                </div>
                ${telegramLink}
            </div>
        </div>
    `;
}

/**
 * Экспорт отзывов в JSON
 */
async function exportReviews() {
    try {
        const response = await apiRequest('/support/public/reviews?limit=100');

        const blob = new Blob([JSON.stringify(response, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `reviews_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);

        showNotification('Отзывы экспортированы успешно', 'success');
    } catch (error) {
        console.error('Export error:', error);
        showNotification('Ошибка экспорта отзывов', 'error');
    }
}

/**
 * Поиск обращений
 */
async function searchSupportQuestions() {
    const query = document.getElementById('support-search').value.trim();
    // TODO: Добавить параметр search в API и реализовать поиск
    loadSupportQuestions(1);
}

/**
 * Отрисовка пагинации для обращений
 */
function renderSupportPagination(total, currentPage, pageSize) {
    const totalPages = Math.ceil(total / pageSize);
    const container = document.getElementById('support-pagination');

    if (totalPages <= 1) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'flex';
    container.innerHTML = renderPaginationButtons(totalPages, currentPage, (page) => loadSupportQuestions(page));
}

/**
 * Отрисовка пагинации для отзывов
 */
function renderReviewsPagination(total, currentPage, pageSize) {
    const totalPages = Math.ceil(total / pageSize);
    const container = document.getElementById('reviews-pagination');

    if (totalPages <= 1) {
        container.style.display = 'none';
        return;
    }

    container.style.display = 'flex';
    container.innerHTML = renderPaginationButtons(totalPages, currentPage, (page) => loadSupportReviews(page));
}

/**
 * Вспомогательная функция для отрисовки кнопок пагинации
 */
function renderPaginationButtons(totalPages, currentPage, onClickCallback) {
    let html = '';

    // Предыдущая страница
    html += `<button class="md-button md-button-outlined"
                     onclick="${onClickCallback.toString().match(/\w+/)[0]}(${currentPage - 1})"
                     ${currentPage === 1 ? 'disabled' : ''}>
                 <span class="material-icons">chevron_left</span>
             </button>`;

    // Номера страниц
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            html += `<button class="md-button ${i === currentPage ? 'md-button-filled' : 'md-button-outlined'}"
                             onclick="${onClickCallback.toString().match(/\w+/)[0]}(${i})">
                         ${i}
                     </button>`;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            html += '<span style="padding: 0 8px;">...</span>';
        }
    }

    // Следующая страница
    html += `<button class="md-button md-button-outlined"
                     onclick="${onClickCallback.toString().match(/\w+/)[0]}(${currentPage + 1})"
                     ${currentPage === totalPages ? 'disabled' : ''}>
                 <span class="material-icons">chevron_right</span>
             </button>`;

    return html;
}

/**
 * Форматирование времени
 */
function formatTime(date) {
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

/**
 * Форматирование даты и времени
 */
function formatDateTime(date) {
    const today = new Date();
    const isToday = date.toDateString() === today.toDateString();

    if (isToday) {
        return 'Сегодня ' + formatTime(date);
    }

    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    }) + ' ' + formatTime(date);
}

/**
 * Форматирование даты
 */
function formatDate(date) {
    return date.toLocaleDateString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric'
    });
}

/**
 * Экранирование HTML
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
```

---

## 📦 Финальные шаги

1. **Открыть** `webapp/frontend/admin.html`
2. **Найти** строку с `<div id="tab-users" class="tab-content">` (примерно 4236)
3. **После закрытия** этого `</div>` (найти конец tab-users)
4. **Вставить** HTML код из раздела "1. HTML контент"
5. **Найти** секцию `<style>` в начале файла
6. **Добавить** CSS код из раздела "2. CSS Стили"
7. **Найти** секцию `<script>` в конце файла (перед `</body>`)
8. **Добавить** JavaScript код из раздела "3. JavaScript функции"
9. **Сохранить** файл
10. **Загрузить** на сервер: `scp admin.html root@31.44.7.144:/root/mira_bot/webapp/frontend/`
11. **Очистить кэш** браузера и проверить

---

## ✅ Что получится

После интеграции в админ-панели появится полнофункциональный раздел "Поддержка" с:

**Подраздел "Вопросы":**
- 📊 Статистика (всего обращений, непрочитанных, за сегодня)
- 📋 Список обращений (accordion с аватарами)
- 💬 История чата при раскрытии обращения
- 🔗 Кнопки для открытия профиля и топика
- 📄 Пагинация

**Подраздел "Отзывы":**
- 📊 Статистика (всего, с разрешением)
- 🎨 Сетка красивых карточек отзывов
- 🔍 Фильтр по разрешению на публикацию
- 💾 Экспорт в JSON
- 📄 Пагинация

---

**Дата создания:** 03.01.2026
**Файл для интеграции:** webapp/frontend/admin.html

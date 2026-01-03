// Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();

const API_BASE = '/api';

// State
let currentSettings = null;
let currentMoodPeriod = 7;  // Текущий период для графика настроения

// Accordion toggle - делаем глобальной для onclick в HTML
window.toggleAccordion = function(header) {
    console.log('toggleAccordion called', header);
    const content = header.nextElementSibling;
    const isActive = content.classList.contains('active');

    // Toggle active class on header
    header.classList.toggle('active');

    // Toggle content
    if (isActive) {
        content.classList.remove('active');
    } else {
        content.classList.add('active');
    }
    console.log('Accordion toggled, active:', !isActive);
}

// Utils
function showTab(tabName) {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    document.getElementById(`${tabName}-tab`).classList.add('active');
}

async function apiRequest(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        'X-Telegram-Init-Data': tg.initData,
    };

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            ...headers,
            ...options.headers,
        },
    });

    if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
}

// Stats
async function loadStats() {
    try {
        const data = await apiRequest('/stats/');

        // Total messages
        document.getElementById('total-messages').textContent = data.total_messages;
        document.getElementById('week-messages').textContent = data.messages_this_week;

        // Subscription
        const planNames = {
            'trial': '🎁 Trial Premium',
            'premium': '✨ Premium',
            'free': 'Free'
        };

        document.getElementById('subscription-title').textContent = planNames[data.subscription_plan] || 'Free';

        if (data.subscription_days_left !== null) {
            document.getElementById('subscription-info').textContent =
                `Осталось ${data.subscription_days_left} дней`;
        } else {
            document.getElementById('subscription-info').textContent =
                data.subscription_plan === 'premium' ? 'Безлимитно' : 'До 10 сообщений в день';
        }

        // Topics
        const topicsList = document.getElementById('topics-list');
        topicsList.innerHTML = '';

        data.top_topics.forEach(topic => {
            const item = document.createElement('div');
            item.className = 'topic-item';
            item.innerHTML = `
                <span class="topic-name">${topic.topic}</span>
                <span class="topic-count">${topic.count}</span>
            `;
            topicsList.appendChild(item);
        });

        // Emotions
        const emotionsList = document.getElementById('emotions-list');
        emotionsList.innerHTML = '';

        const emotionEmoji = {
            'happy': '😊',
            'sad': '😢',
            'anxious': '😰',
            'angry': '😠',
            'tired': '😴',
            'neutral': '😐',
        };

        Object.entries(data.top_emotions).forEach(([emotion, count]) => {
            const item = document.createElement('div');
            item.className = 'emotion-item';
            item.innerHTML = `
                <span class="emotion-name">${emotionEmoji[emotion] || ''} ${emotion}</span>
                <span class="emotion-count">${count}</span>
            `;
            emotionsList.appendChild(item);
        });

        // Mood chart (load for current period)
        await loadMoodChart(currentMoodPeriod);

    } catch (error) {
        console.error('Failed to load stats:', error);
        tg.showAlert('Ошибка загрузки статистики');
    }
}

// Load mood chart for specific period
async function loadMoodChart(days) {
    try {
        const data = await apiRequest(`/stats/mood/history?days=${days}`);

        // Group by day and calculate averages
        const moodByDay = {};
        data.entries.forEach(entry => {
            const date = entry.date.split('T')[0];
            if (!moodByDay[date]) {
                moodByDay[date] = [];
            }
            moodByDay[date].push(entry);
        });

        const moodChart = Object.keys(moodByDay).sort().map(date => {
            const entries = moodByDay[date];
            const avgScore = entries.reduce((sum, e) => sum + e.mood_score, 0) / entries.length;
            const emotions = entries.map(e => e.primary_emotion).filter(e => e);
            const topEmotion = emotions.length > 0
                ? emotions.sort((a, b) =>
                    emotions.filter(v => v === b).length - emotions.filter(v => v === a).length
                )[0]
                : 'neutral';

            return {
                date: date,
                score: avgScore,
                emotion: topEmotion
            };
        });

        // Calculate summary stats
        updateMoodSummary(moodChart, days);

        // Draw chart with trend line
        drawMoodChart(moodChart, true);

    } catch (error) {
        console.error('Failed to load mood history:', error);
        // Fallback to basic chart from stats
        const statsData = await apiRequest('/stats/');
        drawMoodChart(statsData.mood_chart, false);
    }
}

// Update mood summary stats
function updateMoodSummary(moodData, days) {
    const summaryEl = document.getElementById('mood-summary');

    if (moodData.length === 0) {
        summaryEl.innerHTML = '';
        return;
    }

    // Calculate average
    const avgScore = moodData.reduce((sum, p) => sum + p.score, 0) / moodData.length;

    // Calculate trend (compare first half to second half)
    const midPoint = Math.floor(moodData.length / 2);
    const firstHalf = moodData.slice(0, midPoint);
    const secondHalf = moodData.slice(midPoint);

    let trendHtml = '';
    if (firstHalf.length > 0 && secondHalf.length > 0) {
        const firstAvg = firstHalf.reduce((sum, p) => sum + p.score, 0) / firstHalf.length;
        const secondAvg = secondHalf.reduce((sum, p) => sum + p.score, 0) / secondHalf.length;
        const diff = secondAvg - firstAvg;

        if (Math.abs(diff) > 0.05) {
            const trendClass = diff > 0 ? 'mood-trend-up' : 'mood-trend-down';
            const trendIcon = diff > 0 ? '↗' : '↘';
            const trendPercent = Math.abs(Math.round(diff * 100));
            trendHtml = `
                <div class="mood-stat">
                    Тренд: <span class="value ${trendClass}">${trendIcon} ${trendPercent}%</span>
                </div>
            `;
        }
    }

    // Format average score
    const avgFormatted = avgScore >= 0
        ? `+${(avgScore * 100).toFixed(0)}%`
        : `${(avgScore * 100).toFixed(0)}%`;

    summaryEl.innerHTML = `
        <div class="mood-stat">
            Среднее за ${days}д: <span class="value">${avgFormatted}</span>
        </div>
        ${trendHtml}
    `;
}

function drawMoodChart(moodData, showTrendLine = false) {
    const canvas = document.getElementById('mood-chart');
    const ctx = canvas.getContext('2d');

    // Set canvas size
    canvas.width = canvas.offsetWidth * 2;
    canvas.height = 400;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (moodData.length === 0) {
        ctx.fillStyle = '#999';
        ctx.font = '24px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Нет данных', canvas.width / 2, canvas.height / 2);
        return;
    }

    const padding = 40;
    const width = canvas.width - padding * 2;
    const height = canvas.height - padding * 2;

    // Draw grid
    ctx.strokeStyle = '#e0e0e0';
    ctx.lineWidth = 1;

    for (let i = 0; i <= 5; i++) {
        const y = padding + (height / 5) * i;
        ctx.beginPath();
        ctx.moveTo(padding, y);
        ctx.lineTo(padding + width, y);
        ctx.stroke();
    }

    // Calculate X and Y positions
    const pointsX = moodData.length === 1
        ? [padding + width / 2]
        : moodData.map((_, i) => padding + (width / (moodData.length - 1)) * i);

    const pointsY = moodData.map(point => {
        // Mood score from -1 to 1, map to canvas height
        const normalized = (point.score + 1) / 2; // 0 to 1
        return padding + height * (1 - normalized);
    });

    // Draw trend line (moving average) if enabled
    if (showTrendLine && moodData.length >= 3) {
        const windowSize = Math.min(3, Math.floor(moodData.length / 3));
        const trendY = [];

        for (let i = 0; i < moodData.length; i++) {
            const start = Math.max(0, i - windowSize);
            const end = Math.min(moodData.length, i + windowSize + 1);
            const slice = pointsY.slice(start, end);
            const avg = slice.reduce((a, b) => a + b, 0) / slice.length;
            trendY.push(avg);
        }

        // Draw trend line
        ctx.strokeStyle = 'rgba(102, 126, 234, 0.4)';
        ctx.lineWidth = 8;
        ctx.lineCap = 'round';
        ctx.beginPath();

        pointsX.forEach((x, i) => {
            if (i === 0) {
                ctx.moveTo(x, trendY[i]);
            } else {
                ctx.lineTo(x, trendY[i]);
            }
        });
        ctx.stroke();
    }

    // Draw main line
    ctx.strokeStyle = '#2481cc';
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();

    pointsX.forEach((x, i) => {
        if (i === 0) {
            ctx.moveTo(x, pointsY[i]);
        } else {
            ctx.lineTo(x, pointsY[i]);
        }
    });

    ctx.stroke();

    // Draw points
    pointsX.forEach((x, i) => {
        ctx.beginPath();
        ctx.arc(x, pointsY[i], 6, 0, 2 * Math.PI);
        ctx.fillStyle = '#2481cc';
        ctx.fill();
    });

    // Draw labels (show fewer labels if many points)
    ctx.fillStyle = '#666';
    ctx.font = '18px sans-serif';
    ctx.textAlign = 'center';

    const labelStep = moodData.length > 14 ? 3 : (moodData.length > 7 ? 2 : 1);

    moodData.forEach((point, i) => {
        if (i % labelStep === 0 || i === moodData.length - 1) {
            const date = new Date(point.date);
            const label = `${date.getDate()}/${date.getMonth() + 1}`;
            ctx.fillText(label, pointsX[i], canvas.height - 10);
        }
    });
}

// Programs
async function loadPrograms() {
    const programsList = document.getElementById('programs-list');
    const programsSummary = document.getElementById('programs-summary');

    try {
        const data = await apiRequest('/programs/');

        if (data.programs.length === 0) {
            programsList.innerHTML = `
                <div class="no-programs">
                    <p>У тебя пока нет активных программ.</p>
                    <p>Напиши /programs в боте, чтобы начать!</p>
                </div>
            `;
            programsSummary.innerHTML = '';
            return;
        }

        // Render program cards
        programsList.innerHTML = data.programs.map(program => {
            const statusLabels = {
                'active': 'Активна',
                'completed': 'Завершена',
                'paused': 'На паузе',
                'abandoned': 'Отменена'
            };

            // Build day indicators
            const daysHtml = [];
            const completedDayNumbers = (program.completed_days || []).map(d => d.day);

            for (let day = 1; day <= program.total_days; day++) {
                let dayClass = 'pending';
                if (completedDayNumbers.includes(day)) {
                    dayClass = 'completed';
                } else if (day === program.current_day && program.status === 'active') {
                    dayClass = 'current';
                }
                daysHtml.push(`<div class="day-indicator ${dayClass}">${day}</div>`);
            }

            return `
                <div class="program-card">
                    <div class="program-card-header">
                        <span class="program-name">${program.program_name}</span>
                        <span class="program-status ${program.status}">${statusLabels[program.status] || program.status}</span>
                    </div>
                    <div class="program-progress">
                        <div class="program-progress-bar">
                            <div class="program-progress-fill" style="width: ${program.progress_percentage}%"></div>
                        </div>
                        <div class="program-progress-text">
                            <span>День ${program.current_day} из ${program.total_days}</span>
                            <span>${program.progress_percentage}%</span>
                        </div>
                    </div>
                    <div class="program-days">
                        ${daysHtml.join('')}
                    </div>
                </div>
            `;
        }).join('');

        // Render summary
        if (data.total_active > 0 || data.total_completed > 0) {
            programsSummary.innerHTML = `
                <div class="programs-summary-item">
                    <div class="programs-summary-value">${data.total_active}</div>
                    <div class="programs-summary-label">Активных</div>
                </div>
                <div class="programs-summary-item">
                    <div class="programs-summary-value">${data.total_completed}</div>
                    <div class="programs-summary-label">Завершено</div>
                </div>
            `;
        }

    } catch (error) {
        console.error('Failed to load programs:', error);
        programsList.innerHTML = `
            <div class="no-programs">
                <p>Не удалось загрузить программы</p>
            </div>
        `;
    }
}

// Settings
async function loadSettings() {
    try {
        const data = await apiRequest('/settings/');
        currentSettings = data;

        // Fill form
        document.getElementById('display-name').value = data.display_name || '';
        document.getElementById('persona').value = data.persona || 'mira';

        // Partner name - проверяем, что это строка, а не boolean
        if (data.partner_name && typeof data.partner_name === 'string') {
            document.getElementById('partner-name').value = data.partner_name;
        } else {
            document.getElementById('partner-name').value = '';
        }

        // Partner gender всегда "Мужской" (поле readonly)

        if (data.birthday) {
            document.getElementById('birthday').value = data.birthday;
        }

        if (data.anniversary) {
            document.getElementById('anniversary').value = data.anniversary;
        }

        // Rituals
        const morningEnabled = data.rituals_enabled.includes('morning');
        const eveningEnabled = data.rituals_enabled.includes('evening');

        document.getElementById('ritual-morning').checked = morningEnabled;
        document.getElementById('ritual-evening').checked = eveningEnabled;

        document.getElementById('morning-time').value = data.preferred_time_morning || '09:00';
        document.getElementById('evening-time').value = data.preferred_time_evening || '21:00';

        // Show/hide time inputs based on ritual checkboxes
        document.getElementById('morning-time-group').style.display = morningEnabled ? 'block' : 'none';
        document.getElementById('evening-time-group').style.display = eveningEnabled ? 'block' : 'none';

        document.getElementById('proactive-messages').checked = data.proactive_messages;

        // Новые поля - темы для избегания
        document.getElementById('topics-avoided').value = (data.topics_avoided || []).join(', ');

        // Контентные предпочтения
        const contentPrefs = data.content_preferences || {};

        document.getElementById('meditation-enabled').checked = contentPrefs.meditation_enabled || false;

        if (contentPrefs.meditation_enabled) {
            document.getElementById('meditation-settings').style.display = 'block';
        }

        const meditationTypes = contentPrefs.meditation_types || [];
        document.querySelectorAll('.meditation-type').forEach(checkbox => {
            checkbox.checked = meditationTypes.includes(checkbox.value);
        });

        document.getElementById('meditation-frequency').value = contentPrefs.meditation_frequency || 'daily';

        document.getElementById('exercises-enabled').checked = contentPrefs.exercises_enabled || false;

        // Тихие часы
        if (data.quiet_hours_start) {
            document.getElementById('quiet-start').value = data.quiet_hours_start;
        }
        if (data.quiet_hours_end) {
            document.getElementById('quiet-end').value = data.quiet_hours_end;
        }

    } catch (error) {
        console.error('Failed to load settings:', error);
        tg.showAlert('Ошибка загрузки настроек');
    }
}

async function saveSettings() {
    try {
        tg.MainButton.showProgress();

        // Темы для избегания
        const topicsText = document.getElementById('topics-avoided').value;
        const topicsAvoidedArray = topicsText
            .split(',')
            .map(s => s.trim())
            .filter(s => s.length > 0);

        // Контентные предпочтения
        const meditationEnabled = document.getElementById('meditation-enabled').checked;
        const meditationTypes = Array.from(
            document.querySelectorAll('.meditation-type:checked')
        ).map(cb => cb.value);

        const contentPreferences = {
            meditation_enabled: meditationEnabled,
            meditation_types: meditationTypes,
            meditation_frequency: document.getElementById('meditation-frequency').value,
            exercises_enabled: document.getElementById('exercises-enabled').checked
        };

        // Тихие часы
        const quietStart = document.getElementById('quiet-start').value;
        const quietEnd = document.getElementById('quiet-end').value;

        const settings = {
            display_name: document.getElementById('display-name').value || null,
            persona: document.getElementById('persona').value,
            partner_name: document.getElementById('partner-name').value || null,
            partner_gender: 'male',  // Всегда мужской пол партнёра
            birthday: document.getElementById('birthday').value || null,
            anniversary: document.getElementById('anniversary').value || null,
            rituals_enabled: [
                ...(document.getElementById('ritual-morning').checked ? ['morning'] : []),
                ...(document.getElementById('ritual-evening').checked ? ['evening'] : []),
            ],
            preferred_time_morning: document.getElementById('morning-time').value,
            preferred_time_evening: document.getElementById('evening-time').value,
            proactive_messages: document.getElementById('proactive-messages').checked,
            topics_avoided: topicsAvoidedArray,
            content_preferences: contentPreferences,
            quiet_hours_start: quietStart || null,
            quiet_hours_end: quietEnd || null,
        };

        await apiRequest('/settings/', {
            method: 'PATCH',
            body: JSON.stringify(settings),
        });

        tg.MainButton.hideProgress();
        tg.showAlert('Настройки сохранены!');

        // Reload settings
        await loadSettings();

    } catch (error) {
        console.error('Failed to save settings:', error);
        tg.MainButton.hideProgress();
        tg.showAlert('Ошибка сохранения');
    }
}

// Referral
async function loadReferralData() {
    console.log('Loading referral data...');
    try {
        const codeData = await apiRequest('/referral/code');
        const statsData = await apiRequest('/referral/stats');
        console.log('Referral data loaded:', { codeData, statsData });

        const referralCode = codeData.code || '';
        console.log('Setting referral code:', referralCode);

        // Формируем ссылку на лендинг
        const landingLink = referralCode ? `https://miradrug.ru/?ref=${referralCode}` : 'https://miradrug.ru/';
        console.log('Setting landing link:', landingLink);

        const refLinkEl = document.getElementById('referral-link');
        if (refLinkEl) {
            refLinkEl.value = landingLink;
        }

        const refCountEl = document.getElementById('referral-count');
        if (refCountEl) {
            refCountEl.textContent = statsData.invited_count || 0;
        }

        const refBonusEl = document.getElementById('referral-bonus');
        if (refBonusEl) {
            refBonusEl.textContent = statsData.bonus_earned_days || 0;
        }

        const progressBar = document.getElementById('milestone-progress');
        if (progressBar) {
            progressBar.style.width = (statsData.milestone_progress || 0) + '%';
        }

    } catch (error) {
        console.error('Failed to load referral data:', error);
        // Устанавливаем дефолтные значения при ошибке
        const refLinkEl = document.getElementById('referral-link');
        if (refLinkEl) refLinkEl.value = 'https://miradrug.ru/';

        const refCountEl = document.getElementById('referral-count');
        if (refCountEl) refCountEl.textContent = '0';

        const refBonusEl = document.getElementById('referral-bonus');
        if (refBonusEl) refBonusEl.textContent = '0';
    }
}

// Payment Tab
async function loadPaymentTab() {
    try {
        console.log('Loading payment tab...');
        // Загружаем статистику (там есть подписка)
        const stats = await apiRequest('/stats/');
        console.log('Stats loaded:', stats);
        const referralStats = await apiRequest('/referral/stats');
        console.log('Referral stats loaded:', referralStats);
        const referralCode = await apiRequest('/referral/code');
        console.log('Referral code loaded:', referralCode);

        // Статус подписки
        const statusCard = document.getElementById('payment-status-card');
        const planIcon = document.getElementById('payment-plan-icon');
        const planName = document.getElementById('payment-plan-name');
        const planStatus = document.getElementById('payment-plan-status');
        const daysLeft = document.getElementById('payment-days-left');
        const daysNumber = document.getElementById('days-number');
        const tariffsSection = document.getElementById('tariffs-section');
        const renewSection = document.getElementById('renew-section');

        const plan = stats.subscription_plan || 'free';

        if (plan === 'free') {
            statusCard.classList.add('free');
            planIcon.textContent = '🆓';
            planName.textContent = 'Free';
            planStatus.textContent = 'До 10 сообщений в день';
            daysLeft.style.display = 'none';
            tariffsSection.style.display = 'block';
            renewSection.style.display = 'none';
        } else if (plan === 'trial') {
            statusCard.classList.remove('free');
            planIcon.textContent = '🎁';
            planName.textContent = 'Trial Premium';
            if (stats.subscription_days_left !== null) {
                planStatus.textContent = 'Пробный период';
                daysLeft.style.display = 'block';
                daysNumber.textContent = stats.subscription_days_left;
            }
            tariffsSection.style.display = 'block';
            renewSection.style.display = 'none';
        } else {
            // Premium
            statusCard.classList.remove('free');
            planIcon.textContent = '✨';
            planName.textContent = 'Premium';
            if (stats.subscription_days_left !== null) {
                planStatus.textContent = 'Активна';
                daysLeft.style.display = 'block';
                daysNumber.textContent = stats.subscription_days_left;
                // Показать секцию продления
                renewSection.style.display = 'block';
            } else {
                planStatus.textContent = 'Безлимитно';
                daysLeft.style.display = 'none';
                renewSection.style.display = 'block';
            }
            tariffsSection.style.display = 'block';
        }

        // Реферальные бонусы
        document.getElementById('payment-referral-count').textContent = referralStats.invited_count || 0;
        document.getElementById('payment-referral-days').textContent = referralStats.bonus_earned_days || 0;

        // Реферальная ссылка на лендинг
        const refCode = referralCode.code || '';
        const landingLink = refCode ? `https://miradrug.ru/?ref=${refCode}` : 'https://miradrug.ru/';
        console.log('Setting referral link to:', landingLink);
        document.getElementById('referral-link').value = landingLink;

    } catch (error) {
        console.error('Failed to load payment tab:', error);
    }
}

// Применение промо-кода
async function applyPromoCode() {
    const input = document.getElementById('promo-code-input');
    const resultEl = document.getElementById('promo-result');
    const code = input.value.trim().toUpperCase();

    if (!code) {
        resultEl.textContent = 'Введи промо-код';
        resultEl.className = 'promo-result error';
        return;
    }

    try {
        const response = await apiRequest('/promo/apply', {
            method: 'POST',
            body: JSON.stringify({ code })
        });

        if (response.success) {
            resultEl.textContent = response.message || 'Промо-код применён!';
            resultEl.className = 'promo-result success';
            input.value = '';
            // Перезагрузить данные
            await loadPaymentTab();
            await loadStats();
        } else {
            resultEl.textContent = response.message || 'Не удалось применить промо-код';
            resultEl.className = 'promo-result error';
        }
    } catch (error) {
        console.error('Promo code error:', error);
        resultEl.textContent = 'Ошибка. Попробуй ввести код в боте: /subscription';
        resultEl.className = 'promo-result error';
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    // Tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            if (!tab.dataset.tab) return;
            showTab(tab.dataset.tab);

            // Загрузить реферальные данные при переключении на настройки
            if (tab.dataset.tab === 'settings') {
                loadReferralData();
            }
            // Загрузить данные оплаты
            if (tab.dataset.tab === 'payment') {
                loadPaymentTab();
            }
        });
    });

    // Кнопка применения промо-кода
    document.getElementById('apply-promo-btn').addEventListener('click', applyPromoCode);

    // Enter в поле промо-кода
    document.getElementById('promo-code-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            applyPromoCode();
        }
    });

    // Кнопка продления подписки
    document.getElementById('renew-btn').addEventListener('click', () => {
        // Просто закрываем приложение, пользователь вернётся в бота
        tg.close();
    });

    // Клик по тарифу
    document.querySelectorAll('.tariff-card').forEach(card => {
        card.addEventListener('click', () => {
            // Просто закрываем приложение, пользователь вернётся в бота
            tg.close();
        });
    });

    // Save button
    document.getElementById('save-settings').addEventListener('click', saveSettings);

    // Показать/скрыть настройки медитаций
    document.getElementById('meditation-enabled').addEventListener('change', (e) => {
        const settingsDiv = document.getElementById('meditation-settings');
        settingsDiv.style.display = e.target.checked ? 'block' : 'none';
    });

    // Экспорт истории
    document.getElementById('export-history').addEventListener('click', async () => {
        try {
            const response = await fetch('/api/export/history', {
                headers: {
                    'X-Telegram-Init-Data': tg.initData
                }
            });

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'mira_history.csv';
            a.click();

            tg.showAlert('История скачана');
        } catch (error) {
            console.error('Export history failed:', error);
            tg.showAlert('Ошибка экспорта');
        }
    });

    // Экспорт статистики
    document.getElementById('export-stats').addEventListener('click', async () => {
        try {
            const response = await fetch('/api/export/stats', {
                headers: {
                    'X-Telegram-Init-Data': tg.initData
                }
            });

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'mira_mood.csv';
            a.click();

            tg.showAlert('Статистика скачана');
        } catch (error) {
            console.error('Export stats failed:', error);
            tg.showAlert('Ошибка экспорта');
        }
    });

    // Копировать реферальную ссылку
    document.getElementById('copy-referral').addEventListener('click', async () => {
        const link = document.getElementById('referral-link').value;

        try {
            // Попытка использовать современный Clipboard API
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(link);
                tg.showAlert('Ссылка скопирована');
            } else {
                // Fallback для старых браузеров
                const textArea = document.createElement('textarea');
                textArea.value = link;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();

                try {
                    document.execCommand('copy');
                    tg.showAlert('Ссылка скопирована');
                } catch (err) {
                    tg.showAlert('Не удалось скопировать ссылку');
                }

                document.body.removeChild(textArea);
            }
        } catch (err) {
            console.error('Copy error:', err);
            tg.showAlert('Ошибка копирования');
        }
    });

    // Поделиться в Telegram
    document.getElementById('share-referral').addEventListener('click', () => {
        const link = document.getElementById('referral-link').value;

        if (!link) {
            tg.showAlert('Реферальная ссылка не загружена');
            return;
        }

        const text = `Привет! Попробуй Миру — бота для психологической поддержки 💛`;

        // Используем стандартный метод share
        const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(text)}`;

        if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.openTelegramLink) {
            window.Telegram.WebApp.openTelegramLink(shareUrl);
        } else {
            window.open(shareUrl, '_blank');
        }
    });


    // Period toggle buttons
    document.querySelectorAll('.period-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            // Update active state
            document.querySelectorAll('.period-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // Load data for selected period
            currentMoodPeriod = parseInt(btn.dataset.days);
            await loadMoodChart(currentMoodPeriod);
        });
    });

    // Load data
    loadStats();
    loadSettings();
    loadPrograms();

    // Setup ritual checkboxes to show/hide time inputs
    document.getElementById('ritual-morning').addEventListener('change', (e) => {
        document.getElementById('morning-time-group').style.display = e.target.checked ? 'block' : 'none';
    });

    document.getElementById('ritual-evening').addEventListener('change', (e) => {
        document.getElementById('evening-time-group').style.display = e.target.checked ? 'block' : 'none';
    });

    // Setup accordions with event delegation (более надёжный способ)
    console.log('Setting up accordion event delegation');

    // Используем делегирование событий на уровне документа
    document.addEventListener('click', function(e) {
        const header = e.target.closest('.accordion-header');
        if (header) {
            console.log('Accordion header clicked via delegation', header);
            e.preventDefault();
            e.stopPropagation();
            window.toggleAccordion(header);
        }
    }, true); // capture phase для надёжности

    // Также добавляем touchstart для мобильных устройств
    document.addEventListener('touchstart', function(e) {
        const header = e.target.closest('.accordion-header');
        if (header) {
            console.log('Accordion header touched', header);
            e.preventDefault();
            window.toggleAccordion(header);
        }
    }, { passive: false });

    // Проверяем наличие аккордеонов
    const accordionHeaders = document.querySelectorAll('.accordion-header');
    console.log('Found accordion headers:', accordionHeaders.length);

    // Setup Telegram button
    tg.MainButton.setText('Закрыть');
    tg.MainButton.onClick(() => tg.close());
    tg.MainButton.show();
});

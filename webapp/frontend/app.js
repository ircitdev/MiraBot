// Telegram WebApp
const tg = window.Telegram.WebApp;
tg.expand();

const API_BASE = '/api';

// State
let currentSettings = null;

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

        // Mood chart (simple visualization)
        drawMoodChart(data.mood_chart);

    } catch (error) {
        console.error('Failed to load stats:', error);
        tg.showAlert('Ошибка загрузки статистики');
    }
}

function drawMoodChart(moodData) {
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

    // Draw line
    ctx.strokeStyle = '#2481cc';
    ctx.lineWidth = 3;
    ctx.beginPath();

    const pointsX = moodData.map((_, i) => padding + (width / (moodData.length - 1)) * i);
    const pointsY = moodData.map(point => {
        // Mood score from -1 to 1, map to canvas height
        const normalized = (point.score + 1) / 2; // 0 to 1
        return padding + height * (1 - normalized);
    });

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

    // Draw labels
    ctx.fillStyle = '#666';
    ctx.font = '20px sans-serif';
    ctx.textAlign = 'center';

    moodData.forEach((point, i) => {
        const date = new Date(point.date);
        const label = `${date.getDate()}/${date.getMonth() + 1}`;
        ctx.fillText(label, pointsX[i], canvas.height - 10);
    });
}

// Settings
async function loadSettings() {
    try {
        const data = await apiRequest('/settings/');
        currentSettings = data;

        // Fill form
        document.getElementById('display-name').value = data.display_name || '';
        document.getElementById('persona').value = data.persona || 'mira';
        document.getElementById('partner-name').value = data.partner_name || '';
        document.getElementById('partner-gender').value = data.partner_gender || '';

        if (data.birthday) {
            document.getElementById('birthday').value = data.birthday;
        }

        if (data.anniversary) {
            document.getElementById('anniversary').value = data.anniversary;
        }

        // Rituals
        document.getElementById('ritual-morning').checked = data.rituals_enabled.includes('morning');
        document.getElementById('ritual-evening').checked = data.rituals_enabled.includes('evening');

        document.getElementById('morning-time').value = data.preferred_time_morning || '09:00';
        document.getElementById('evening-time').value = data.preferred_time_evening || '21:00';

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
            partner_gender: document.getElementById('partner-gender').value || null,
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
    try {
        const codeData = await apiRequest('/referral/code');
        const statsData = await apiRequest('/referral/stats');

        document.getElementById('referral-link').value = codeData.link;
        document.getElementById('referral-count').textContent = statsData.invited_count;
        document.getElementById('referral-bonus').textContent = statsData.bonus_earned_days;

        const progressBar = document.getElementById('milestone-progress');
        progressBar.style.width = statsData.milestone_progress + '%';

    } catch (error) {
        console.error('Failed to load referral data:', error);
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    // Tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            showTab(tab.dataset.tab);

            // Загрузить реферальные данные при переключении на настройки
            if (tab.dataset.tab === 'settings') {
                loadReferralData();
            }
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
    document.getElementById('copy-referral').addEventListener('click', () => {
        const link = document.getElementById('referral-link');
        link.select();
        document.execCommand('copy');
        tg.showAlert('Ссылка скопирована');
    });

    // Поделиться в Telegram
    document.getElementById('share-referral').addEventListener('click', () => {
        const link = document.getElementById('referral-link').value;
        const text = encodeURIComponent(
            `Привет! Попробуй Миру — бота для психологической поддержки 💛\n\n${link}`
        );
        const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${text}`;
        window.open(shareUrl, '_blank');
    });

    // Load data
    loadStats();
    loadSettings();

    // Setup Telegram button
    tg.MainButton.setText('Закрыть');
    tg.MainButton.onClick(() => tg.close());
    tg.MainButton.show();
});

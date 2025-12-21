with open('/root/mira_bot/webapp/frontend/admin.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''                messages.forEach(msg => {
                    const messageDiv = document.createElement('div');
                    const isUser = msg.role === 'user';
                    messageDiv.className = `message ${isUser ? 'message-user' : 'message-assistant'}`;

                    const date = new Date(msg.created_at).toLocaleString('ru-RU');
                    const roleName = isUser ? 'Пользователь' : 'Мира';

                    let tagsHtml = '';
                    if (msg.tags && msg.tags.length > 0) {
                        tagsHtml = `<div class="message-tags">🏷️ ${msg.tags.join(', ')}</div>`;
                    }

                    messageDiv.innerHTML = `
                        <div class="message-header">
                            <span class="message-role">${roleName}</span>
                            <span class="message-date">${date}</span>
                        </div>
                        <div class="message-content">${msg.content}</div>
                        ${tagsHtml}
                    `;

                    chatContainer.appendChild(messageDiv);
                });'''

new_code = '''                messages.forEach(msg => {
                    const messageDiv = document.createElement('div');
                    const isUser = msg.role === 'user';
                    messageDiv.className = `message ${isUser ? 'message-user' : 'message-assistant'}`;

                    const date = new Date(msg.created_at).toLocaleString('ru-RU');
                    const roleName = isUser ? 'Пользователь' : 'Мира';

                    let tagsHtml = '';
                    if (msg.tags && msg.tags.length > 0) {
                        tagsHtml = `<div class="message-tags">🏷️ ${msg.tags.join(', ')}</div>`;
                    }

                    // Определяем контент с медиа
                    let contentHtml = '';
                    const hasPhoto = msg.tags && msg.tags.includes('photo');
                    const isVoice = msg.message_type === 'voice';

                    if (hasPhoto && msg.file_url) {
                        // Фото с превью
                        contentHtml = `
                            <div class="message-media">
                                <img src="${msg.file_url}" class="message-photo" alt="photo" onclick="openPhotoModal('${msg.file_url}')">
                            </div>
                            <div class="message-text">${escapeHtml(msg.content)}</div>
                        `;
                    } else if (isVoice && msg.file_url) {
                        // Голосовое сообщение с плеером
                        contentHtml = `
                            <div class="message-voice">
                                <div class="voice-player">
                                    <button class="voice-play-btn" onclick="toggleVoicePlay(this, '${msg.file_url}')">
                                        <span class="material-icons">play_arrow</span>
                                    </button>
                                    <div class="voice-wave">
                                        <div class="voice-progress" data-audio="${msg.file_url}"></div>
                                    </div>
                                    <span class="voice-duration">--:--</span>
                                </div>
                            </div>
                            <div class="message-text">${escapeHtml(msg.content)}</div>
                        `;
                    } else if (hasPhoto && !msg.file_url) {
                        // Фото без URL - показываем плейсхолдер
                        contentHtml = `
                            <div class="message-media message-media-placeholder">
                                <span class="material-icons">image</span>
                                <span>photo</span>
                            </div>
                            <div class="message-text">${escapeHtml(msg.content)}</div>
                        `;
                    } else if (isVoice && !msg.file_url) {
                        // Голосовое без URL
                        contentHtml = `
                            <div class="message-voice message-voice-placeholder">
                                <span class="material-icons">mic</span>
                                <span>voice</span>
                            </div>
                            <div class="message-text">${escapeHtml(msg.content)}</div>
                        `;
                    } else {
                        // Обычный текст
                        contentHtml = `<div class="message-text">${escapeHtml(msg.content)}</div>`;
                    }

                    messageDiv.innerHTML = `
                        <div class="message-header">
                            <span class="message-role">${roleName}</span>
                            <span class="message-date">${date}</span>
                        </div>
                        <div class="message-content">${contentHtml}</div>
                        ${tagsHtml}
                    `;

                    chatContainer.appendChild(messageDiv);
                });'''

content = content.replace(old_code, new_code)

with open('/root/mira_bot/webapp/frontend/admin.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Message rendering updated')

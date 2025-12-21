with open('/root/mira_bot/webapp/frontend/admin.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''                // Превью для картинок
                let previewContent;
                if (isImage && file.gcs_url) {
                    previewContent = `<img src="${file.gcs_url}" alt="preview" loading="lazy" onclick="openFileModal('${file.gcs_url}', '${file.file_type}', '${formatDate(file.created_at)}', ${file.file_size || 0})">`;
                } else {
                    previewContent = `<span class="material-icons">${icon}</span>`;
                }

                // Формат даты
                const date = formatDate(file.created_at);

                // Размер файла
                const size = file.file_size ? formatFileSize(file.file_size) : '';

                return `
                    <div class="file-item" ${file.gcs_url ? `onclick="openFileModal('${file.gcs_url}', '${file.file_type}', '${date}', ${file.file_size || 0})"` : ''}>
                        <div class="file-preview">
                            ${previewContent}
                        </div>
                        <div class="file-info">
                            <div class="file-type">${file.file_type}</div>
                            <div class="file-date">${date}</div>
                            ${size ? `<div class="file-size">${size}</div>` : ''}
                        </div>
                    </div>
                `;'''

new_code = '''                // Превью для картинок
                let previewContent;
                if (isImage && file.gcs_url) {
                    previewContent = `<img src="${file.gcs_url}" alt="preview" loading="lazy">`;
                } else if (isVoice && file.gcs_url) {
                    // Мини-плеер для голосовых
                    previewContent = `
                        <div class="voice-mini-player" onclick="event.stopPropagation()">
                            <button class="voice-play-btn-sm" onclick="event.stopPropagation(); toggleVoicePlay(this, '${file.gcs_url}')">
                                <span class="material-icons">play_arrow</span>
                            </button>
                            <div class="voice-wave-sm">
                                <div class="voice-progress"></div>
                            </div>
                            <span class="voice-duration">--:--</span>
                        </div>
                    `;
                } else {
                    previewContent = `<span class="material-icons">${icon}</span>`;
                }

                // Формат даты
                const date = formatDate(file.created_at);

                // Размер файла
                const size = file.file_size ? formatFileSize(file.file_size) : '';

                // Для голосовых не нужен onclick на весь элемент
                const itemClick = (isVoice || !file.gcs_url) ? '' : `onclick="openFileModal('${file.gcs_url}', '${file.file_type}', '${date}', ${file.file_size || 0})"`;

                return `
                    <div class="file-item ${isVoice ? 'file-item-voice' : ''}" ${itemClick}>
                        <div class="file-preview">
                            ${previewContent}
                        </div>
                        <div class="file-info">
                            <div class="file-type">${file.file_type}</div>
                            <div class="file-date">${date}</div>
                            ${size ? `<div class="file-size">${size}</div>` : ''}
                        </div>
                    </div>
                `;'''

content = content.replace(old_code, new_code)

with open('/root/mira_bot/webapp/frontend/admin.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Gallery rendering updated')

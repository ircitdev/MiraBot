/**
 * Загрузка списка документации в sidebar
 */
async function loadDocumentation() {
    const docsList = document.getElementById('docs-list');
    const container = document.getElementById('documentation-container');

    docsList.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
    container.innerHTML = '<div class="docs-placeholder"><span class="material-icons" style="font-size: 64px; color: var(--md-sys-color-outline); margin-bottom: 16px;">description</span><p style="color: var(--md-sys-color-on-surface-variant); font-size: 16px;">Выберите документ из списка слева</p></div>';

    try {
        const data = await apiRequest('/documentation');
        if (data && data.documents) {
            const documents = data.documents;

            if (documents.length === 0) {
                docsList.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--md-sys-color-error);">Документация не найдена</div>';
                return;
            }

            // Группируем по папкам
            const groupedDocs = {};
            documents.forEach(doc => {
                if (!groupedDocs[doc.folder]) {
                    groupedDocs[doc.folder] = [];
                }
                groupedDocs[doc.folder].push(doc);
            });

            let html = '';

            // Создаём список по папкам
            Object.keys(groupedDocs).sort().forEach(folder => {
                const folderName = folder === 'root' ? 'Корень' : folder;
                html += `<div class="docs-list-group">`;
                html += `<div class="docs-list-group-title">${folderName}</div>`;

                groupedDocs[folder].forEach(doc => {
                    html += `
                        <div class="docs-list-item" onclick="loadDocumentFile('${doc.path}', this)">
                            <span class="material-icons">description</span>
                            <div class="docs-list-item-content">
                                <div class="docs-list-item-name">${doc.name}</div>
                                <div class="docs-list-item-meta">
                                    <span>${doc.size_kb} KB</span>
                                    <span>${new Date(doc.modified_at).toLocaleDateString('ru-RU')}</span>
                                </div>
                            </div>
                        </div>
                    `;
                });

                html += `</div>`;
            });

            docsList.innerHTML = html;
        } else {
            docsList.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--md-sys-color-error);">Не удалось загрузить список документации</div>';
        }
    } catch (error) {
        console.error('Failed to load documentation:', error);
        docsList.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--md-sys-color-error);">Ошибка загрузки: ' + (error.message || 'неизвестная ошибка') + '</div>';
    }
}

/**
 * Загрузка конкретного файла документации
 */
async function loadDocumentFile(docPath, element) {
    const container = document.getElementById('documentation-container');

    // Убираем active класс со всех элементов
    document.querySelectorAll('.docs-list-item').forEach(item => {
        item.classList.remove('active');
    });

    // Добавляем active класс к выбранному элементу
    if (element) {
        element.classList.add('active');
    }

    // Обновляем URL с полным путем к документу (не перезагружая страницу)
    const fileName = docPath.split('/').pop();
    history.replaceState(null, '', `#docs/documentation/${fileName}`);

    container.innerHTML = '<div class="loading"><div class="spinner"></div><div>Загрузка документа...</div></div>';

    try {
        const data = await apiRequest(`/documentation/${encodeURIComponent(docPath)}`);
        if (data && data.content) {
            const markdown = data.content;
            const contentHtml = renderMarkdownToHTML(markdown);

            const html = `
                <div style="margin-bottom: 24px;">
                    <div style="font-size: 28px; font-weight: 500; color: var(--md-sys-color-on-surface); margin-bottom: 8px;">
                        ${data.name}
                    </div>
                    <div style="color: var(--md-sys-color-on-surface-variant); font-size: 13px; display: flex; gap: 16px;">
                        <span>${data.size_kb} KB</span>
                        <span>${data.path}</span>
                    </div>
                </div>
                <div>
                    ${contentHtml}
                </div>
            `;

            container.innerHTML = html;
        } else {
            container.innerHTML = '<div class="error-message">Не удалось загрузить документ</div>';
        }
    } catch (error) {
        console.error('Failed to load document:', error);
        container.innerHTML = '<div class="error-message">Ошибка загрузки документа: ' + (error.message || 'неизвестная ошибка') + '</div>';
    }
}

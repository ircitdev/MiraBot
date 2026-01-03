/**
 * Загрузка списка документации
 */
async function loadDocumentation() {
    const container = document.getElementById('documentation-container');
    container.innerHTML = '<div class="loading"><div class="spinner"></div><div>Загрузка документации...</div></div>';

    try {
        const data = await apiRequest('/documentation');
        if (data && data.documents) {
            const documents = data.documents;

            if (documents.length === 0) {
                container.innerHTML = '<div class="error-message">Документация не найдена</div>';
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

            let html = `
                <div style="margin-bottom: 24px;">
                    <div style="font-size: 24px; font-weight: 500; color: var(--md-sys-color-on-surface); margin-bottom: 8px;">
                        📚 Документация проекта
                    </div>
                    <div style="color: var(--md-sys-color-on-surface-variant); font-size: 14px;">
                        Все документы и отчёты
                    </div>
                </div>
            `;

            // Создаём список по папкам
            Object.keys(groupedDocs).sort().forEach(folder => {
                const folderName = folder === 'root' ? '📁 Корень' : \`📁 \${folder}\`;
                html += \`
                    <div style="margin-bottom: 24px;">
                        <h3 style="color: var(--md-sys-color-primary); margin-bottom: 12px;">\${folderName}</h3>
                        <div style="display: grid; gap: 12px;">
                \`;

                groupedDocs[folder].forEach(doc => {
                    html += \`
                        <div class="doc-card" onclick="loadDocumentFile('\${doc.path}')" style="
                            padding: 16px;
                            border: 1px solid var(--md-sys-color-outline);
                            border-radius: 12px;
                            cursor: pointer;
                            transition: all 0.2s;
                            background: var(--md-sys-color-surface);
                        " onmouseover="this.style.background='var(--md-sys-color-surface-variant)'" onmouseout="this.style.background='var(--md-sys-color-surface)'">
                            <div style="display: flex; justify-content: space-between; align-items: start;">
                                <div style="flex: 1;">
                                    <div style="font-weight: 500; color: var(--md-sys-color-on-surface); margin-bottom: 4px;">
                                        📄 \${doc.name}
                                    </div>
                                    <div style="font-size: 12px; color: var(--md-sys-color-on-surface-variant);">
                                        \${doc.size_kb} KB • \${new Date(doc.modified_at).toLocaleDateString('ru-RU')}
                                    </div>
                                </div>
                                <span class="material-icons" style="color: var(--md-sys-color-on-surface-variant);">arrow_forward</span>
                            </div>
                        </div>
                    \`;
                });

                html += \`
                        </div>
                    </div>
                \`;
            });

            container.innerHTML = html;
        } else {
            container.innerHTML = '<div class="error-message">Не удалось загрузить список документации</div>';
        }
    } catch (error) {
        console.error('Failed to load documentation:', error);
        container.innerHTML = '<div class="error-message">Ошибка загрузки документации: ' + (error.message || 'неизвестная ошибка') + '</div>';
    }
}

/**
 * Загрузка конкретного файла документации
 */
async function loadDocumentFile(docPath) {
    const container = document.getElementById('documentation-container');
    container.innerHTML = '<div class="loading"><div class="spinner"></div><div>Загрузка документа...</div></div>';

    try {
        const data = await apiRequest(\`/documentation/\${encodeURIComponent(docPath)}\`);
        if (data && data.content) {
            const markdown = data.content;
            const contentHtml = renderMarkdownToHTML(markdown);

            const html = \`
                <div style="margin-bottom: 24px;">
                    <button class="md-button md-button-outlined" onclick="loadDocumentation()" style="margin-bottom: 16px;">
                        <span class="material-icons">arrow_back</span>
                        Назад к списку
                    </button>
                    <div style="font-size: 24px; font-weight: 500; color: var(--md-sys-color-on-surface); margin-bottom: 8px;">
                        📄 \${data.name}
                    </div>
                    <div style="color: var(--md-sys-color-on-surface-variant); font-size: 14px;">
                        \${data.size_kb} KB • \${data.path}
                    </div>
                </div>
                <div style="padding: 20px; background: var(--md-sys-color-surface); border-radius: 12px; border: 1px solid var(--md-sys-color-outline);">
                    \${contentHtml}
                </div>
            \`;

            container.innerHTML = html;
        } else {
            container.innerHTML = '<div class="error-message">Не удалось загрузить документ</div>';
        }
    } catch (error) {
        console.error('Failed to load document:', error);
        container.innerHTML = '<div class="error-message">Ошибка загрузки документа: ' + (error.message || 'неизвестная ошибка') + '</div>';
    }
}

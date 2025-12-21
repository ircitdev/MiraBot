with open('/root/mira_bot/webapp/frontend/admin.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_form = '''        function addPhoto() {
            const modal = document.createElement("div");
            modal.className = "photo-modal-overlay";
            modal.innerHTML = `
                <div class="photo-modal" style="max-width: 600px;">
                    <button class="photo-modal-close" onclick="this.closest('.photo-modal-overlay').remove()">
                        <span class="material-icons">close</span>
                    </button>
                    <div style="padding: 24px;">
                        <h3 style="margin-bottom: 20px;">Добавить новое фото</h3>
                        <form id="add-photo-form" onsubmit="submitNewPhoto(event)">
                            <div style="margin-bottom: 16px;">
                                <label class="md-label">Файл изображения</label>
                                <input type="file" id="new-photo-file" accept="image/*" class="md-input" required>
                            </div>
                            <div style="margin-bottom: 16px;">
                                <label class="md-label">Название</label>
                                <input type="text" id="new-photo-title" class="md-input" placeholder="Название фото" required>
                            </div>
                            <div style="margin-bottom: 16px;">
                                <label class="md-label">История</label>
                                <textarea id="new-photo-story" class="md-input" rows="4" placeholder="История этого фото..." required></textarea>
                            </div>
                            <div style="margin-bottom: 16px;">
                                <label class="md-label">Настроение</label>
                                <input type="text" id="new-photo-mood" class="md-input" placeholder="счастливая, радостная">
                            </div>
                            <div style="margin-bottom: 16px;">
                                <label class="md-label">Контекст</label>
                                <input type="text" id="new-photo-context" class="md-input" placeholder="дом, праздник, семья">
                            </div>
                            <div style="margin-bottom: 16px;">
                                <label class="md-label">Люди на фото</label>
                                <input type="text" id="new-photo-people" class="md-input" placeholder="с мужем Андреем">
                            </div>
                            <div style="margin-bottom: 16px;">
                                <label class="md-label">Теги (через запятую)</label>
                                <input type="text" id="new-photo-tags" class="md-input" placeholder="семья, праздник, дом">
                            </div>
                            <div style="display: flex; gap: 12px; justify-content: flex-end;">
                                <button type="button" class="md-button" onclick="this.closest('.photo-modal-overlay').remove()">Отмена</button>
                                <button type="submit" class="md-button md-button-primary">Добавить</button>
                            </div>
                        </form>
                    </div>
                </div>
            `;
            modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
            document.body.appendChild(modal);
        }'''

new_form = '''        function addPhoto() {
            const modal = document.createElement("div");
            modal.className = "photo-modal-overlay";
            modal.innerHTML = `
                <div class="photo-modal" style="max-width: 500px; max-height: 90vh; overflow-y: auto;">
                    <button class="photo-modal-close" onclick="this.closest('.photo-modal-overlay').remove()">
                        <span class="material-icons">close</span>
                    </button>
                    <div style="padding: 24px;">
                        <h3 style="margin: 0 0 24px 0; font-size: 20px; font-weight: 500; color: var(--md-sys-color-on-surface); display: flex; align-items: center; gap: 8px;">
                            <span class="material-icons">add_photo_alternate</span>
                            Добавить фото
                        </h3>
                        <form id="add-photo-form" onsubmit="submitNewPhoto(event)">
                            <div class="form-field">
                                <label>Файл изображения</label>
                                <div class="file-upload-wrapper">
                                    <input type="file" id="new-photo-file" accept="image/*" required onchange="updateFileName(this)">
                                    <div class="file-upload-btn">
                                        <span class="material-icons">upload_file</span>
                                        <span id="file-name-display">Выберите файл...</span>
                                    </div>
                                </div>
                            </div>
                            <div class="form-field">
                                <label>Название *</label>
                                <input type="text" id="new-photo-title" placeholder="Например: Наш отпуск в горах" required>
                            </div>
                            <div class="form-field">
                                <label>История *</label>
                                <textarea id="new-photo-story" rows="3" placeholder="Расскажите историю этого момента..." required></textarea>
                            </div>
                            <div class="form-row">
                                <div class="form-field">
                                    <label>Настроение</label>
                                    <input type="text" id="new-photo-mood" placeholder="радостная">
                                </div>
                                <div class="form-field">
                                    <label>Люди на фото</label>
                                    <input type="text" id="new-photo-people" placeholder="с Андреем">
                                </div>
                            </div>
                            <div class="form-field">
                                <label>Контекст</label>
                                <input type="text" id="new-photo-context" placeholder="дом, праздник, семья">
                            </div>
                            <div class="form-field">
                                <label>Теги (через запятую)</label>
                                <input type="text" id="new-photo-tags" placeholder="семья, праздник, радость">
                            </div>
                            <div class="form-actions">
                                <button type="button" class="md-button" onclick="this.closest('.photo-modal-overlay').remove()">
                                    Отмена
                                </button>
                                <button type="submit" class="md-button md-button-primary">
                                    <span class="material-icons" style="font-size: 18px; margin-right: 4px;">add</span>
                                    Добавить
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            `;
            modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
            document.body.appendChild(modal);
        }

        function updateFileName(input) {
            const display = document.getElementById('file-name-display');
            if (input.files && input.files[0]) {
                display.textContent = input.files[0].name;
            } else {
                display.textContent = 'Выберите файл...';
            }
        }'''

content = content.replace(old_form, new_form)

with open('/root/mira_bot/webapp/frontend/admin.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Form updated')

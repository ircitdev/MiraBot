with open('/root/mira_bot/webapp/frontend/admin.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_js = '''        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function generateReport() {'''

new_js = '''        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Photo modal for conversation
        function openPhotoModal(url) {
            const modal = document.createElement('div');
            modal.className = 'photo-view-modal';
            modal.innerHTML = `
                <button class="close-btn" onclick="this.parentElement.remove()">
                    <span class="material-icons">close</span>
                </button>
                <img src="${url}" alt="photo">
            `;
            modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
            document.body.appendChild(modal);
        }

        // Voice player
        let currentAudio = null;
        let currentPlayBtn = null;

        function toggleVoicePlay(btn, url) {
            // Если играет другое аудио - останавливаем
            if (currentAudio && currentPlayBtn !== btn) {
                currentAudio.pause();
                currentAudio = null;
                if (currentPlayBtn) {
                    currentPlayBtn.innerHTML = '<span class="material-icons">play_arrow</span>';
                }
            }

            if (!currentAudio || currentPlayBtn !== btn) {
                // Создаём новое аудио
                currentAudio = new Audio(url);
                currentPlayBtn = btn;

                const voicePlayer = btn.closest('.voice-player');
                const progressBar = voicePlayer.querySelector('.voice-progress');
                const durationSpan = voicePlayer.querySelector('.voice-duration');
                const waveEl = voicePlayer.querySelector('.voice-wave');

                currentAudio.addEventListener('loadedmetadata', () => {
                    const mins = Math.floor(currentAudio.duration / 60);
                    const secs = Math.floor(currentAudio.duration % 60);
                    durationSpan.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
                });

                currentAudio.addEventListener('timeupdate', () => {
                    const progress = (currentAudio.currentTime / currentAudio.duration) * 100;
                    progressBar.style.width = progress + '%';

                    const mins = Math.floor(currentAudio.currentTime / 60);
                    const secs = Math.floor(currentAudio.currentTime % 60);
                    durationSpan.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
                });

                currentAudio.addEventListener('ended', () => {
                    btn.innerHTML = '<span class="material-icons">play_arrow</span>';
                    progressBar.style.width = '0%';
                    currentAudio = null;
                    currentPlayBtn = null;
                });

                // Click on wave to seek
                waveEl.onclick = (e) => {
                    if (currentAudio && currentAudio.duration) {
                        const rect = waveEl.getBoundingClientRect();
                        const percent = (e.clientX - rect.left) / rect.width;
                        currentAudio.currentTime = percent * currentAudio.duration;
                    }
                };

                currentAudio.play();
                btn.innerHTML = '<span class="material-icons">pause</span>';
            } else {
                // Toggle play/pause
                if (currentAudio.paused) {
                    currentAudio.play();
                    btn.innerHTML = '<span class="material-icons">pause</span>';
                } else {
                    currentAudio.pause();
                    btn.innerHTML = '<span class="material-icons">play_arrow</span>';
                }
            }
        }

        async function generateReport() {'''

content = content.replace(old_js, new_js)

with open('/root/mira_bot/webapp/frontend/admin.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Media JS functions added')

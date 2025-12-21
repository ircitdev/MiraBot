with open('/root/mira_bot/webapp/frontend/admin.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_css = '''.file-item:hover {
            transform: translateY(-2px);
            box-shadow: var(--md-sys-elevation-2);
        }

        .file-preview {'''

new_css = '''.file-item:hover {
            transform: translateY(-2px);
            box-shadow: var(--md-sys-elevation-2);
        }

        .file-item-voice {
            cursor: default;
        }
        .file-item-voice:hover {
            transform: none;
        }

        /* Mini voice player for gallery */
        .voice-mini-player {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 8px;
            width: 100%;
        }
        .voice-play-btn-sm {
            width: 28px;
            height: 28px;
            border-radius: 50%;
            border: none;
            background: var(--md-sys-color-primary);
            color: var(--md-sys-color-on-primary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .voice-play-btn-sm .material-icons {
            font-size: 18px;
        }
        .voice-wave-sm {
            flex: 1;
            height: 20px;
            background: var(--md-sys-color-outline);
            border-radius: 3px;
            position: relative;
        }
        .voice-wave-sm .voice-progress {
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
            width: 0%;
            background: var(--md-sys-color-primary);
            border-radius: 3px;
        }
        .voice-mini-player .voice-duration {
            font-size: 10px;
            color: var(--md-sys-color-on-surface-variant);
            min-width: 30px;
        }

        .file-preview {'''

content = content.replace(old_css, new_css)

with open('/root/mira_bot/webapp/frontend/admin.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Voice mini player CSS added')

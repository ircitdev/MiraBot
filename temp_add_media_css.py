with open('/root/mira_bot/webapp/frontend/admin.html', 'r', encoding='utf-8') as f:
    content = f.read()

old_css = '''.message-content {
            word-wrap: break-word;
        }

        .message-tags {'''

new_css = '''.message-content {
            word-wrap: break-word;
        }

        /* Message media styles */
        .message-media {
            margin-bottom: 8px;
        }
        .message-photo {
            max-width: 200px;
            max-height: 200px;
            border-radius: 8px;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .message-photo:hover {
            transform: scale(1.02);
        }
        .message-media-placeholder,
        .message-voice-placeholder {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 12px;
            background: var(--md-sys-color-surface-variant);
            border-radius: 8px;
            font-size: 12px;
            color: var(--md-sys-color-on-surface-variant);
        }
        .message-media-placeholder .material-icons,
        .message-voice-placeholder .material-icons {
            font-size: 18px;
        }
        .message-voice {
            margin-bottom: 8px;
        }
        .voice-player {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 12px;
            background: var(--md-sys-color-surface-variant);
            border-radius: 20px;
            max-width: 280px;
        }
        .voice-play-btn {
            width: 32px;
            height: 32px;
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
        .voice-play-btn:hover {
            opacity: 0.9;
        }
        .voice-play-btn .material-icons {
            font-size: 20px;
        }
        .voice-wave {
            flex: 1;
            height: 24px;
            background: linear-gradient(90deg,
                var(--md-sys-color-primary) 0%,
                var(--md-sys-color-primary) var(--progress, 0%),
                var(--md-sys-color-outline) var(--progress, 0%),
                var(--md-sys-color-outline) 100%);
            border-radius: 4px;
            position: relative;
            cursor: pointer;
        }
        .voice-progress {
            position: absolute;
            left: 0;
            top: 0;
            height: 100%;
            width: 0%;
            background: var(--md-sys-color-primary);
            border-radius: 4px;
            transition: width 0.1s;
        }
        .voice-duration {
            font-size: 11px;
            color: var(--md-sys-color-on-surface-variant);
            min-width: 35px;
            text-align: right;
        }
        .message-text {
            white-space: pre-wrap;
        }

        /* Photo modal for conversation */
        .photo-view-modal {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.9);
            z-index: 3000;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .photo-view-modal img {
            max-width: 90vw;
            max-height: 90vh;
            border-radius: 8px;
        }
        .photo-view-modal .close-btn {
            position: absolute;
            top: 20px;
            right: 20px;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            border: none;
            background: rgba(255,255,255,0.2);
            color: white;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .message-tags {'''

content = content.replace(old_css, new_css)

with open('/root/mira_bot/webapp/frontend/admin.html', 'w', encoding='utf-8') as f:
    f.write(content)

print('Media CSS added')

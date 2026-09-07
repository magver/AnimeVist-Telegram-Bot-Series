"""
Standalone AnimeVist Patchnote Publisher.
Fetches official releases from GitHub Releases API or accepts custom changelogs,
then formats and broadcasts rich update posts (#patchnote) to Telegram.
"""

import os
import sys
import json
import urllib.request

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram_sender import TelegramSender, load_config

def fetch_latest_github_release():
    config = load_config()
    repo = config.get('app', {}).get('github_repo', 'magver/AnimeVist-Releases')
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'AnimeVistBot/1.0',
        'Accept': 'application/vnd.github.v3+json'
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        print(f"[Patchnote] Ошибка запроса к GitHub API: {e}")
        return None

def publish_patchnote_from_github(dry_run=False):
    config = load_config()
    sender = TelegramSender()
    app_name = config.get('app', {}).get('name', 'AnimeVist')
    repo = config.get('app', {}).get('github_repo', 'magver/AnimeVist-Releases')

    rel = fetch_latest_github_release()
    if not rel:
        print("[Patchnote] Не удалось получить данные релиза с GitHub.")
        return False

    tag_name = rel.get('tag_name', 'v1.0.0')
    release_name = rel.get('name') or f"{app_name} {tag_name}"
    body = rel.get('body', '')
    html_url = rel.get('html_url')

    # Find download links from assets
    win_download = f"https://github.com/{repo}/releases/download/{tag_name}/{app_name}-Setup-{tag_name.replace('v', '')}.exe"
    apk_download = f"https://github.com/{repo}/releases/download/{tag_name}/{app_name}-{tag_name.replace('v', '')}.apk"
    apk_browser_download_url = None

    for asset in rel.get('assets', []):
        name = asset.get('name', '').lower()
        if name.endswith('.apk'):
            apk_download = asset.get('browser_download_url')
            apk_browser_download_url = apk_download
        elif name.endswith('.exe') and 'setup' in name:
            win_download = asset.get('browser_download_url')

    # Extract highlights from body if formatted
    lines = body.split('\n')
    bullets = []
    for l in lines:
        clean = l.strip()
        if clean.startswith('- ') or clean.startswith('* '):
            bullets.append(clean[2:].strip())

    if bullets:
        highlights_html = "\n".join([f"• {b}" for b in bullets[:6]])
    else:
        highlights_html = (
            "• Бесшовная сквозная синхронизация истории и серий между ПК и Android.\n"
            "• Плеер с автопропуском опенингов (+85с) и качеством 1080p Full HD.\n"
            "• Повышенная стабильность воспроизведения потоков."
        )

    text = (
        f"🚀 <b>Обновление {app_name} {tag_name}: {release_name}</b>\n\n"
        f"<b>✨ Что нового:</b>\n"
        f"{highlights_html}\n\n"
        f"<b>📦 Ссылки для скачивания:</b>\n"
        f"💻 <a href=\"{win_download}\">Windows (Установщик .EXE)</a>\n"
        f"📱 <a href=\"{apk_download}\">Android & Smart TV (Пакет .APK)</a>\n\n"
        f"<i>Приложение также умеет обновляться автоматически прямо при запуске!</i>\n\n"
        f"#patchnote #update #{app_name.lower()}"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📱 Скачать APK для Android", "url": apk_download},
                {"text": "💻 Скачать для Windows", "url": win_download}
            ],
            [
                {"text": "🐙 Релиз на GitHub", "url": html_url or f"https://github.com/{repo}/releases"}
            ]
        ]
    }

    if dry_run:
        print("\n[DRY-RUN] Предпросмотр поста:")
        print(text)
        return True

    res = sender.send_message(text, reply_markup=reply_markup, disable_preview=True)
    if res.get('ok'):
        print(f"✅ Патчноут релиза {tag_name} успешно опубликован в Telegram-канал!")
        return True
    else:
        print(f"❌ Ошибка публикации: {res.get('description')}")
        return False

def publish_custom_patchnote(version, title, highlights, fixes=None, dry_run=False):
    config = load_config()
    sender = TelegramSender()
    app_name = config.get('app', {}).get('name', 'AnimeVist')
    repo = config.get('app', {}).get('github_repo', 'magver/AnimeVist-Releases')
    
    clean_ver = version.replace('v', '')
    tag_ver = f"v{clean_ver}"
    
    release_url = f"https://github.com/{repo}/releases/tag/{tag_ver}"
    win_download = f"https://github.com/{repo}/releases/download/{tag_ver}/{app_name}-Setup-{clean_ver}.exe"
    apk_download = f"https://github.com/{repo}/releases/download/{tag_ver}/{app_name}-{clean_ver}.apk"

    highlights_html = "\n".join([f"• {h}" for h in highlights])
    fixes_html = ""
    if fixes and len(fixes) > 0:
        fixes_html = "\n\n<b>🐛 Исправления и стабильность:</b>\n" + "\n".join([f"• {f}" for f in fixes])

    text = (
        f"🚀 <b>Обновление {app_name} {tag_ver}: {title}</b>\n\n"
        f"<b>✨ Что нового:</b>\n"
        f"{highlights_html}"
        f"{fixes_html}\n\n"
        f"<b>📦 Ссылки для скачивания:</b>\n"
        f"💻 <a href=\"{win_download}\">Windows (Установщик .EXE)</a>\n"
        f"📱 <a href=\"{apk_download}\">Android & Smart TV (Пакет .APK)</a>\n\n"
        f"<i>Приложение также умеет обновляться автоматически прямо при запуске!</i>\n\n"
        f"#patchnote #update #{app_name.lower()}"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📱 Скачать APK для Android", "url": apk_download},
                {"text": "💻 Скачать для Windows", "url": win_download}
            ],
            [
                {"text": "🐙 Релиз на GitHub", "url": release_url}
            ]
        ]
    }

    if dry_run:
        print("[DRY-RUN] Preview:")
        print(text)
        return True

    res = sender.send_message(text, reply_markup=reply_markup, disable_preview=True)
    if res.get('ok'):
        print(f"✅ Патчноут {tag_ver} успешно опубликован в Telegram!")
        return True
    else:
        print(f"❌ Ошибка публикации: {res.get('description')}")
        return False

if __name__ == '__main__':
    publish_patchnote_from_github(dry_run=True)

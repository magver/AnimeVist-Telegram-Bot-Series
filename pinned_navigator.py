"""
Standalone AnimeVist Pinned Message & Navigator Publisher.
Fetches latest release info from GitHub and broadcasts the master pinned
navigation post to your Telegram channel, automatically pinning or editing it.
"""

import os
import sys
import json
import urllib.request

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram_sender import TelegramSender, load_config, save_config

def get_latest_version_from_github():
    config = load_config()
    repo = config.get('app', {}).get('github_repo', 'magver/AnimeVist-Releases')
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'AnimeVistBot/1.0',
        'Accept': 'application/vnd.github.v3+json'
    })
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            tag = data.get('tag_name')
            if tag:
                return tag.replace('v', '')
    except Exception:
        pass
    return "1.0.30"

def publish_pinned_navigator(dry_run=False, update_existing=True):
    config = load_config()
    sender = TelegramSender()
    app_name = config.get('app', {}).get('name', 'AnimeVist')
    repo = config.get('app', {}).get('github_repo', 'magver/AnimeVist-Releases')
    version = get_latest_version_from_github()
    existing_msg_id = config.get('telegram', {}).get('pinned_message_id')
    chat_url = config.get('app', {}).get('chat_invite_url', 'https://t.me/animevist_chat')
    
    release_url = f"https://github.com/{repo}/releases/latest"
    win_download = f"https://github.com/{repo}/releases/download/v{version}/{app_name}-Setup-{version}.exe"
    apk_download = f"https://github.com/{repo}/releases/download/v{version}/{app_name}-{version}.apk"

    text = (
        f"📌 <b>ДОБРО ПОЖАЛОВАТЬ В {app_name.upper()}!</b>\n\n"
        f"<b>{app_name}</b> — это кроссплатформенное приложение нового поколения для ПК (Windows) и Android (смартфоны, планшеты, Smart TV) "
        f"для комфортного просмотра аниме в высоком качестве <b>1080p Full HD</b> без рекламы.\n\n"
        f"🌟 <b>ГЛАВНЫЕ ВОЗМОЖНОСТИ:</b>\n"
        f"• 🔄 <b>Сквозной просмотр:</b> начали серию на ПК — продолжили с той же секунды на телефоне или Android TV.\n"
        f"• 🎙 <b>Все озвучки в одном месте:</b> AnimeVost (прямой быстрый поток), AniLibria, Studio Band, субтитры.\n"
        f"• ⏩ <b>Умный плеер:</b> автопропуск опенингов (+85с) и бесшовный переход к следующей серии.\n"
        f"• 📥 <b>Офлайн-режим:</b> скачивайте серии в память устройства и смотрите без интернета.\n"
        f"• 🎨 <b>Кастомизация:</b> палитра тем (Cyber Dark, OLED Pure Black, Sakura Pink) и 16 векторных аватаров.\n\n"
        f"⬇️ <b>СКАЧАТЬ АКТУАЛЬНУЮ ВЕРСИЮ (v{version}):</b>\n"
        f"💻 <a href=\"{win_download}\">Для Windows (.EXE Установщик)</a>\n"
        f"📱 <a href=\"{apk_download}\">Для Android и Android TV (.APK Пакет)</a>\n\n"
        f"❓ <b>НАВИГАЦИЯ ПО КАНАЛУ:</b>\n"
        f"• <code>#release</code> — анонсы выхода новых серий\n"
        f"• <code>#patchnote</code> — обновления и чейнджлоги\n"
        f"• <code>#news</code> — главные новости мира аниме\n"
        f"• <code>#poll</code> — голосования за новые функции\n\n"
        f"💬 Наш чат комьюнити: {chat_url}\n"
        f"🤖 Баг-репортер: прямо внутри приложения или через бота"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "📱 Скачать APK (Android / TV)", "url": apk_download},
                {"text": "💻 Скачать для Windows", "url": win_download}
            ],
            [
                {"text": "🐙 Все релизы на GitHub", "url": release_url}
            ]
        ]
    }

    if dry_run:
        print("[DRY-RUN] Pinned message preview:")
        print(text)
        return True

    # If updating already pinned message
    if update_existing and existing_msg_id:
        print(f"[Pinned] Обновление существующего закрепленного сообщения ID {existing_msg_id}...")
        edit_res = sender.edit_message_text(existing_msg_id, text, reply_markup=reply_markup, disable_preview=True)
        if edit_res.get('ok'):
            print("✅ Существующий закрепленный пост успешно обновлен!")
            return True
        else:
            print(f"⚠️ Не удалось отредактировать ({edit_res.get('description')}). Публикуем новый...")

    # Fresh send and pin
    res = sender.send_message(text, reply_markup=reply_markup, disable_preview=True)
    if res.get('ok'):
        msg_id = res['result']['message_id']
        print(f"✅ Сообщение отправлено (ID: {msg_id}). Закрепляем в канале...")
        pin_res = sender.pin_chat_message(msg_id)
        if pin_res.get('ok'):
            print("📌 Сообщение успешно закреплено в шапке канала!")
        else:
            print(f"⚠️ Пост отправлен, но закрепить не удалось: {pin_res.get('description')} (Выдайте боту право 'Pin Messages')")
        
        config['telegram']['pinned_message_id'] = msg_id
        save_config(config)
        return True
    else:
        print(f"❌ Ошибка отправки: {res.get('description')}")
        return False

if __name__ == '__main__':
    publish_pinned_navigator(dry_run=True)

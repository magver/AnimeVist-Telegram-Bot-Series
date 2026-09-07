"""
WSGI Application entry point for PythonAnywhere, Gunicorn, and uWSGI.
Allows running the AnimeVist Web Dashboard as a hosted WSGI service.
"""

import os
import sys
import json
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from telegram_sender import TelegramSender, load_config, save_config
from web_dashboard import HTML_PAGE, log_event, activity_logs, last_check_time, get_channel_auto_detect
from series_announcer import run_series_check
from news_announcer import run_news_check
from patchnote_publisher import publish_patchnote_from_github
from pinned_navigator import publish_pinned_navigator

def application(environ, start_response):
    path = environ.get('PATH_INFO', '/')
    method = environ.get('REQUEST_METHOD', 'GET')
    
    if method == 'GET':
        if path == '/' or path == '/index.html':
            start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
            return [HTML_PAGE.encode('utf-8')]
            
        elif path == '/api/status':
            sender = TelegramSender()
            me = sender.get_me()
            config = load_config()
            resp = {
                "bot": me.get('result') if me.get('ok') else None,
                "config": config,
                "last_check": last_check_time,
                "logs": activity_logs
            }
            start_response('200 OK', [('Content-Type', 'application/json; charset=utf-8'), ('Access-Control-Allow-Origin', '*')])
            return [json.dumps(resp, ensure_ascii=False).encode('utf-8')]
            
        elif path == '/api/logs':
            start_response('200 OK', [('Content-Type', 'application/json; charset=utf-8'), ('Access-Control-Allow-Origin', '*')])
            return [json.dumps(activity_logs, ensure_ascii=False).encode('utf-8')]
            
        else:
            start_response('404 Not Found', [('Content-Type', 'text/plain; charset=utf-8')])
            return [b'Not Found']
            
    elif method == 'POST':
        try:
            content_length = int(environ.get('CONTENT_LENGTH', 0))
        except (ValueError, TypeError):
            content_length = 0
            
        body = environ['wsgi.input'].read(content_length).decode('utf-8') if content_length > 0 else '{}'
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}
            
        if path == '/api/save-config':
            config = load_config()
            config.setdefault('telegram', {})['bot_token'] = data.get('bot_token', config.get('telegram', {}).get('bot_token'))
            config.setdefault('telegram', {})['channel_id'] = data.get('channel_id', config.get('telegram', {}).get('channel_id'))
            config.setdefault('app', {})['chat_invite_url'] = data.get('chat_invite_url', config.get('app', {}).get('chat_invite_url'))
            config.setdefault('announcer', {})['check_interval_seconds'] = data.get('interval', 300)
            config.setdefault('announcer', {})['enable_series_releases'] = data.get('enable_releases', True)
            config.setdefault('announcer', {})['enable_anime_news'] = data.get('enable_news', True)
            save_config(config)
            log_event("Настройки сохранены через веб-интерфейс", "success")
            start_response('200 OK', [('Content-Type', 'application/json; charset=utf-8'), ('Access-Control-Allow-Origin', '*')])
            return [b'{"ok": true}']
            
        elif path == '/api/test-message':
            config = load_config()
            sender = TelegramSender()
            channel = config.get('telegram', {}).get('channel_id')
            res = sender.send_message(
                "🤖 <b>AnimeVist — Тест подключения!</b>\n\nВеб-интерфейс на PythonAnywhere успешно подключен к каналу.",
                chat_id=channel
            )
            if res.get('ok'):
                log_event("Тестовое сообщение успешно отправлено", "success")
            else:
                log_event(f"Ошибка теста: {res.get('description')}", "error")
            start_response('200 OK', [('Content-Type', 'application/json; charset=utf-8'), ('Access-Control-Allow-Origin', '*')])
            return [json.dumps(res, ensure_ascii=False).encode('utf-8')]
            
        elif path == '/api/auto-detect-channel':
            res = get_channel_auto_detect()
            if res.get('ok'):
                config = load_config()
                config.setdefault('telegram', {})['channel_id'] = str(res['chat_id'])
                save_config(config)
                log_event(f"Канал обнаружен автоматически: {res.get('title')}", "success")
            start_response('200 OK', [('Content-Type', 'application/json; charset=utf-8'), ('Access-Control-Allow-Origin', '*')])
            return [json.dumps(res, ensure_ascii=False).encode('utf-8')]
            
        elif path == '/api/action':
            act = data.get('action')
            def run_bg(action_name):
                try:
                    if action_name == 'releases':
                        log_event("Запуск проверки серий...")
                        cnt = run_series_check()
                        log_event(f"Проверка серий завершена. Опубликовано: {cnt}", "success")
                    elif action_name == 'news':
                        log_event("Запуск проверки новостей...")
                        cnt = run_news_check()
                        log_event(f"Проверка новостей завершена. Опубликовано: {cnt}", "success")
                    elif action_name == 'patchnote':
                        log_event("Публикация патчноута из GitHub...")
                        res = publish_patchnote_from_github()
                        log_event("Патчноут опубликован", "success" if res else "error")
                    elif action_name == 'pinned':
                        log_event("Закрепление навигатора...")
                        res = publish_pinned_navigator()
                        log_event("Навигатор закреплен", "success" if res else "error")
                except Exception as e:
                    log_event(f"Ошибка: {e}", "error")
                    
            threading.Thread(target=run_bg, args=(act,), daemon=True).start()
            start_response('200 OK', [('Content-Type', 'application/json; charset=utf-8'), ('Access-Control-Allow-Origin', '*')])
            return [b'{"ok": true}']

    start_response('404 Not Found', [('Content-Type', 'text/plain; charset=utf-8')])
    return [b'Not Found']

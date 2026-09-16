"""
AnimeVist Professional Web Dashboard & 24/7 Automation Hub.
Serves modern responsive dashboard (PC & Mobile) and provides DevOps REST APIs
for controlling the Telegram Bot, broadcasting to channel, and cloud sync.
"""

import os
import sys
import json
import time
import threading
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram_sender import (
    TelegramSender,
    load_config,
    save_config,
    sync_config_to_cloud,
    sync_config_to_supabase,
    fetch_config_from_supabase,
    fetch_config_from_cloud,
    test_supabase_connection,
    test_turso_connection
)
from series_announcer import run_series_check, get_recent_releases_for_preview, publish_single_custom_episode
from news_announcer import run_news_check, collect_multi_source_news, publish_single_custom_news, get_recent_news_for_preview
from compilations_announcer import run_compilation_post, list_available_themes, load_last_compilation_time, get_compilation_preview
from patchnote_publisher import publish_patchnote_from_github, get_patchnote_preview
from pinned_navigator import publish_pinned_navigator, get_pinned_navigator_preview, publish_custom_pinned_navigator
from user_auth import get_bot_users_summary
from personal_notifier import run_notification_cycle

INDEX_HTML_PATH = os.path.join(os.path.dirname(__file__), 'index.html')

# Global runtime state
activity_logs = []
daemon_thread = None
daemon_running = True
daemon_paused = False
last_check_time = None
last_compilation_time = load_last_compilation_time()
last_personal_check_time = 0
server_start_time = time.time()
cached_bot_info = None
cached_chat_info = None
cached_member_count = None
last_bot_fetch_time = 0

def log_event(message, level="info"):
    timestamp = time.strftime('%H:%M:%S')
    entry = {"time": timestamp, "message": str(message), "level": level}
    activity_logs.append(entry)
    if len(activity_logs) > 250:
        activity_logs.pop(0)
    print(f"[{timestamp}] [{level.upper()}] {message}")

def background_monitoring_worker():
    global last_check_time, last_compilation_time, last_personal_check_time, daemon_running, daemon_paused
    log_event("Служба автономного мониторинга 24/7 инициализирована", "success")

    while daemon_running:
        try:
            if not daemon_paused:
                config = load_config()
                ann_conf = config.get('announcer', {})

                # 1. Check Series Releases
                if ann_conf.get('enable_series_releases', True):
                    cnt = run_series_check()
                    if cnt > 0:
                        log_event(f"Опубликовано новых серий в канал: {cnt}", "success")

                # 2. Check Anime News
                if ann_conf.get('enable_anime_news', True):
                    cnt_n = run_news_check()
                    if cnt_n > 0:
                        log_event(f"Опубликовано аниме-новостей: {cnt_n}", "success")

                # 3. Check Compilations
                if ann_conf.get('enable_compilations', True):
                    comp_hours = float(ann_conf.get('compilations_interval_hours', 6))
                    if last_compilation_time == 0:
                        last_compilation_time = load_last_compilation_time()
                    if time.time() - last_compilation_time >= comp_hours * 3600:
                        log_event("Авто-цикл: публикация плановой Топ-подборки аниме...")
                        res_c = run_compilation_post()
                        if res_c.get('ok'):
                            log_event(f"Опубликована подборка: {res_c.get('theme')}", "success")
                        last_compilation_time = time.time()

                # 4. Check Personal Notifications (configurable interval, default 60 mins)
                if ann_conf.get('enable_personal_notifications', True):
                    p_interval_min = float(ann_conf.get('personal_interval_minutes', 60))
                    p_interval_sec = max(60, p_interval_min * 60)
                    if time.time() - last_personal_check_time >= p_interval_sec:
                        p_res = run_notification_cycle(dry_run=False)
                        sent_cnt = p_res.get('stats', {}).get('sent', 0)
                        if sent_cnt > 0:
                            log_event(f"Отправлено персональных уведомлений в ЛС: {sent_cnt}", "success")
                        last_personal_check_time = time.time()

                last_check_time = time.strftime('%d.%m.%Y %H:%M:%S')
        except Exception as e:
            log_event(f"Исключение в цикле мониторинга: {e}", "error")

        config = load_config()
        sleep_total = config.get('announcer', {}).get('check_interval_seconds', 300)
        for _ in range(max(10, int(sleep_total))):
            if not daemon_running:
                break
            time.sleep(1)

def get_channel_auto_detect():
    config = load_config()
    token = config.get('telegram', {}).get('bot_token')
    if not token:
        return {"ok": False, "error": "Токен бота не указан в настройках"}

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'AnimeVistBot/2.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = data.get('result', [])
            for u in reversed(results):
                if 'channel_post' in u:
                    chat = u['channel_post'].get('chat', {})
                    return {
                        "ok": True,
                        "chat_id": chat.get('id'),
                        "title": chat.get('title'),
                        "username": chat.get('username')
                    }
                if 'my_chat_member' in u:
                    chat = u['my_chat_member'].get('chat', {})
                    if chat.get('type') == 'channel':
                        return {
                            "ok": True,
                            "chat_id": chat.get('id'),
                            "title": chat.get('title'),
                            "username": chat.get('username')
                        }
            return {
                "ok": False,
                "error": "В обновлениях бота пока нет сообщений из канала. Опубликуйте любое сообщение в канал и повторите поиск."
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if os.path.exists(INDEX_HTML_PATH):
                with open(INDEX_HTML_PATH, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"<h1>AnimeVist Dashboard</h1><p>index.html not found</p>")

        elif path == "/open.html":
            open_html_p = os.path.join(os.path.dirname(__file__), 'open.html')
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if os.path.exists(open_html_p):
                with open(open_html_p, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"<h1>AnimeVist</h1><p>open.html not found</p>")

        elif path == "/api/status":
            global cached_bot_info, cached_chat_info, cached_member_count, last_bot_fetch_time
            now = time.time()
            if (now - last_bot_fetch_time > 45) or (cached_bot_info is None):
                try:
                    sender = TelegramSender()
                    me = sender.get_me()
                    if me.get('ok'):
                        cached_bot_info = me.get('result')
                        chat_info = sender.get_chat()
                        cached_chat_info = chat_info.get('result') if chat_info.get('ok') else None
                        member_count_res = sender.get_chat_member_count()
                        cached_member_count = member_count_res.get('result') if member_count_res.get('ok') else None
                        last_bot_fetch_time = now
                    else:
                        cached_bot_info = None
                except Exception as e:
                    print(f"[Status] Error fetching Telegram info: {e}")

            config = load_config()
            uptime_min = int((time.time() - server_start_time) / 60)

            episodes_count = 0
            news_count = 0
            compilations_count = 0
            try:
                if os.path.exists('seen_episodes.json'):
                    episodes_count = len(json.load(open('seen_episodes.json', 'r', encoding='utf-8')))
                if os.path.exists('seen_news.json'):
                    news_count = len(json.load(open('seen_news.json', 'r', encoding='utf-8')))
                if os.path.exists('seen_compilation_animes.json'):
                    compilations_count = len(json.load(open('seen_compilation_animes.json', 'r', encoding='utf-8')))
            except Exception:
                pass

            # Bot users stats from Supabase
            bot_summary = {"total_users": 0, "active_subscriptions": 0}
            try:
                bot_summary = get_bot_users_summary()
            except Exception:
                pass

            last_comp = load_last_compilation_time()
            comp_hours = float(config.get('announcer', {}).get('compilations_interval_hours', 6))
            is_comp_enabled = config.get('announcer', {}).get('enable_compilations', True)
            if is_comp_enabled:
                next_comp_sec = max(0, int((last_comp + comp_hours * 3600) - time.time())) if last_comp > 0 else 0
            else:
                next_comp_sec = None

            resp = {
                "bot": cached_bot_info,
                "chat": cached_chat_info,
                "member_count": cached_member_count,
                "stats": {
                    "episodes": episodes_count,
                    "news": news_count,
                    "compilations": compilations_count,
                    "bot_users": bot_summary.get('total_users', 0),
                    "bot_subscriptions": bot_summary.get('active_subscriptions', 0)
                },
                "next_compilation_sec": next_comp_sec,
                "config": config,
                "last_check": last_check_time,
                "daemon_running": daemon_running,
                "daemon_paused": daemon_paused,
                "uptime_minutes": uptime_min,
                "logs": activity_logs
            }
            self._send_json(resp)

        elif path == "/api/logs":
            self._send_json(activity_logs)

        elif path == "/api/compilations-themes":
            self._send_json(list_available_themes())

        elif path == "/api/compilation-preview":
            query_components = urllib.parse.parse_qs(parsed.query)
            genre_arg = query_components.get('genre', ['must_watch'])[0]
            count_arg = int(query_components.get('count', [4])[0])
            refresh_arg = query_components.get('refresh', ['1'])[0] in ['1', 'true', 'yes']
            gen_collage = query_components.get('generate_collage', ['1'])[0] in ['1', 'true', 'yes']
            prev = get_compilation_preview(genre_arg, count=count_arg, refresh=refresh_arg, generate_collage=gen_collage)
            self._send_json(prev)

        elif path == "/api/module-data":
            query_components = urllib.parse.parse_qs(parsed.query)
            mod = query_components.get('module', [''])[0]
            if mod == 'releases':
                include_seen = query_components.get('include_seen', ['0'])[0] in ['1', 'true', 'yes']
                self._send_json(get_recent_releases_for_preview(count=15, only_unseen=(not include_seen)))
            elif mod == 'news':
                try:
                    include_seen = query_components.get('include_seen', ['0'])[0] in ['1', 'true', 'yes']
                    self._send_json(get_recent_news_for_preview(count=15, only_unseen=(not include_seen)))
                except Exception as e:
                    self._send_json({"error": str(e)})
            elif mod == 'compilation':
                self._send_json({
                    "themes": list_available_themes(),
                    "last_compilation_time": load_last_compilation_time()
                })
            elif mod == 'personal':
                self._send_json(get_bot_users_summary())
            elif mod == 'patchnote':
                self._send_json(get_patchnote_preview())
            elif mod == 'pinned':
                self._send_json(get_pinned_navigator_preview())
            else:
                self._send_json({"error": "unknown module"})

        elif path.startswith("/assets/"):
            rel_p = path.lstrip("/").replace('\\', '/')
            full_p = os.path.join(os.path.dirname(__file__), rel_p)
            if os.path.exists(full_p) and os.path.isfile(full_p):
                ctype = "application/octet-stream"
                if full_p.endswith('.png'): ctype = "image/png"
                elif full_p.endswith('.jpg') or full_p.endswith('.jpeg'): ctype = "image/jpeg"
                elif full_p.endswith('.ttf'): ctype = "font/ttf"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                with open(full_p, 'rb') as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_response(404)
                self.end_headers()
                return

        elif path.startswith("/scratch/"):
            rel_p = path.lstrip("/").replace('\\', '/')
            full_p = os.path.join(os.path.dirname(__file__), rel_p)
            if os.path.exists(full_p) and os.path.isfile(full_p):
                ctype = "image/jpeg" if (full_p.endswith('.jpg') or full_p.endswith('.jpeg')) else "image/png"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                with open(full_p, 'rb') as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_response(404)
                self.end_headers()
                return

        else:
            self.send_response(404)
            self.end_headers()


    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else '{}'
        try:
            data = json.loads(body) if body else {}
        except Exception:
            data = {}

        if path == "/api/save-config":
            config = load_config()
            tg = config.setdefault('telegram', {})
            app = config.setdefault('app', {})
            ann = config.setdefault('announcer', {})
            cloud = config.setdefault('cloud_storage', {})

            if 'bot_token' in data: tg['bot_token'] = data['bot_token']
            if 'channel_id' in data: tg['channel_id'] = data['channel_id']
            if 'discussion_chat_id' in data: tg['discussion_chat_id'] = data['discussion_chat_id']
            if 'admin_id' in data: tg['admin_id'] = data['admin_id']

            if 'supabase_url' in data: cloud['supabase_url'] = data['supabase_url']
            if 'supabase_key' in data: cloud['supabase_key'] = data['supabase_key']
            if 'turso_url' in data: cloud['turso_url'] = data['turso_url']
            if 'turso_token' in data: cloud['turso_token'] = data['turso_token']
            if 'cloudflare_worker_url' in data:
                cloud['cloudflare_worker_url'] = data['cloudflare_worker_url']
                cloud['api_url'] = data['cloudflare_worker_url']
            if 'provider' in data: cloud['provider'] = data['provider']

            if 'app_name' in data: app['name'] = data['app_name']
            if 'github_repo' in data: app['github_repo'] = data['github_repo']
            if 'chat_invite_url' in data: app['chat_invite_url'] = data['chat_invite_url']

            if 'enable_releases' in data: ann['enable_series_releases'] = bool(data['enable_releases'])
            if 'enable_news' in data: ann['enable_anime_news'] = bool(data['enable_news'])
            if 'enable_compilations' in data: ann['enable_compilations'] = bool(data['enable_compilations'])
            if 'compilations_interval_hours' in data: ann['compilations_interval_hours'] = max(1.0, float(data['compilations_interval_hours']))
            if 'enable_personal' in data: ann['enable_personal_notifications'] = bool(data['enable_personal'])

            save_config(config, sync_to_cloud=True)
            log_event("Настройки успешно обновлены и синхронизированы в облако", "success")
            self._send_json({"ok": True, "config": config})

        elif path == "/api/test-message":
            config = load_config()
            sender = TelegramSender()
            channel = config.get('telegram', {}).get('channel_id')
            res = sender.send_message(
                "🤖 <b>AnimeVist — Тест Подключения!</b>\n\nПанель управления успешно подключена к каналу вещания.",
                chat_id=channel
            )
            if res.get('ok'):
                log_event("Тестовое сообщение успешно отправлено в целевой канал", "success")
            else:
                log_event(f"Ошибка отправки тестового сообщения: {res.get('description')}", "error")
            self._send_json(res)

        elif path == "/api/custom-post":
            config = load_config()
            sender = TelegramSender()
            channel = config.get('telegram', {}).get('channel_id')

            text = data.get('text', '').strip()
            photo_url = data.get('photo_url', '').strip()
            btn_text = data.get('btn_text', '').strip()
            btn_url = data.get('btn_url', '').strip()

            if not text:
                self._send_json({"ok": False, "error": "Текст сообщения не может быть пустым"})
                return

            reply_markup = None
            if btn_text and btn_url and btn_url.startswith('http'):
                reply_markup = {
                    "inline_keyboard": [
                        [{"text": btn_text, "url": btn_url}]
                    ]
                }

            if photo_url and photo_url.startswith('http'):
                res = sender.send_photo(photo_url, caption=text, chat_id=channel, reply_markup=reply_markup)
            else:
                res = sender.send_message(text, chat_id=channel, reply_markup=reply_markup)

            if res.get('ok'):
                log_event("Кастомный пост успешно опубликован в канале", "success")
                self._send_json({"ok": True})
            else:
                desc = res.get('description', 'Ошибка отправки')
                log_event(f"Ошибка отправки кастомного поста: {desc}", "error")
                self._send_json({"ok": False, "error": desc})

        elif path == "/api/auto-detect-channel":
            res = get_channel_auto_detect()
            if res.get('ok'):
                config = load_config()
                config.setdefault('telegram', {})['channel_id'] = str(res['chat_id'])
                save_config(config)
                log_event(f"Канал обнаружен автоматически: {res.get('title')} ({res.get('chat_id')})", "success")
            self._send_json(res)

        elif path == "/api/cloud-sync":
            config = load_config()
            res = sync_config_to_cloud(config)
            prov = (config.get('cloud_storage', {}).get('provider') or 'cloud').upper()
            if res.get('ok'):
                log_event(f"Конфигурация успешно синхронизирована в {prov}", "success")
            else:
                log_event(f"Ошибка облачной синхронизации: {res.get('error')}", "error")
            self._send_json(res)

        elif path == "/api/cloud-fetch":
            config = load_config()
            res = fetch_config_from_cloud(config)
            if res.get('ok'):
                log_event("Настройки успешно восстановлены из облака", "success")
            else:
                log_event(f"Ошибка восстановления: {res.get('error')}", "error")
            self._send_json(res)

        elif path == "/api/test-turso":
            config = load_config()
            res = test_turso_connection(config)
            self._send_json(res)

        elif path == "/api/test-supabase":
            config = load_config()
            res = test_supabase_connection(config)
            self._send_json(res)

        elif path == "/api/toggle-daemon":
            global daemon_paused
            daemon_paused = not daemon_paused
            state_str = "приостановлен" if daemon_paused else "возобновлен"
            log_event(f"Фоновый демон автопостинга {state_str} оператором", "info")
            self._send_json({"ok": True, "paused": daemon_paused})

        elif path == "/api/action":
            act = data.get('action')
            genre = data.get('genre')
            count = int(data.get('count', 4))

            def run_bg(action_name, genre_param, count_param):
                try:
                    if action_name == 'releases':
                        log_event("Ручной запуск сканирования новых серий...")
                        cnt = run_series_check()
                        log_event(f"Сканирование серий завершено. Опубликовано: {cnt}", "success")
                    elif action_name == 'news':
                        log_event("Ручной запуск сбора аниме-новостей...")
                        cnt = run_news_check()
                        log_event(f"Сбор новостей завершен. Опубликовано: {cnt}", "success")
                    elif action_name == 'compilation':
                        log_event(f"Ручной запуск публикации подборки ({genre_param or 'авто'}, {count_param} аниме)...")
                        res_c = run_compilation_post(genre_key=genre_param, count=count_param)
                        if res_c.get('ok'):
                            log_event(f"Подборка успешно опубликована: {res_c.get('theme')}", "success")
                        else:
                            log_event(f"Ошибка публикации подборки: {res_c.get('error')}", "error")
                    elif action_name == 'patchnote':
                        log_event("Публикация свежего патчноута из GitHub Releases...")
                        res = publish_patchnote_from_github()
                        log_event("Публикация патчноута завершена", "success" if res else "error")
                    elif action_name == 'pinned':
                        log_event("Отправка и закрепление навигационного поста...")
                        res = publish_pinned_navigator()
                        log_event("Закрепление навигатора завершено", "success" if res else "error")
                    elif action_name == 'personal_check':
                        log_event("Ручной запуск проверки новых серий для подписчиков бота в ЛС...")
                        p_res = run_notification_cycle(dry_run=False)
                        sent_cnt = p_res.get('stats', {}).get('sent', 0)
                        log_event(f"Цикл ЛС завершен. Отправлено уведомлений: {sent_cnt}", "success")
                except Exception as e:
                    log_event(f"Ошибка выполнения действия [{action_name}]: {e}", "error")

            threading.Thread(target=run_bg, args=(act, genre, count), daemon=True).start()
            self._send_json({"ok": True})

        elif path == "/api/save-module-schedule":
            mod = data.get('module')
            config = load_config()
            ann = config.setdefault('announcer', {})

            if mod == 'releases':
                if 'enabled' in data: ann['enable_series_releases'] = bool(data['enabled'])
                if 'interval_minutes' in data: ann['check_interval_seconds'] = max(60, int(data['interval_minutes']) * 60)
                if 'interval_sec' in data: ann['check_interval_seconds'] = max(60, int(data['interval_sec']))
                if 'max_releases' in data: ann['max_releases_per_cycle'] = int(data['max_releases'])
                if 'include_hashtags' in data: ann['include_genre_hashtags'] = bool(data['include_hashtags'])
                if 'show_chat' in data: ann['show_chat_button'] = bool(data['show_chat'])
            elif mod == 'news':
                if 'enabled' in data: ann['enable_anime_news'] = bool(data['enabled'])
            elif mod == 'compilation':
                if 'enabled' in data: ann['enable_compilations'] = bool(data['enabled'])
                if 'interval_hours' in data: ann['compilations_interval_hours'] = max(1.0, float(data['interval_hours']))
            elif mod == 'personal':
                if 'enabled' in data: ann['enable_personal_notifications'] = bool(data['enabled'])
                if 'interval_minutes' in data: ann['personal_interval_minutes'] = max(5, int(data['interval_minutes']))
                if 'cooldown_hours' in data: ann['personal_user_cooldown_hours'] = max(0.0, float(data['cooldown_hours']))
                if 'max_per_user' in data: ann['personal_max_episodes_per_user'] = max(1, int(data['max_per_user']))
                if 'batch_digest' in data: ann['personal_batch_digest'] = bool(data['batch_digest'])
                if 'quiet_hours_enabled' in data: ann['personal_quiet_hours_enabled'] = bool(data['quiet_hours_enabled'])
                if 'quiet_start' in data: ann['personal_quiet_hours_start'] = int(data['quiet_start'])
                if 'quiet_end' in data: ann['personal_quiet_hours_end'] = int(data['quiet_end'])
                if 'quiet_mode' in data: ann['personal_quiet_action'] = str(data['quiet_mode'])
                if 'silent_all' in data: ann['personal_silent_notifications'] = bool(data['silent_all'])
                if 'strict_matching' in data: ann['personal_strict_matching'] = bool(data['strict_matching'])

            save_config(config, sync_to_cloud=True)
            log_event(f"Расписание модуля [{mod}] обновлено и сохранено в Supabase", "success")
            self._send_json({"ok": True, "config": config})

        elif path == "/api/publish-custom-module-post":
            mod = data.get('module')
            caption = data.get('caption', '').strip()
            poster_url = data.get('poster_url', '').strip()
            vost_id = data.get('vost_id')
            ep_num = data.get('ep_num')

            reply_markup = None
            btn_text = data.get('btn_text', '').strip()
            btn_url = data.get('btn_url', '').strip()
            if btn_text and btn_url and btn_url.startswith('http'):
                reply_markup = {"inline_keyboard": [[{"text": btn_text, "url": btn_url}]]}

            config = load_config()
            sender = TelegramSender()
            channel = config.get('telegram', {}).get('channel_id')

            if mod == 'releases':
                title_ru = data.get('title_ru')
                total_ep = data.get('total_ep')
                rating = data.get('rating')
                res = publish_single_custom_episode(
                    vost_id or '0',
                    ep_num or '1',
                    caption,
                    poster_url=poster_url,
                    reply_markup=reply_markup,
                    title_ru=title_ru,
                    total_ep=total_ep,
                    rating=rating
                )
                log_event(f"Ручная публикация серии {ep_num} в канал", "success" if res.get('ok') else "error")
                self._send_json(res)
            elif mod == 'news':
                news_id = data.get('news_id')
                title = data.get('title')
                source = data.get('source')
                res = publish_single_custom_news(
                    news_id,
                    caption,
                    poster_url=poster_url,
                    reply_markup=reply_markup,
                    title=title,
                    source=source
                )
                log_event("Ручная публикация новости в канал", "success" if res.get('ok') else "error")
                self._send_json(res)
            elif mod == 'pinned':
                res = publish_custom_pinned_navigator(caption, custom_reply_markup=reply_markup)
                log_event("Ручное обновление и закрепление Навигатора", "success" if res.get('ok') else "error")
                self._send_json(res)
            elif mod == 'patchnote':
                if poster_url and poster_url.startswith('http'):
                    res = sender.send_photo(poster_url, caption=caption, chat_id=channel, reply_markup=reply_markup)
                else:
                    res = sender.send_message(caption, chat_id=channel, reply_markup=reply_markup, disable_preview=True)
                log_event("Ручная публикация патчноута релиза", "success" if res.get('ok') else "error")
            elif mod == 'compilation':
                local_collage = os.path.join(os.path.dirname(__file__), 'scratch', 'compilation_collage.jpg')
                photo_target = poster_url
                if not photo_target or photo_target.startswith('/scratch/') or not photo_target.startswith('http'):
                    if os.path.exists(local_collage):
                        photo_target = local_collage
                if photo_target:
                    res = sender.send_photo(photo_target, caption=caption, chat_id=channel, reply_markup=reply_markup)
                else:
                    res = sender.send_message(caption, chat_id=channel, reply_markup=reply_markup)
                if res.get('ok'):
                    log_event("Ручная публикация Топ-подборки аниме в канал", "success")
                    from compilations_announcer import save_last_compilation_time
                    save_last_compilation_time()
                else:
                    desc = res.get('description', 'Сбой')
                    log_event(f"Ошибка публикации подборки: {desc}", "error")
                self._send_json(res)
            else:
                if poster_url and poster_url.startswith('http'):
                    res = sender.send_photo(poster_url, caption=caption, chat_id=channel, reply_markup=reply_markup)
                else:
                    res = sender.send_message(caption, chat_id=channel, reply_markup=reply_markup)
                log_event(f"Ручная публикация поста модуля [{mod}]", "success" if res.get('ok') else "error")
                self._send_json(res)

        else:
            self.send_response(404)
            self.end_headers()

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        pass

def start_server(port=None):
    if port is None:
        env_port = os.environ.get("PORT")
        preferred_port = int(env_port) if env_port else 7860
        ports_to_try = [preferred_port, 5000, 7860, 5001, 8080]
    else:
        ports_to_try = [port]

    server = None
    actual_port = None
    for p in ports_to_try:
        try:
            server = ThreadingHTTPServer(("0.0.0.0", p), DashboardHandler)
            server.daemon_threads = True
            actual_port = p
            break
        except OSError:
            continue

    if server is None:
        server = ThreadingHTTPServer(("0.0.0.0", 0), DashboardHandler)
        server.daemon_threads = True
        actual_port = server.server_port

    print(f"\n================================================================")
    print(f"  🎬 ANIME VIST — ПАНЕЛЬ УПРАВЛЕНИЯ & БОТ ЗАПУЩЕНЫ 24/7")
    print(f"  🌐 Веб-интерфейс активен на порту: {actual_port}")
    print(f"================================================================\n")
    log_event(f"Веб-сервер активен на порту {actual_port}", "info")

    try:
        startup_conf = load_config()
        prov = startup_conf.get('cloud_storage', {}).get('provider', 'local')
        if prov != 'local':
            cloud_res = fetch_config_from_cloud(startup_conf)
            if cloud_res.get('ok'):
                log_event(f"Настройки успешно синхронизированы из облака ({prov.upper()}) при старте", "success")
    except Exception as e:
        print(f"[Startup] Cloud sync notice: {e}")

    global daemon_thread, last_compilation_time
    last_compilation_time = load_last_compilation_time()
    daemon_thread = threading.Thread(target=background_monitoring_worker, daemon=True)
    daemon_thread.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановка сервера...")
        server.server_close()

if __name__ == '__main__':
    start_server()
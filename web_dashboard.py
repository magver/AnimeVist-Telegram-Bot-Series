"""
AnimeVist Professional Web Dashboard & 24/7 Automation Hub.
DevOps Control Center for managing the AnimeVist Telegram Bot,
channel broadcasting, configuration sync, and background autonomous monitoring.
Includes manual posting studio (compilations, episodes, news, custom posts).
Zero external dependencies (pure Python standard library).
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
    sync_config_to_telegram,
    fetch_config_from_telegram,
    sync_config_to_supabase,
    fetch_config_from_supabase,
    test_supabase_connection
)
from series_announcer import run_series_check
from news_announcer import run_news_check
from compilations_announcer import run_compilation_post, list_available_themes, THEMES, load_last_compilation_time
from patchnote_publisher import publish_patchnote_from_github
from pinned_navigator import publish_pinned_navigator

# Global runtime state
activity_logs = []
daemon_thread = None
daemon_running = True
daemon_paused = False
last_check_time = None
last_compilation_time = 0
server_start_time = time.time()
cached_bot_info = None
cached_chat_info = None
cached_member_count = None
last_bot_fetch_time = 0

def log_event(message, level="info"):
    timestamp = time.strftime('%H:%M:%S')
    entry = {"time": timestamp, "message": str(message), "level": level}
    activity_logs.append(entry)
    if len(activity_logs) > 200:
        activity_logs.pop(0)
    print(f"[{timestamp}] [{level.upper()}] {message}")

def background_monitoring_worker():
    global last_check_time, last_compilation_time, daemon_running, daemon_paused
    log_event("Служба автономного мониторинга 24/7 инициализирована", "success")

    while daemon_running:
        try:
            if not daemon_paused:
                config = load_config()
                ann_conf = config.get('announcer', {})

                # 1. Check Series Releases
                if ann_conf.get('enable_series_releases', True):
                    log_event("Авто-цикл: сканирование релизов AnimeVost & Shikimori...")
                    cnt = run_series_check()
                    if cnt > 0:
                        log_event(f"Опубликовано новых серий в канал: {cnt}", "success")
                    else:
                        log_event("Свежих непубликовавшихся эпизодов не найдено", "info")

                # 2. Check Anime News
                if ann_conf.get('enable_anime_news', True):
                    log_event("Авто-цикл: проверка новостей (Shikimori, MAL, ANN)...")
                    cnt_n = run_news_check()
                    if cnt_n > 0:
                        log_event(f"Опубликовано аниме-новостей: {cnt_n}", "success")

                # 3. Check Compilations
                if ann_conf.get('enable_compilations', True):
                    comp_hours = float(ann_conf.get('compilations_interval_hours', 6))
                    if time.time() - last_compilation_time >= comp_hours * 3600:
                        log_event("Авто-цикл: публикация плановой Топ-подборки аниме...")
                        res_c = run_compilation_post()
                        if res_c.get('ok'):
                            log_event(f"Опубликована подборка: {res_c.get('theme')}", "success")
                        last_compilation_time = time.time()

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
        req = urllib.request.Request(url, headers={'User-Agent': 'AnimeVistBot/1.0'})
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

HTML_PAGE = """<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AnimeVist — Консоль Управления Ботом 24/7</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-base: #080c14;
      --bg-surface: rgba(15, 23, 42, 0.75);
      --bg-surface-elevated: rgba(30, 41, 59, 0.8);
      --bg-card: rgba(19, 29, 49, 0.65);
      --bg-card-hover: rgba(28, 42, 70, 0.8);
      --bg-input: #0a0f1d;
      --border-subtle: rgba(255, 255, 255, 0.08);
      --border-default: rgba(255, 255, 255, 0.14);
      --border-glow: rgba(99, 102, 241, 0.4);
      --border-focus: #6366f1;
      --text-primary: #f8fafc;
      --text-secondary: #94a3b8;
      --text-muted: #64748b;
      --accent-primary: #6366f1;
      --accent-secondary: #ec4899;
      --accent-gradient: linear-gradient(135deg, #6366f1 0%, #ec4899 100%);
      --accent-blue: #3b82f6;
      --accent-blue-hover: #2563eb;
      --accent-cyan: #06b6d4;
      --success: #10b981;
      --success-bg: rgba(16, 185, 129, 0.15);
      --warning: #f59e0b;
      --warning-bg: rgba(245, 158, 11, 0.15);
      --danger: #ef4444;
      --danger-bg: rgba(239, 68, 68, 0.15);
      --radius-sm: 8px;
      --radius-md: 12px;
      --radius-lg: 18px;
      --shadow-card: 0 8px 32px 0 rgba(0, 0, 0, 0.45);
      --font-mono: 'JetBrains Mono', monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background-color: var(--bg-base);
      background-image: 
        radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 85% 85%, rgba(236, 72, 153, 0.06) 0%, transparent 40%),
        radial-gradient(circle at 50% 50%, rgba(6, 182, 212, 0.04) 0%, transparent 60%);
      background-attachment: fixed;
      color: var(--text-primary);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      line-height: 1.5;
      font-size: 14px;
    }

    /* Top App Header */
    header {
      background: var(--bg-surface);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border-subtle);
      padding: 0.85rem 1.75rem;
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .header-left {
      display: flex;
      align-items: center;
      gap: 14px;
    }
    .logo-badge {
      width: 40px;
      height: 40px;
      background: var(--accent-gradient);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-radius: var(--radius-md);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 800;
      font-size: 1.15rem;
      color: #fff;
      box-shadow: 0 0 16px rgba(99, 102, 241, 0.4);
    }
    .brand-title {
      font-size: 1.1rem;
      font-weight: 700;
      letter-spacing: -0.3px;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .version-tag {
      font-size: 0.72rem;
      background: rgba(99, 102, 241, 0.15);
      color: #a5b4fc;
      border: 1px solid rgba(99, 102, 241, 0.35);
      padding: 2px 8px;
      border-radius: 20px;
      font-weight: 600;
    }
    .brand-sub {
      font-size: 0.76rem;
      color: var(--text-secondary);
    }

    .header-center {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .status-pill {
      display: flex;
      align-items: center;
      gap: 8px;
      background: var(--bg-surface-elevated);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      border: 1px solid var(--border-subtle);
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 0.8rem;
    }
    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 10px var(--success);
      animation: pulseGlow 2s infinite ease-in-out;
    }
    @keyframes pulseGlow {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.6; transform: scale(0.85); }
    }
    .status-dot.warn { background: var(--warning); box-shadow: 0 0 10px var(--warning); }
    .status-dot.error { background: var(--danger); box-shadow: 0 0 10px var(--danger); }

    .header-right {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    /* Buttons */
    .btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-family: inherit;
      font-size: 0.86rem;
      font-weight: 600;
      padding: 9px 16px;
      min-height: 40px;
      border-radius: var(--radius-sm);
      border: 1px solid transparent;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      text-decoration: none;
      white-space: nowrap;
      user-select: none;
    }
    .btn:active { transform: scale(0.98); }
    .btn-primary {
      background: var(--accent-gradient);
      color: #fff;
      box-shadow: 0 2px 14px rgba(99, 102, 241, 0.35);
    }
    .btn-primary:hover {
      box-shadow: 0 4px 20px rgba(99, 102, 241, 0.55);
      transform: translateY(-1px);
    }
    .btn-secondary {
      background: var(--bg-surface-elevated);
      color: var(--text-primary);
      border-color: var(--border-default);
    }
    .btn-secondary:hover {
      background: rgba(51, 65, 85, 0.8);
      border-color: rgba(255, 255, 255, 0.25);
      transform: translateY(-1px);
    }
    .btn-outline {
      background: transparent;
      color: var(--text-secondary);
      border-color: var(--border-default);
    }
    .btn-outline:hover {
      color: #fff;
      border-color: var(--accent-primary);
      background: rgba(99, 102, 241, 0.08);
      transform: translateY(-1px);
    }
    .btn-danger {
      background: var(--danger-bg);
      color: #fca5a5;
      border-color: rgba(239, 68, 68, 0.3);
    }
    .btn-danger:hover {
      background: rgba(239, 68, 68, 0.25);
      color: #fff;
    }
    .btn-sm { padding: 6px 12px; min-height: 34px; font-size: 0.8rem; border-radius: 6px; }
    .btn-block { width: 100%; }

    /* Navigation Tabs */
    .nav-tabs {
      display: flex;
      gap: 6px;
      background: var(--bg-surface);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--border-subtle);
      padding: 0 1.75rem;
      overflow-x: auto;
      scrollbar-width: none;
    }
    .nav-tabs::-webkit-scrollbar { display: none; }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-secondary);
      font-family: inherit;
      font-size: 0.88rem;
      font-weight: 500;
      padding: 13px 18px;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
      outline: none;
    }
    .tab-btn:hover { color: var(--text-primary); }
    .tab-btn.active {
      color: #fff;
      border-bottom-color: var(--accent-primary);
      font-weight: 600;
      text-shadow: 0 0 12px rgba(99, 102, 241, 0.5);
    }

    /* Main Container */
    .app-body {
      flex: 1;
      padding: 1.75rem;
      max-width: 1440px;
      width: 100%;
      margin: 0 auto;
    }
    .tab-content { display: none; }
    .tab-content.active { display: block; animation: fadeIn 0.2s cubic-bezier(0.4, 0, 0.2, 1); }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }

    /* KPI Cards Grid */
    .grid-kpi {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 1.15rem;
      margin-bottom: 1.75rem;
    }
    .kpi-card {
      background: var(--bg-card);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 1.25rem;
      box-shadow: var(--shadow-card);
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .kpi-card:hover {
      border-color: var(--border-glow);
      transform: translateY(-2px);
      box-shadow: 0 12px 30px -6px rgba(0, 0, 0, 0.6), 0 0 16px rgba(99, 102, 241, 0.15);
    }
    .kpi-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      color: var(--text-muted);
      font-size: 0.76rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.6px;
      margin-bottom: 8px;
    }
    .kpi-value {
      font-size: 1.6rem;
      font-weight: 800;
      color: #fff;
      font-family: var(--font-mono);
      margin-bottom: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      letter-spacing: -0.5px;
    }
    .kpi-desc {
      font-size: 0.78rem;
      color: var(--text-secondary);
    }

    /* Layout Grids */
    .grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(460px, 1fr)); gap: 1.5rem; margin-bottom: 1.75rem; }
    .card {
      background: var(--bg-card);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-lg);
      padding: 1.4rem;
      box-shadow: var(--shadow-card);
      transition: all 0.2s ease;
    }
    .card:hover { border-color: rgba(99, 102, 241, 0.22); }
    .card-title {
      font-size: 1.05rem;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 4px;
    }
    .card-subtitle {
      font-size: 0.82rem;
      color: var(--text-secondary);
      margin-bottom: 1.2rem;
    }

    /* Action Tiles */
    .action-tiles-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 1rem;
    }
    .action-tile {
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-md);
      padding: 1.15rem;
      cursor: pointer;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      text-decoration: none;
    }
    .action-tile:hover {
      border-color: var(--accent-primary);
      background: var(--bg-card-hover);
      transform: translateY(-3px);
      box-shadow: 0 10px 25px -4px rgba(0, 0, 0, 0.5), 0 0 16px rgba(99, 102, 241, 0.2);
    }
    .tile-top { display: flex; align-items: flex-start; gap: 10px; margin-bottom: 8px; }
    .tile-icon { font-size: 1.6rem; }
    .tile-title { font-size: 0.95rem; font-weight: 700; color: #fff; }
    .tile-tag { font-size: 0.72rem; font-family: var(--font-mono); color: var(--accent-cyan); font-weight: 500; }
    .tile-desc { font-size: 0.8rem; color: var(--text-secondary); line-height: 1.45; margin-bottom: 12px; }
    .tile-footer { display: flex; align-items: center; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); border-top: 1px solid var(--border-subtle); padding-top: 10px; }

    /* Form Controls */
    .form-group { margin-bottom: 1.25rem; }
    .form-label { display: flex; align-items: center; justify-content: space-between; font-size: 0.84rem; font-weight: 600; color: var(--text-secondary); margin-bottom: 7px; }
    .input-wrapper { position: relative; display: flex; align-items: center; }
    input[type="text"], input[type="password"], input[type="number"], textarea, select {
      width: 100%;
      background: var(--bg-input);
      border: 1px solid var(--border-default);
      color: #fff;
      padding: 10px 14px;
      min-height: 42px;
      border-radius: var(--radius-sm);
      font-size: 0.88rem;
      font-family: inherit;
      outline: none;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }
    input[type="text"]:focus, input[type="password"]:focus, input[type="number"]:focus, textarea:focus, select:focus {
      border-color: var(--border-focus);
      box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
    }
    .input-toggle-btn { position: absolute; right: 10px; background: transparent; border: none; color: var(--text-muted); cursor: pointer; padding: 6px; font-size: 0.95rem; }
    .input-toggle-btn:hover { color: #fff; }

    /* Switch */
    .switch-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 12px 14px;
      background: var(--bg-surface);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      margin-bottom: 10px;
      transition: border-color 0.15s;
    }
    .switch-row:hover { border-color: rgba(255, 255, 255, 0.18); }
    .switch-title { font-size: 0.88rem; font-weight: 600; color: #fff; }
    .switch-sub { font-size: 0.76rem; color: var(--text-muted); }
    .switch { position: relative; display: inline-block; width: 44px; height: 24px; flex-shrink: 0; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider {
      position: absolute; cursor: pointer;
      top: 0; left: 0; right: 0; bottom: 0;
      background-color: #334155;
      transition: .2s;
      border-radius: 24px;
    }
    .slider:before {
      position: absolute; content: "";
      height: 18px; width: 18px; left: 3px; bottom: 3px;
      background-color: white;
      transition: .2s;
      border-radius: 50%;
    }
    input:checked + .slider { background-color: var(--accent-primary); }
    input:checked + .slider:before { transform: translateX(20px); }

    /* Visual Toolbar Button */
    .tool-btn {
      display: inline-flex; align-items: center; justify-content: center; gap: 6px;
      background: var(--bg-surface-elevated); border: 1px solid var(--border-default);
      color: var(--text-primary); font-family: inherit; font-size: 0.82rem; font-weight: 600;
      padding: 7px 12px; min-height: 38px; min-width: 40px; border-radius: var(--radius-sm);
      cursor: pointer; transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1); outline: none;
    }
    .tool-btn:hover {
      background: var(--bg-card-hover); border-color: var(--accent-primary);
      color: #fff; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(99, 102, 241, 0.25);
    }
    .tool-btn:active { transform: scale(0.96); }
    .tool-btn:focus-visible { outline: 2px solid var(--accent-primary); }

    /* Telegram Realistic Chat Mockup */
    .tg-device-mockup {
      background: #0f1621;
      background-image: 
        radial-gradient(circle at 100% 0%, rgba(99, 102, 241, 0.08), transparent 40%),
        radial-gradient(circle at 0% 100%, rgba(6, 182, 212, 0.06), transparent 40%);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: var(--radius-lg);
      padding: 16px;
      max-width: 520px;
      margin: 0 auto 16px auto;
      box-shadow: 0 12px 35px -6px rgba(0, 0, 0, 0.6);
    }
    .tg-chat-header {
      display: flex; align-items: center; gap: 12px;
      padding-bottom: 12px; margin-bottom: 12px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.07);
    }
    .tg-avatar {
      width: 38px; height: 38px; border-radius: 50%;
      background: linear-gradient(135deg, #6366f1 0%, #ec4899 100%);
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; font-size: 0.95rem; color: #fff;
      box-shadow: 0 2px 10px rgba(99, 102, 241, 0.4);
    }
    .tg-chat-meta { display: flex; flex-direction: column; }
    .tg-channel-name {
      font-weight: 600; font-size: 0.95rem; color: #fff;
      display: flex; align-items: center; gap: 6px;
    }
    .tg-badge-check {
      display: inline-flex; align-items: center; justify-content: center;
      width: 14px; height: 14px; background: #38bdf8; color: #0c1524;
      border-radius: 50%; font-size: 9px; font-weight: 900;
    }
    .tg-channel-subs { font-size: 0.75rem; color: #708499; }
    .tg-post-bubble {
      background: #182533; border-radius: 14px; border-bottom-left-radius: 4px;
      padding: 12px; color: #f1f5f9; box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
      border: 1px solid rgba(255, 255, 255, 0.04);
    }
    .tg-post-img-wrap {
      width: 100%; border-radius: 10px; overflow: hidden; margin-bottom: 10px; background: #080c14;
    }
    .tg-post-img {
      width: 100%; height: auto; max-height: 520px; object-fit: contain; display: block;
      transition: transform 0.3s ease;
    }
    .tg-post-img:hover { transform: scale(1.02); }
    .tg-post-text {
      font-size: 0.88rem; line-height: 1.5; color: #f1f5f9; white-space: pre-wrap; word-break: break-word;
    }
    .tg-post-text a { color: #64b5f6; text-decoration: none; }
    .tg-post-text a:hover { text-decoration: underline; }
    .tg-post-text blockquote {
      border-left: 3px solid #6366f1; padding: 4px 8px; margin: 6px 0;
      color: #cbd5e1; background: rgba(99, 102, 241, 0.08); border-radius: 0 6px 6px 0;
    }
    .tg-post-footer {
      display: flex; align-items: center; justify-content: flex-end;
      gap: 4px; margin-top: 6px; font-size: 0.72rem; color: #708499;
    }
    .tg-post-ticks { color: #38bdf8; letter-spacing: -1px; }
    .tg-post-btn-wrap { margin-top: 8px; }
    .tg-post-btn {
      display: block; background: rgba(255, 255, 255, 0.07);
      border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 9px;
      color: #64b5f6; text-align: center; padding: 10px 14px; font-size: 0.88rem;
      font-weight: 500; text-decoration: none; transition: background 0.15s, border-color 0.15s;
      cursor: pointer;
    }
    .tg-post-btn:hover {
      background: rgba(255, 255, 255, 0.12); border-color: rgba(100, 181, 246, 0.3);
    }

    /* Console Terminal */
    .terminal-container {
      background: #05080f;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: var(--radius-sm);
      padding: 12px;
      font-family: var(--font-mono);
      font-size: 0.8rem;
      height: 380px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .log-line { display: flex; gap: 8px; line-height: 1.4; }
    .log-ts { color: #64748b; flex-shrink: 0; }
    .log-lvl { font-weight: 600; padding: 0 4px; border-radius: 2px; flex-shrink: 0; }
    .log-lvl.info { color: #38bdf8; }
    .log-lvl.success { color: #34d399; }
    .log-lvl.error { color: #f87171; }
    .log-msg { color: #cbd5e1; word-break: break-word; }

    /* Toast */
    #toastContainer {
      position: fixed; bottom: 24px; right: 24px; z-index: 9999;
      display: flex; flex-direction: column; gap: 10px;
      max-width: 400px; width: calc(100% - 48px);
    }
    .toast {
      background: rgba(22, 32, 53, 0.95);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--border-default);
      color: #fff; padding: 13px 18px; border-radius: var(--radius-md);
      box-shadow: 0 14px 40px rgba(0, 0, 0, 0.6);
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      animation: slideIn 0.25s cubic-bezier(0.4, 0, 0.2, 1) forwards; font-size: 0.88rem;
    }
    .toast.success { border-color: rgba(16, 185, 129, 0.5); box-shadow: 0 10px 30px rgba(16, 185, 129, 0.2); }
    .toast.error { border-color: rgba(239, 68, 68, 0.5); box-shadow: 0 10px 30px rgba(239, 68, 68, 0.2); }
    .toast.info { border-color: rgba(99, 102, 241, 0.5); box-shadow: 0 10px 30px rgba(99, 102, 241, 0.2); }
    @keyframes slideIn { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

    @media (max-width: 768px) {
      header { padding: 0.75rem 1rem; }
      .nav-tabs { padding: 0 1rem; }
      .app-body { padding: 1rem; }
      .grid-2 { grid-template-columns: 1fr; }
      .btn { min-height: 44px; }
    }
  </style>
</head>
<body>

  <!-- Header -->
  <header>
    <div class="header-left">
      <div class="logo-badge">AV</div>
      <div>
        <div class="brand-title">
          AnimeVist <span>Bot Console</span>
          <span class="version-tag">24/7 v2.3</span>
        </div>
        <div class="brand-sub">Операционный центр автоматизации Telegram-канала</div>
      </div>
    </div>

    <div class="header-center">
      <div class="status-pill">
        <div class="status-dot" id="headerDot"></div>
        <span id="headerStatusText">Подключение к боту...</span>
      </div>
    </div>

    <div class="header-right">
      <button class="btn btn-secondary btn-sm" onclick="sendTestMessage()">
        💬 Тест канала
      </button>
      <button class="btn btn-primary btn-sm" onclick="runAction('releases')">
        📺 Сканировать серии
      </button>
      <button class="btn btn-outline btn-sm" onclick="loadData()" title="Обновить">
        🔄
      </button>
    </div>
  </header>

  <!-- Navigation Tabs -->
  <nav class="nav-tabs">
    <button class="tab-btn active" onclick="switchTab('tab-overview', this)">📊 Мониторинг & KPI</button>
    <button class="tab-btn" onclick="switchTab('tab-actions', this)">⚡ Ручная публикация</button>
    <button class="tab-btn" onclick="switchTab('tab-config', this)">⚙️ Конфигурация</button>
    <button class="tab-btn" onclick="switchTab('tab-storage', this)">💾 Облачное хранилище</button>
    <button class="tab-btn" onclick="switchTab('tab-console', this)">📟 Консоль логов</button>
  </nav>

  <!-- Main Content -->
  <main class="app-body">
    <!-- TAB 1: OVERVIEW -->
    <section id="tab-overview" class="tab-content active">
      <div class="grid-kpi">
        <div class="kpi-card">
          <div class="kpi-header"><span>👥 АУДИТОРИЯ КАНАЛА</span><span>📢</span></div>
          <div class="kpi-value" style="color:#60a5fa;" id="kpiAudience">—</div>
          <div class="kpi-desc" id="kpiAudienceSub">Канал: AnimeVist</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-header"><span>📺 ВЫПУЩЕНО СЕРИЙ</span><span>🎬</span></div>
          <div class="kpi-value" style="color:var(--success);" id="kpiEpisodes">—</div>
          <div class="kpi-desc" id="kpiEpisodesSub">Мониторинг: каждые 5 мин</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-header"><span>📰 ЛЕНТА НОВОСТЕЙ</span><span>⚡</span></div>
          <div class="kpi-value" style="color:#f59e0b;" id="kpiNews">—</div>
          <div class="kpi-desc" id="kpiNewsSub">Shikimori • MAL • ANN</div>
        </div>

        <div class="kpi-card">
          <div class="kpi-header"><span>🌟 ТОП-ПОДБОРКИ</span><span>🖼️</span></div>
          <div class="kpi-value" style="color:#c084fc;" id="kpiCompilations">HD Коллажи</div>
          <div class="kpi-desc" id="kpiCompilationsSub">Каждые 6 часов</div>
        </div>
      </div>

      <div class="grid-2">
        <div class="card">
          <div class="card-title">⚡ Быстрый Запуск Модулей Вещания</div>
          <div class="card-subtitle">Мгновенная публикация контента в Telegram одним кликом:</div>

          <div class="action-tiles-grid">
            <div class="action-tile" onclick="runAction('releases')">
              <div class="tile-top">
                <div class="tile-icon">📺</div>
                <div>
                  <div class="tile-title">Новые серии</div>
                  <div class="tile-tag">#онгоинг</div>
                </div>
              </div>
              <div class="tile-desc">Точный номер серии, постеры без 404, хештеги жанров.</div>
              <div class="tile-footer"><span>Ручной запуск</span><span class="btn btn-outline btn-sm">Старт ➔</span></div>
            </div>

            <div class="action-tile" onclick="runAction('news')">
              <div class="tile-top">
                <div class="tile-icon">📰</div>
                <div>
                  <div class="tile-title">Аниме-новости</div>
                  <div class="tile-tag">#новости</div>
                </div>
              </div>
              <div class="tile-desc">Мульти-сбор: Shikimori, MyAnimeList, ANN + перевод.</div>
              <div class="tile-footer"><span>Ручной запуск</span><span class="btn btn-outline btn-sm">Старт ➔</span></div>
            </div>

            <div class="action-tile" onclick="switchTab('tab-actions', document.querySelectorAll('.tab-btn')[1]); focusCompilation();">
              <div class="tile-top">
                <div class="tile-icon">🌟</div>
                <div>
                  <div class="tile-title">Топ-подборки</div>
                  <div class="tile-tag">#подборка</div>
                </div>
              </div>
              <div class="tile-desc">Топ 3-10 аниме: Киберпанк, Фэнтези, Триллеры, Романтика.</div>
              <div class="tile-footer"><span>Выбрать тему</span><span class="btn btn-outline btn-sm">Открыть ➔</span></div>
            </div>

            <div class="action-tile" onclick="runAction('patchnote')">
              <div class="tile-top">
                <div class="tile-icon">🚀</div>
                <div>
                  <div class="tile-title">Патчноут релиза</div>
                  <div class="tile-tag">#patchnote</div>
                </div>
              </div>
              <div class="tile-desc">Публикация свежего релиза приложения из GitHub.</div>
              <div class="tile-footer"><span>Ручной запуск</span><span class="btn btn-outline btn-sm">Старт ➔</span></div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="card-title">📊 Пульт Контент-Менеджера и Пульс Канала</div>
          <div style="display:flex; flex-direction:column; gap:12px; margin-bottom:18px;">
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-secondary);">Статус вещания:</span>
              <strong style="color:var(--success);" id="cmStatus">🟢 Автономно 24/7</strong>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-secondary);">Целевой канал:</span>
              <span style="font-family:var(--font-mono); color:#fff;" id="cmChannelTitle">AnimeVist</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-secondary);">Формат подборок:</span>
              <span style="font-family:var(--font-mono); color:var(--accent-cyan);">HD-коллаж (до 10 аниме / сетка 5×2)</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-secondary);">База данных Supabase:</span>
              <span style="font-family:var(--font-mono); color:var(--success);" id="cmDbStatus">Синхронизировано</span>
            </div>
          </div>

          <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px;">
            <button class="btn btn-primary" onclick="switchTab('tab-actions', document.querySelectorAll('.tab-btn')[1]); focusCustomPost();">
              ✍️ Создать пост
            </button>
            <button class="btn btn-secondary" onclick="switchTab('tab-actions', document.querySelectorAll('.tab-btn')[1]); focusCompilation();">
              🌟 Выпустить подборку
            </button>
            <button class="btn btn-outline" onclick="runAction('releases')">
              📺 Проверить серии
            </button>
            <a id="btnOpenChannel" href="https://t.me/animevist" target="_blank" class="btn btn-outline" style="text-align:center; text-decoration:none;">
              📢 Открыть канал
            </a>
          </div>
        </div>
      </div>
    </section>

    <!-- TAB 2: MANUAL ACTIONS & POST STUDIO -->
    <section id="tab-actions" class="tab-content">
      <div class="grid-2">
        <!-- Compilations & Instant Triggers -->
        <div class="card">
          <div class="card-title">🌟 Публикация Топ-Подборки Аниме (#подборка)</div>
          <div class="card-subtitle">Формирует единый постер-коллаж и подробное описание без повторов:</div>

          <div style="background:rgba(6,182,212,0.1); border:1px solid rgba(6,182,212,0.3); border-radius:var(--radius-sm); padding:10px 12px; margin:12px 0 16px 0; font-size:0.8rem; color:#67e8f9; display:flex; align-items:center; gap:8px;">
            <span>🖼</span>
            <span>Обложки объединяются в <b>единый HD-коллаж</b> (1-рядный для 3-5, сетка 5×2 для 10) с номерами и шапкой!</span>
          </div>

          <div class="form-group">
            <label class="form-label">Тема подборки:</label>
            <select id="compilationGenreSelect" onchange="previewSelectedCompTheme(this.value)">
              <option value="auto">🔄 Автоматический выбор (по очереди без повторов)</option>
              <option value="must_watch">🏆 Золотая классика и шедевры (8.5+)</option>
              <option value="hidden_gems">💎 Недооценённые алмазы и скрытые жемчужины</option>
              <option value="mindfuck">🧠 Игры разума, психологические триллеры и детективы</option>
              <option value="cyberpunk_scifi">🌆 Киберпанк, космос и фантастика</option>
              <option value="epic_fantasy">⚔️ Эпическое фэнтези и приключения</option>
              <option value="soul_romance">💖 Трогательная романтика и драма</option>
              <option value="pure_comedy">😂 Отборные комедии и позитив</option>
              <option value="isekai_special">🌀 Захватывающие исекаи и попаданцы</option>
            </select>
          </div>

          <div class="form-group">
            <label class="form-label">Количество аниме в подборке (в 1 коллаже):</label>
            <select id="compilationCountSelect" onchange="previewSelectedCompTheme(document.getElementById('compilationGenreSelect').value)">
              <option value="3">3 аниме (крупный постер)</option>
              <option value="4" selected>4 аниме (рекомендуется)</option>
              <option value="5">5 аниме (панорамный коллаж)</option>
              <option value="7">7 аниме (сетка 4+3)</option>
              <option value="10">10 аниме (ТОП-10 сетка 5×2)</option>
            </select>
            <button type="button" class="btn btn-secondary" onclick="rerollCompilationPreview()" style="margin-top:8px; width:100%; display:flex; align-items:center; justify-content:center; gap:6px;">
              <span>🎲</span> <span>Подобрать другие аниме (Случайная ротация)</span>
            </button>
          </div>

          <div class="form-label" style="margin-top:12px; font-weight:600; color:var(--text-primary);">
            🖼 Предпросмотр карточки подборки в Telegram:
          </div>

          <div class="tg-device-mockup" style="margin-bottom:16px;">
            <div class="tg-chat-header">
              <div class="tg-avatar">AV</div>
              <div class="tg-chat-meta">
                <div class="tg-channel-name">
                  AnimeVist <span class="tg-badge-check">✓</span>
                </div>
                <div class="tg-channel-subs">канал • #подборка</div>
              </div>
            </div>
            <div class="tg-post-bubble">
              <div class="tg-post-img-wrap" style="display:block;">
                <img id="compPreviewImg" class="tg-post-img" alt="Обложка" src="https://images.unsplash.com/photo-1578632767115-351597cf2477?w=800&q=80">
              </div>
              <div id="compPreviewText" class="tg-post-text"></div>
              <div class="tg-post-footer">
                <span class="tg-post-time" id="compPreviewTime">14:30</span>
                <span class="tg-post-ticks">✓✓</span>
              </div>
            </div>
          </div>

          <button class="btn btn-primary btn-block" onclick="publishCompilation()" style="margin-bottom:18px;">
            🌟 Опубликовать выбранную подборку сейчас
          </button>

          <div style="border-top:1px solid var(--border-subtle); padding-top:16px;">
            <div class="card-title" style="font-size:0.92rem;">⚡ Мгновенные публикации серий и новостей:</div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px;">
              <button class="btn btn-secondary" onclick="runAction('releases')">
                📺 Новые серии
              </button>
              <button class="btn btn-secondary" onclick="runAction('news')">
                📰 Собрать новости
              </button>
            </div>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:10px;">
              <button class="btn btn-outline" onclick="runAction('patchnote')">
                🚀 Патчноут GitHub
              </button>
              <button class="btn btn-outline" onclick="runAction('pinned')">
                📌 Закрепить навигатор
              </button>
            </div>
          </div>
        </div>

        <!-- Custom Post Studio -->
        <div class="card">
          <div class="card-title">✍️ Студия Кастомного Поста в Канал</div>
          <div class="card-subtitle">Создайте пост с форматированием, фото и кнопкой без ручного HTML-кодинга:</div>

          <div class="form-group">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <label class="form-label" style="margin-bottom:0;">Текст публикации:</label>
              <button class="btn btn-sm" type="button" onclick="autoFormatAnimeVistPost('customText')" style="background:var(--accent-gradient); color:#fff; font-weight:700; box-shadow:0 2px 10px rgba(99,102,241,0.35);">
                ✨ Оформить в стиле AnimeVist
              </button>
            </div>

            <!-- Visual Formatting Toolbar (UI/UX Pro Max touch targets) -->
            <div class="editor-toolbar" style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:10px; background:var(--bg-surface); padding:8px; border-radius:var(--radius-md); border:1px solid var(--border-subtle);">
              <button type="button" class="tool-btn" onclick="insertTag('customText', 'b')" title="Жирный шрифт (Ctrl+B)"><b>B</b></button>
              <button type="button" class="tool-btn" onclick="insertTag('customText', 'i')" title="Курсив (Ctrl+I)"><i>I</i></button>
              <button type="button" class="tool-btn" onclick="insertTag('customText', 'tg-spoiler')" title="Спойлер (скрыть текст)">👁 Спойлер</button>
              <button type="button" class="tool-btn" onclick="insertLinkPrompt('customText')" title="Вставить ссылку">🔗 Ссылка</button>
              <button type="button" class="tool-btn" onclick="insertTag('customText', 'blockquote')" title="Цитата">💬 Цитата</button>
              <button type="button" class="tool-btn" onclick="insertSnippet('customText', '⭐️ <b>Рейтинг:</b> 8.6 / 10 (Shikimori)\n')" title="Вставить рейтинг">⭐️ Рейтинг</button>
              <button type="button" class="tool-btn" onclick="insertSnippet('customText', '🎬 <b>Студия:</b> MAPPA\n📅 <b>Премьера:</b> 2026\n')" title="Студия и дата">🎬 Студия/Дата</button>
              <button type="button" class="tool-btn" onclick="insertSnippet('customText', '\n\n#новости #анонс #animevist')" title="Хештеги">🏷 Хештеги</button>
            </div>

            <textarea id="customText" rows="6" placeholder="Вставьте любой сырой текст или заметку — и нажмите «✨ Оформить в стиле AnimeVist», либо используйте кнопки панели форматирования..." oninput="updateCustomPreview()"></textarea>
          </div>

          <div class="form-group">
            <label class="form-label">URL изображения / постера (опционально):</label>
            <input type="text" id="customPhoto" placeholder="https://example.com/poster.jpg" oninput="updateCustomPreview()">
          </div>

          <div class="grid-2" style="margin-bottom:0; gap:10px;">
            <div class="form-group">
              <label class="form-label">Текст кнопки (опционально):</label>
              <input type="text" id="customBtnText" placeholder="Смотреть в AnimeVist" oninput="updateCustomPreview()">
            </div>
            <div class="form-group">
              <label class="form-label">Ссылка кнопки (URL):</label>
              <input type="text" id="customBtnUrl" placeholder="https://t.me/animevist" oninput="updateCustomPreview()">
            </div>
          </div>

          <!-- Preview -->
          <div class="form-label" style="margin-top:14px; font-weight:600; color:var(--text-primary);">
            📱 Симуляция поста в Telegram-канале (Live Device Preview):
          </div>
          <div class="tg-device-mockup">
            <div class="tg-chat-header">
              <div class="tg-avatar">AV</div>
              <div class="tg-chat-meta">
                <div class="tg-channel-name">
                  AnimeVist <span class="tg-badge-check">✓</span>
                </div>
                <div class="tg-channel-subs">канал • живой просмотр</div>
              </div>
            </div>

            <div class="tg-post-bubble">
              <div id="previewImgWrap" class="tg-post-img-wrap" style="display:none;">
                <img id="previewImg" class="tg-post-img" alt="Постер">
              </div>
              <div id="previewText" class="tg-post-text">Текст вашего сообщения появится здесь...</div>
              <div class="tg-post-footer">
                <span class="tg-post-time" id="previewPostTime">14:30</span>
                <span class="tg-post-ticks">✓✓</span>
              </div>
            </div>

            <div id="previewBtnWrap" class="tg-post-btn-wrap" style="display:none;">
              <a id="previewBtn" class="tg-post-btn" target="_blank">Кнопка</a>
            </div>
          </div>

          <div style="margin-top:16px;">
            <button class="btn btn-primary btn-block" onclick="sendCustomPost()">
              🚀 Опубликовать кастомный пост в канал
            </button>
          </div>
        </div>
      </div>
    </section>

    <!-- TAB 3: CONFIGURATION -->
    <section id="tab-config" class="tab-content">
      <div class="card" style="max-width: 820px; margin: 0 auto;">
        <div class="card-title">⚙️ Настройки Telegram & Параметров Автоматизации</div>
        <div class="card-subtitle">Все изменения сохраняются в конфигурацию и базу Supabase.</div>

        <h3 style="font-size:0.9rem; color:var(--accent-blue); margin-bottom:12px; text-transform:uppercase; letter-spacing:0.5px;">1. Ключи и авторизация Telegram</h3>
        
        <div class="form-group">
          <div class="form-label">
            <span>Токен Telegram-бота:</span>
            <span style="font-size:0.75rem; color:var(--text-muted);">От @BotFather</span>
          </div>
          <div class="input-wrapper">
            <input type="password" id="cfg_token" placeholder="8958974614:AAF-...">
            <button type="button" class="input-toggle-btn" onclick="togglePasswordVisibility('cfg_token', this)">👁️</button>
          </div>
        </div>

        <div class="grid-2">
          <div class="form-group">
            <div class="form-label">
              <span>ID канала:</span>
              <a href="javascript:void(0)" onclick="autoDetectChannel()" style="color:var(--accent-cyan); text-decoration:none; font-size:0.75rem;">🔍 Найти ID</a>
            </div>
            <input type="text" id="cfg_channel" placeholder="-1004465332635">
          </div>

          <div class="form-group">
            <div class="form-label">
              <span>Ссылка чата обсуждений:</span>
            </div>
            <input type="text" id="cfg_chat" placeholder="https://t.me/animevist_chat">
          </div>
        </div>

        <div class="form-group">
          <div class="form-label">
            <span>ID Telegram Администратора:</span>
          </div>
          <input type="text" id="cfg_admin" placeholder="869155357">
        </div>

        <h3 style="font-size:0.9rem; color:var(--accent-blue); margin-top:24px; margin-bottom:12px; text-transform:uppercase; letter-spacing:0.5px;">2. Режимы и модули вещания</h3>

        <div class="switch-row">
          <div>
            <div class="switch-title">Автопостинг новых серий (#онгоинг)</div>
            <div class="switch-sub">Опрос AnimeVost & Shikimori с точным распознаванием номера серии</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="cfg_releases_enabled" checked>
            <span class="slider"></span>
          </label>
        </div>

        <div class="switch-row">
          <div>
            <div class="switch-title">Автопостинг аниме-новостей (#новости)</div>
            <div class="switch-sub">Сбор из Shikimori, MyAnimeList и ANN с авто-переводом и категоризацией</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="cfg_news_enabled" checked>
            <span class="slider"></span>
          </label>
        </div>

        <div class="switch-row">
          <div>
            <div class="switch-title">Автопостинг топ-подборок аниме (#подборка)</div>
            <div class="switch-sub">Тематические коллекции топ-аниме (Киберпанк, Фэнтези, Триллеры и др.)</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="cfg_compilations_enabled" checked>
            <span class="slider"></span>
          </label>
        </div>

        <div class="switch-row">
          <div>
            <div class="switch-title">Жанровые хештеги к сериям (#фэнтези #онгоинг #серия10)</div>
            <div class="switch-sub">Удобная быстрая фильтрация по жанрам для подписчиков канала</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="cfg_genre_hashtags_enabled" checked>
            <span class="slider"></span>
          </label>
        </div>

        <div class="switch-row">
          <div>
            <div class="switch-title">Кнопка «Обсудить серию в чате»</div>
            <div class="switch-sub">Показывать инлайн-кнопку обсуждения к сериям (если ссылка задана)</div>
          </div>
          <label class="switch">
            <input type="checkbox" id="cfg_chat_button_enabled">
            <span class="slider"></span>
          </label>
        </div>

        <div class="grid-2" style="margin-top:14px;">
          <div class="form-group">
            <div class="form-label">
              <span>Интервал серий/новостей (секунды):</span>
            </div>
            <input type="number" id="cfg_interval" value="300" min="30" step="30">
          </div>
          <div class="form-group">
            <div class="form-label">
              <span>Интервал подборок (часов):</span>
            </div>
            <input type="number" id="cfg_comp_hours" value="6" min="1" step="1">
          </div>
        </div>

        <div style="margin-top:25px;">
          <button class="btn btn-primary btn-block" onclick="saveSettings()">
            💾 Сохранить и применить конфигурацию
          </button>
        </div>
      </div>
    </section>

    <!-- TAB 4: CLOUD STORAGE -->
    <section id="tab-storage" class="tab-content">
      <div class="card" style="max-width: 820px; margin: 0 auto;">
        <div class="card-title">💾 Облачное Хранилище Supabase (Активно)</div>
        <div class="card-subtitle">
          База данных AnimeVist обеспечивает вечное сохранение настроек и истории опубликованных серий без риска потери данных:
        </div>

        <div style="background:var(--bg-surface); border:1px solid rgba(16,185,129,0.3); border-radius:var(--radius-sm); padding:16px; margin-bottom:15px;">
          <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:8px;">
            <h4 style="color:#fff; font-size:0.92rem; display:flex; align-items:center; gap:8px;">
              <span>🐘 Supabase Database</span>
              <span style="font-size:0.7rem; background:rgba(16,185,129,0.15); color:#34d399; padding:2px 8px; border-radius:12px; font-weight:600;">АКТИВНА</span>
            </h4>
            <button class="btn btn-outline btn-sm" onclick="testSupabaseConnection()">
              🔌 Проверить связь
            </button>
          </div>
          <p style="font-size:0.8rem; color:var(--text-secondary); margin-bottom:12px; line-height:1.45;">
            Ваша облачная база данных AnimeVist подключена. Таблица <code>bot_config</code> хранит конфигурацию, а таблица <code>bot_seen_items</code> исключает повторные публикации серий и новостей.
          </p>

          <div class="form-group">
            <label class="form-label">SUPABASE_URL:</label>
            <input type="text" id="storage_supabase_url" value="https://zuciuwunelfqhhhohhyn.supabase.co">
          </div>
          <div class="form-group" style="margin-bottom:0;">
            <label class="form-label">SUPABASE_KEY:</label>
            <input type="password" id="storage_supabase_key">
          </div>
        </div>

        <div style="display:flex; gap:10px;">
          <button class="btn btn-primary btn-block" onclick="syncCloudNow()">
            ☁️ Загрузить бэкап в Supabase
          </button>
          <button class="btn btn-secondary btn-block" onclick="fetchCloudNow()">
            📥 Восстановить из Supabase
          </button>
        </div>
      </div>
    </section>

    <!-- TAB 5: CONSOLE -->
    <section id="tab-console" class="tab-content">
      <div class="card">
        <div class="console-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
          <div class="card-title" style="margin:0;">📟 Консоль Автономного Демона 24/7</div>
          <div style="display:flex; gap:8px;">
            <button class="btn btn-outline btn-sm" onclick="clearConsoleView()">🧹 Очистить</button>
            <button class="btn btn-outline btn-sm" onclick="fetchLogsOnly()">🔄 Обновить</button>
          </div>
        </div>

        <div class="terminal-container" id="terminalBox">
          <div class="log-line"><span class="log-ts">[00:00:00]</span> <span class="log-lvl info">INFO</span> <span class="log-msg">Ожидание событий демона...</span></div>
        </div>
      </div>
    </section>
  </main>

  <!-- Toast Container -->
  <div id="toastContainer"></div>

  <script>
    let currentConfig = null;
    let rawLogs = [];

    function showToast(message, type = 'info', duration = 3500) {
      const c = document.getElementById('toastContainer');
      const t = document.createElement('div');
      t.className = `toast ${type}`;
      const icon = type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️');
      t.innerHTML = `<span>${icon} ${message}</span><button style="background:transparent; border:none; color:#94a3b8; cursor:pointer; font-size:1rem;" onclick="this.parentElement.remove()">&times;</button>`;
      c.appendChild(t);
      setTimeout(() => {
        t.style.opacity = '0';
        t.style.transform = 'translateY(10px)';
        t.style.transition = 'all 0.2s';
        setTimeout(() => t.remove(), 200);
      }, duration);
    }

    function switchTab(tabId, el) {
      document.querySelectorAll('.tab-content').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      const target = document.getElementById(tabId);
      if (target) target.classList.add('active');
      if (el) el.classList.add('active');
    }

    function togglePasswordVisibility(id, btn) {
      const input = document.getElementById(id);
      if (input.type === 'password') {
        input.type = 'text';
        btn.innerText = '🙈';
      } else {
        input.type = 'password';
        btn.innerText = '👁️';
      }
    }

    async function loadData() {
      try {
        const res = await fetch('/api/status');
        const data = await res.json();
        currentConfig = data.config || {};
        const tg = currentConfig.telegram || {};
        const app = currentConfig.app || {};
        const ann = currentConfig.announcer || {};
        const cloud = currentConfig.cloud_storage || {};

        if (data.bot) {
          document.getElementById('headerStatusText').innerText = `@${data.bot.username} Онлайн`;
          document.getElementById('headerDot').className = 'status-dot';
        } else {
          document.getElementById('headerStatusText').innerText = 'Ошибка подключения к боту';
          document.getElementById('headerDot').className = 'status-dot error';
        }

        // Live audience metric
        if (data.member_count !== undefined && data.member_count !== null) {
          document.getElementById('kpiAudience').innerText = `${data.member_count} подписч.`;
        } else {
          document.getElementById('kpiAudience').innerText = 'Канал активен';
        }

        if (data.chat && data.chat.title) {
          document.getElementById('kpiAudienceSub').innerText = `${data.chat.title}`;
          document.getElementById('cmChannelTitle').innerText = `${data.chat.title} (${tg.channel_id || ''})`;
          if (data.chat.invite_link) {
            document.getElementById('btnOpenChannel').href = data.chat.invite_link;
          }
        } else if (tg.channel_id) {
          document.getElementById('cmChannelTitle').innerText = `${tg.channel_id}`;
        }

        // Content Manager Metrics
        const stats = data.stats || {};
        document.getElementById('kpiEpisodes').innerText = `${stats.episodes || 0} серий`;
        document.getElementById('kpiEpisodesSub').innerText = `Интервал: ${ann.check_interval_seconds || 300} сек`;

        document.getElementById('kpiNews').innerText = `${stats.news || 0} новостей`;
        document.getElementById('kpiNewsSub').innerText = `Shikimori • MAL • ANN`;

        document.getElementById('kpiCompilations').innerText = `HD-коллажи`;
        document.getElementById('kpiCompilationsSub').innerText = `Каждые ${ann.compilations_interval_hours || 6} ч`;

        // Config form
        document.getElementById('cfg_token').value = tg.bot_token || '';
        document.getElementById('cfg_channel').value = tg.channel_id || '';
        document.getElementById('cfg_chat').value = app.chat_invite_url || '';
        document.getElementById('cfg_admin').value = tg.admin_id || '';
        document.getElementById('cfg_releases_enabled').checked = ann.enable_series_releases !== false;
        document.getElementById('cfg_news_enabled').checked = ann.enable_anime_news !== false;
        document.getElementById('cfg_compilations_enabled').checked = ann.enable_compilations !== false;
        document.getElementById('cfg_genre_hashtags_enabled').checked = ann.include_genre_hashtags !== false;
        document.getElementById('cfg_chat_button_enabled').checked = ann.show_chat_button === true;
        document.getElementById('cfg_interval').value = ann.check_interval_seconds || 300;
        document.getElementById('cfg_comp_hours').value = ann.compilations_interval_hours || 6;

        document.getElementById('storage_supabase_url').value = cloud.supabase_url || '';
        document.getElementById('storage_supabase_key').value = cloud.supabase_key || '';

        if (data.logs) {
          rawLogs = data.logs;
          renderLogs();
        }
      } catch (e) {
        console.error("loadData error:", e);
        const statusEl = document.getElementById('headerStatusText');
        const dotEl = document.getElementById('headerDot');
        if (statusEl) statusEl.innerText = 'Сервер временно недоступен (повтор...)';
        if (dotEl) dotEl.className = 'status-dot error';
        showToast("Ошибка связи с сервером дашборда", "error");
        setTimeout(loadData, 3000);
      }
    }

    function renderLogs() {
      const box = document.getElementById('terminalBox');
      box.innerHTML = rawLogs.map(l => `
        <div class="log-line">
          <span class="log-ts">[${l.time}]</span>
          <span class="log-lvl ${l.level}">${l.level.toUpperCase()}</span>
          <span class="log-msg">${escapeHtml(l.message)}</span>
        </div>
      `).join('');
      box.scrollTop = box.scrollHeight;
    }

    function escapeHtml(text) {
      return (text || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function clearConsoleView() {
      rawLogs = [];
      renderLogs();
    }

    async function fetchLogsOnly() {
      try {
        const res = await fetch('/api/logs');
        rawLogs = await res.json();
        renderLogs();
      } catch (e) {}
    }

    async function runAction(actionName) {
      showToast(`Инициирован запуск [${actionName}]...`, "info");
      try {
        const res = await fetch('/api/action', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ action: actionName })
        });
        const data = await res.json();
        if (data.ok) {
          showToast(`Действие [${actionName}] запущено`, "success");
        } else {
          showToast(`Ошибка: ${data.error}`, "error");
        }
        setTimeout(fetchLogsOnly, 1200);
      } catch (e) {
        showToast("Ошибка отправки запроса", "error");
      }
    }

    async function publishCompilation() {
      const genre = document.getElementById('compilationGenreSelect').value;
      const count = parseInt(document.getElementById('compilationCountSelect').value) || 4;
      showToast(`Публикация подборки (${count} аниме) в Telegram...`, "info");
      try {
        const res = await fetch('/api/action', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ action: 'compilation', genre: genre === 'auto' ? null : genre, count: count })
        });
        const data = await res.json();
        if (data.ok) {
          showToast("Подборка успешно отправлена в канал!", "success");
        } else {
          showToast(`Ошибка: ${data.error}`, "error");
        }
        setTimeout(fetchLogsOnly, 1200);
      } catch (e) {
        showToast("Ошибка публикации подборки", "error");
      }
    }

    /* Visual Editor & Magic Formatter Helpers */
    function insertTag(textAreaId, tagName) {
      const el = document.getElementById(textAreaId);
      if (!el) return;
      const start = el.selectionStart;
      const end = el.selectionEnd;
      const val = el.value;
      const selected = val.substring(start, end);
      const openTag = `<${tagName}>`;
      const closeTag = `</${tagName}>`;
      const replacement = selected ? `${openTag}${selected}${closeTag}` : `${openTag}Текст${closeTag}`;
      el.value = val.substring(0, start) + replacement + val.substring(end);
      el.focus();
      el.setSelectionRange(start + openTag.length, start + replacement.length - closeTag.length);
      updateCustomPreview();
    }

    function insertSnippet(textAreaId, snippet) {
      const el = document.getElementById(textAreaId);
      if (!el) return;
      const start = el.selectionStart;
      const end = el.selectionEnd;
      const val = el.value;
      el.value = val.substring(0, start) + snippet + val.substring(end);
      el.focus();
      el.setSelectionRange(start + snippet.length, start + snippet.length);
      updateCustomPreview();
    }

    function insertLinkPrompt(textAreaId) {
      const url = prompt("Введите ссылку (URL):", "https://");
      if (!url) return;
      const text = prompt("Введите текст ссылки (анкор):", "Подробнее в AnimeVist");
      if (!text) return;
      insertSnippet(textAreaId, `<a href="${url}">${text}</a>`);
    }

    function autoFormatAnimeVistPost(textAreaId) {
      const el = document.getElementById(textAreaId);
      if (!el) return;
      let raw = el.value.trim();
      if (!raw) {
        showToast("Сначала вставьте или напечатайте текст для оформления", "error");
        return;
      }

      const lines = raw.split(/\\r?\\n/).map(l => l.trim()).filter(l => l.length > 0);
      if (lines.length === 0) return;

      let title = lines[0].replace(/^[«"']|[»"']$/g, '').trim();
      title = title.replace(/^(Анонс|Новость|Релиз|Новый сезон|Премьера):\\s*/i, '');

      let studio = '';
      let date = '';
      let score = '';
      let genre = '';
      let bodyLines = [];

      for (let i = 1; i < lines.length; i++) {
        const line = lines[i];
        if (/^(студия|studio):\\s*(.*)/i.test(line)) {
          studio = line.replace(/^(студия|studio):\\s*/i, '').trim();
        } else if (/^(премьера|дата|релиз|выход|год|date|release):\\s*(.*)/i.test(line)) {
          date = line.replace(/^(премьера|дата|релиз|выход|год|date|release):\\s*/i, '').trim();
        } else if (/^(рейтинг|оценка|score|rating):\\s*(.*)/i.test(line)) {
          score = line.replace(/^(рейтинг|оценка|score|rating):\\s*/i, '').trim();
        } else if (/^(жанр|жанры|genres?):\\s*(.*)/i.test(line)) {
          genre = line.replace(/^(жанр|жанры|genres?):\\s*/i, '').trim();
        } else if (!line.startsWith('#')) {
          bodyLines.push(line);
        }
      }

      let formatted = `🔥 <b>«${title}»</b>\n\n`;

      if (studio) formatted += `🎬 <b>Студия:</b> ${studio}\n`;
      if (date) formatted += `📅 <b>Премьера:</b> ${date}\n`;
      if (score) formatted += `⭐️ <b>Рейтинг:</b> ${score}\n`;
      if (genre) formatted += `🎭 <b>Жанр:</b> ${genre}\n`;
      if (studio || date || score || genre) formatted += `\n`;

      if (bodyLines.length > 0) {
        const bodyText = bodyLines.join('\n\n');
        formatted += `${bodyText}\n\n`;
      }

      formatted += `━━━━━━━━━━━━━━━\n`;
      formatted += `💬 Чат комьюнити: @animevist_chat\n`;
      formatted += `🤖 Бот и каталог: @animevist_bot\n\n`;
      formatted += `#новости #анонс #animevist`;

      el.value = formatted;
      updateCustomPreview();
      showToast("Текст автоматически оформлен в стиле AnimeVist!", "success");
    }

    function focusCustomPost() {
      const el = document.getElementById('customText');
      if (el) el.focus();
    }

    function focusCompilation() {
      const el = document.getElementById('compilationGenreSelect');
      if (el) el.focus();
    }

    const SAMPLE_THEMES = {
      must_watch: {
        title: "Золотая Классика и Шедевры (8.5+)",
        banner: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx154587-qQTzQnEJJ3oB.jpg",
        items: [
          "1. 🏆 <b>«Провожающая в последний путь Фрирен»</b> (Sousou no Frieren)<br>⭐️ Рейтинг: <b>9.25</b> • 🎭 Фэнтези, Драма",
          "2. 🏆 <b>«Стальной алхимик: Братство»</b> (Fullmetal Alchemist)<br>⭐️ Рейтинг: <b>9.11</b> • 🎭 Сёнэн, Фэнтези",
          "3. 🏆 <b>«Врата Штейна»</b> (Steins;Gate)<br>⭐️ Рейтинг: <b>9.07</b> • 🎭 Фантастика, Триллер",
          "4. 🏆 <b>«Охотник х Охотник»</b> (Hunter x Hunter)<br>⭐️ Рейтинг: <b>9.04</b> • 🎭 Приключения",
          "5. 🏆 <b>«Монстр»</b> (Monster)<br>⭐️ Рейтинг: <b>8.87</b> • 🎭 Драма, Триллер",
          "6. 🏆 <b>«Ковбой Бибоп»</b> (Cowboy Bebop)<br>⭐️ Рейтинг: <b>8.75</b> • 🎭 Космос, Джаз",
          "7. 🏆 <b>«Гуррен-Лаганн»</b> (Tengen Toppa Gurren Lagann)<br>⭐️ Рейтинг: <b>8.63</b> • 🎭 Меха, Экшен",
          "8. 🏆 <b>«Код Гиас: Восставший Лелуш»</b> (Code Geass)<br>⭐️ Рейтинг: <b>8.70</b> • 🎭 Меха, Детектив",
          "9. 🏆 <b>«Тетрадь смерти»</b> (Death Note)<br>⭐️ Рейтинг: <b>8.62</b> • 🎭 Мистика, Триллер",
          "10. 🏆 <b>«Крутой учитель Онидзука»</b> (GTO)<br>⭐️ Рейтинг: <b>8.69</b> • 🎭 Комедия, Школа"
        ]
      },
      hidden_gems: {
        title: "Недооценённые Алмазы и Скрытые Жемчужины",
        banner: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx13125-2EDZb8ahshQc.png",
        items: [
          "1. 💎 <b>«Из нового света»</b> (Shinsekai yori)<br>⭐️ Рейтинг: <b>8.27</b> • 🎭 Драма, Фантастика",
          "2. 💎 <b>«Пинг-понг»</b> (Ping Pong the Animation)<br>⭐️ Рейтинг: <b>8.60</b> • 🎭 Спорт, Драма",
          "3. 💎 <b>«Эрго Прокси»</b> (Ergo Proxy)<br>⭐️ Рейтинг: <b>7.91</b> • 🎭 Киберпанк, Детектив",
          "4. 💎 <b>«Путешествие Кино»</b> (Kino no Tabi)<br>⭐️ Рейтинг: <b>8.38</b> • 🎭 Философия, Приключения",
          "5. 💎 <b>«Баккано!»</b> (Baccano!)<br>⭐️ Рейтинг: <b>8.38</b> • 🎭 Экшен, Комедия",
          "6. 💎 <b>«Мононокэ»</b> (Mononoke)<br>⭐️ Рейтинг: <b>8.42</b> • 🎭 Мистика, Детектив",
          "7. 💎 <b>«Альянс Серокрылых»</b> (Haibane Renmei)<br>⭐️ Рейтинг: <b>7.99</b> • 🎭 Драма, Мистика",
          "8. 💎 <b>«Радуга: Семеро из шестой камеры»</b> (Rainbow)<br>⭐️ Рейтинг: <b>8.46</b> • 🎭 Драма, Триллер",
          "9. 💎 <b>«Клеймор»</b> (Claymore)<br>⭐️ Рейтинг: <b>7.80</b> • 🎭 Тёмное фэнтези, Экшен",
          "10. 💎 <b>«Дороро»</b> (Dororo)<br>⭐️ Рейтинг: <b>8.24</b> • 🎭 Исторический, Экшен"
        ]
      },
      mindfuck: {
        title: "Игры Разума, Психологические Триллеры и Детективы",
        banner: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx1535-kUgkcrfOrkUM.jpg",
        items: [
          "1. 🧠 <b>«Монстр»</b> (Monster)<br>⭐️ Рейтинг: <b>8.87</b> • 🎭 Детектив, Триллер",
          "2. 🧠 <b>«Тетрадь смерти»</b> (Death Note)<br>⭐️ Рейтинг: <b>8.62</b> • 🎭 Мистика, Детектив",
          "3. 🧠 <b>«Психопаспорт»</b> (Psycho-Pass)<br>⭐️ Рейтинг: <b>8.34</b> • 🎭 Киберпанк, Триллер",
          "4. 🧠 <b>«Паразит: Учение о жизни»</b> (Kiseijuu)<br>⭐️ Рейтинг: <b>8.34</b> • 🎭 Экшен, Ужасы",
          "5. 🧠 <b>«Идеальная грусть»</b> (Perfect Blue)<br>⭐️ Рейтинг: <b>8.53</b> • 🎭 Психология, Триллер",
          "6. 🧠 <b>«Обещанный Неверленд»</b> (Neverland)<br>⭐️ Рейтинг: <b>8.51</b> • 🎭 Мистика, Триллер",
          "7. 🧠 <b>«Токийский гуль»</b> (Tokyo Ghoul)<br>⭐️ Рейтинг: <b>7.79</b> • 🎭 Драма, Ужасы",
          "8. 🧠 <b>«Иная»</b> (Another)<br>⭐️ Рейтинг: <b>7.46</b> • 🎭 Мистика, Ужасы",
          "9. 🧠 <b>«Игра друзей»</b> (Tomodachi Game)<br>⭐️ Рейтинг: <b>7.69</b> • 🎭 Психология, Игры",
          "10. 🧠 <b>«Шарлотта»</b> (Charlotte)<br>⭐️ Рейтинг: <b>7.74</b> • 🎭 Драма, Сверхъестественное"
        ]
      },
      cyberpunk_scifi: {
        title: "Киберпанк, Космос и Научная Фантастика",
        banner: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx120377-ayZPoxiWt4Li.jpg",
        items: [
          "1. 🌆 <b>«Киберпанк: Бегущие по краю»</b> (Edgerunners)<br>⭐️ Рейтинг: <b>8.62</b> • 🎭 Киберпанк, Экшен",
          "2. 🌆 <b>«Ковбой Бибоп»</b> (Cowboy Bebop)<br>⭐️ Рейтинг: <b>8.75</b> • 🎭 Космос, Джаз",
          "3. 🌆 <b>«Призрак в доспехах»</b> (Ghost in the Shell)<br>⭐️ Рейтинг: <b>8.28</b> • 🎭 Меха, Sci-Fi",
          "4. 🌆 <b>«Виви: Песнь флюоритового глаза»</b> (Vivy)<br>⭐️ Рейтинг: <b>8.40</b> • 🎭 Музыка, Sci-Fi",
          "5. 🌆 <b>«Акира»</b> (Akira)<br>⭐️ Рейтинг: <b>8.15</b> • 🎭 Фантастика, Экшен",
          "6. 🌆 <b>«Легенда о героях Галактики»</b> (LOGH)<br>⭐️ Рейтинг: <b>9.02</b> • 🎭 Космос, Военное",
          "7. 🌆 <b>«Триган»</b> (Trigun)<br>⭐️ Рейтинг: <b>8.21</b> • 🎭 Sci-Fi, Экшен",
          "8. 🌆 <b>«Изгнанник»</b> (Last Exile)<br>⭐️ Рейтинг: <b>7.82</b> • 🎭 Стимпанк, Приключения",
          "9. 🌆 <b>«Время Евы»</b> (Eve no Jikan)<br>⭐️ Рейтинг: <b>7.98</b> • 🎭 Sci-Fi, Повседневность",
          "10. 🌆 <b>«Акудама Драйв»</b> (Akudama Drive)<br>⭐️ Рейтинг: <b>7.58</b> • 🎭 Экшен, Киберпанк"
        ]
      },
      epic_fantasy: {
        title: "Эпическое Фэнтези и Магические Приключения",
        banner: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101348-2fhDFPCuMNiz.jpg",
        items: [
          "1. ⚔️ <b>«Сага о Винланде»</b> (Vinland Saga)<br>⭐️ Рейтинг: <b>8.75</b> • 🎭 Экшен, Приключения",
          "2. ⚔️ <b>«Берсерк (1997)»</b> (Berserk)<br>⭐️ Рейтинг: <b>8.57</b> • 🎭 Тёмное фэнтези, Драма",
          "3. ⚔️ <b>«Созданный в Бездне»</b> (Made in Abyss)<br>⭐️ Рейтинг: <b>8.66</b> • 🎭 Приключения, Драма",
          "4. ⚔️ <b>«Клинок, рассекающий демонов»</b> (Kimetsu no Yaiba)<br>⭐️ Рейтинг: <b>8.47</b> • 🎭 Сверхъестественное, Экшен",
          "5. ⚔️ <b>«Бездомный бог»</b> (Noragami)<br>⭐️ Рейтинг: <b>7.96</b> • 🎭 Мистика, Комедия",
          "6. ⚔️ <b>«Убей или умри»</b> (Kill la Kill)<br>⭐️ Рейтинг: <b>8.04</b> • 🎭 Экшен, Комедия",
          "7. ⚔️ <b>«ДжоДжо: Невероятные приключения»</b> (JoJo)<br>⭐️ Рейтинг: <b>8.11</b> • 🎭 Приключения, Экшен",
          "8. ⚔️ <b>«Подземелье вкусностей»</b> (Dungeon Meshi)<br>⭐️ Рейтинг: <b>8.58</b> • 🎭 Фэнтези, Комедия",
          "9. ⚔️ <b>«Охотник х Охотник»</b> (Hunter x Hunter)<br>⭐️ Рейтинг: <b>9.04</b> • 🎭 Экшен, Приключения",
          "10. ⚔️ <b>«Клеймор»</b> (Claymore)<br>⭐️ Рейтинг: <b>7.80</b> • 🎭 Тёмное фэнтези, Экшен"
        ]
      },
      soul_romance: {
        title: "Трогательная Романтика и Драма для Души",
        banner: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx101921-ufrjLzhSz7L1.jpg",
        items: [
          "1. 💖 <b>«Госпожа Кагуя: В любви как на войне»</b> (Kaguya-sama)<br>⭐️ Рейтинг: <b>8.89</b> • 🎭 Комедия, Романтика",
          "2. 💖 <b>«Хоримия»</b> (Horimiya)<br>⭐️ Рейтинг: <b>8.19</b> • 🎭 Школа, Романтика",
          "3. 💖 <b>«Кланнад: Продолжение истории»</b> (Clannad)<br>⭐️ Рейтинг: <b>8.93</b> • 🎭 Драма, Романтика",
          "4. 💖 <b>«Форма голоса»</b> (Koe no Katachi)<br>⭐️ Рейтинг: <b>8.93</b> • 🎭 Драма, Школа",
          "5. 💖 <b>«Твоя апрельская ложь»</b> (Shigatsu)<br>⭐️ Рейтинг: <b>8.64</b> • 🎭 Музыка, Драма",
          "6. 💖 <b>«Торадора!»</b> (Toradora!)<br>⭐️ Рейтинг: <b>8.08</b> • 🎭 Комедия, Романтика",
          "7. 💖 <b>«Этот глупый свин не понимает мечту девочки-зайки»</b><br>⭐️ Рейтинг: <b>8.24</b> • 🎭 Мистика, Романтика",
          "8. 💖 <b>«Дотянуться до тебя»</b> (Kimi ni Todoke)<br>⭐️ Рейтинг: <b>7.99</b> • 🎭 Школа, Романтика",
          "9. 💖 <b>«Опасность в моем сердце»</b> (Bokuyaba)<br>⭐️ Рейтинг: <b>8.78</b> • 🎭 Комедия, Романтика",
          "10. 💖 <b>«Пять невест»</b> (Gotoubun)<br>⭐️ Рейтинг: <b>7.64</b> • 🎭 Гарем, Романтика"
        ]
      },
      pure_comedy: {
        title: "Отборные Комедии и Море Позитива",
        banner: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx918-iOaeBVUn4uK7.jpg",
        items: [
          "1. 😂 <b>«Гинтама»</b> (Gintama)<br>⭐️ Рейтинг: <b>8.93</b> • 🎭 Пародия, Экшен",
          "2. 😂 <b>«Необъятный океан»</b> (Grand Blue)<br>⭐️ Рейтинг: <b>8.44</b> • 🎭 Комедия, Студенты",
          "3. 😂 <b>«Несладкая жизнь псионика Сайки К.»</b><br>⭐️ Рейтинг: <b>8.41</b> • 🎭 Комедия, Мистика",
          "4. 😂 <b>«Этот замечательный мир! (KonoSuba)»</b><br>⭐️ Рейтинг: <b>8.10</b> • 🎭 Комедия, Пародия",
          "5. 😂 <b>«Моб Психо 100»</b> (Mob Psycho 100)<br>⭐️ Рейтинг: <b>8.48</b> • 🎭 Экшен, Комедия",
          "6. 😂 <b>«Крутой учитель Онидзука»</b> (GTO)<br>⭐️ Рейтинг: <b>8.69</b> • 🎭 Комедия, Школа",
          "7. 😂 <b>«Повседневная жизнь старшеклассников»</b><br>⭐️ Рейтинг: <b>8.23</b> • 🎭 Комедия, Повседневность",
          "8. 😂 <b>«Сатана на подработке!»</b> (Hataraku Maou)<br>⭐️ Рейтинг: <b>7.74</b> • 🎭 Комедия, Фэнтези",
          "9. 😂 <b>«Восхождение в тени!»</b> (Kage no Jitsuryokusha)<br>⭐️ Рейтинг: <b>8.24</b> • 🎭 Экшен, Пародия",
          "10. 😂 <b>«Семья шпиона»</b> (Spy x Family)<br>⭐️ Рейтинг: <b>8.48</b> • 🎭 Комедия, Экшен"
        ]
      },
      isekai_special: {
        title: "Захватывающие Исекаи и Попаданцы",
        banner: "https://s4.anilist.co/file/anilistcdn/media/anime/cover/large/bx108465-1ANspF1EWyFx.jpg",
        items: [
          "1. 🌀 <b>«Реинкарнация безработного»</b> (Mushoku Tensei)<br>⭐️ Рейтинг: <b>8.65</b> • 🎭 Магия, Приключения",
          "2. 🌀 <b>«Re:Zero — жизнь с нуля в другом мире»</b><br>⭐️ Рейтинг: <b>8.23</b> • 🎭 Триллер, Драма",
          "3. 🌀 <b>«О моём перерождении в слизь»</b> (Tensei Slime)<br>⭐️ Рейтинг: <b>8.12</b> • 🎭 Фэнтези, Сёнэн",
          "4. 🌀 <b>«Повелитель»</b> (Overlord)<br>⭐️ Рейтинг: <b>7.92</b> • 🎭 Фэнтези, Экшен",
          "5. 🌀 <b>«Восхождение героя щита»</b> (Tate no Yuusha)<br>⭐️ Рейтинг: <b>7.94</b> • 🎭 Драма, Фэнтези",
          "6. 🌀 <b>«Военная хроника маленькой девочки»</b> (Youjo Senki)<br>⭐️ Рейтинг: <b>7.96</b> • 🎭 Магия, Военное",
          "7. 🌀 <b>«Нет игры — нет жизни»</b> (No Game No Life)<br>⭐️ Рейтинг: <b>8.08</b> • 🎭 Игры, Комедия",
          "8. 🌀 <b>«Да, я паук, и что же?»</b> (Kumo desu ga)<br>⭐️ Рейтинг: <b>7.39</b> • 🎭 Экшен, Фэнтези",
          "9. 🌀 <b>«Непризнанный школой владыка демонов»</b><br>⭐️ Рейтинг: <b>7.35</b> • 🎭 Магия, Фэнтези",
          "10. 🌀 <b>«Этот герой неуязвим, но очень осторожен»</b><br>⭐️ Рейтинг: <b>7.45</b> • 🎭 Комедия, Фэнтези"
        ]
      }
    };

    async function previewSelectedCompTheme(themeKey, refresh = false) {
      if (!themeKey || themeKey === 'auto') themeKey = 'must_watch';
      const count = parseInt(document.getElementById('compilationCountSelect')?.value || 4);

      const pText = document.getElementById('compPreviewText');
      const pImg = document.getElementById('compPreviewImg');
      const pTime = document.getElementById('compPreviewTime');

      if (pTime) {
        const now = new Date();
        pTime.textContent = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
      }

      // 1. Try fetching live preview from backend engine
      try {
        const url = `/api/compilation-preview?genre=${encodeURIComponent(themeKey)}&count=${count}&refresh=${refresh ? 1 : 0}`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          if (data.ok && data.caption_html) {
            if (pText) pText.innerHTML = data.caption_html;
            if (pImg && data.poster) pImg.src = data.poster;
            return;
          }
        }
      } catch (e) {
        // Fallback to local sample presets
      }

      // 2. Fallback with randomized rotation
      const theme = SAMPLE_THEMES[themeKey] || SAMPLE_THEMES.must_watch;
      let pool = [...theme.items];
      if (refresh) {
        pool.sort(() => Math.random() - 0.5);
      }
      const items = pool.slice(0, count);

      if (pImg) pImg.src = theme.banner;
      if (pText) {
        let html = `✨ <b>ТОП-${count}: ${theme.title}</b><br><br>`;
        html += `Отборная коллекция тайтлов для вашего идеального вечера:<br><br>`;
        html += items.join('<br><br>') + '<br><br>';
        html += `━━━━━━━━━━━━━━━<br>`;
        html += `💬 Обсудить подборку: @animevist_chat<br>`;
        html += `🍿 Приложение: AnimeVist v1.0<br><br>`;
        html += `#подборка #топаниме #animevist`;
        pText.innerHTML = html;
      }
    }

    function rerollCompilationPreview() {
      const g = document.getElementById('compilationGenreSelect').value;
      showToast("🎲 Подбираем новую выборку аниме...", "info", 1500);
      previewSelectedCompTheme(g, true);
    }

    function updateCustomPreview() {
      const text = document.getElementById('customText').value;
      const photo = document.getElementById('customPhoto').value.trim();
      const btnText = document.getElementById('customBtnText').value.trim();
      const btnUrl = document.getElementById('customBtnUrl').value.trim();

      const pText = document.getElementById('previewText');
      const pImgWrap = document.getElementById('previewImgWrap');
      const pImg = document.getElementById('previewImg');
      const pBtnWrap = document.getElementById('previewBtnWrap');
      const pBtn = document.getElementById('previewBtn');
      const pTime = document.getElementById('previewPostTime');

      if (pTime) {
        const now = new Date();
        pTime.textContent = now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0');
      }

      if (text) {
        let formatted = text
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/&lt;b&gt;(.*?)&lt;\\/b&gt;/gi, '<b>$1</b>')
          .replace(/&lt;i&gt;(.*?)&lt;\\/i&gt;/gi, '<i>$1</i>')
          .replace(/&lt;tg-spoiler&gt;(.*?)&lt;\\/tg-spoiler&gt;/gi, '<span style="background:#334155; filter:blur(3px); cursor:pointer;" onclick="this.style.filter=\'none\'">$1</span>')
          .replace(/&lt;blockquote&gt;([\\s\\S]*?)&lt;\\/blockquote&gt;/gi, '<blockquote>$1</blockquote>')
          .replace(/&lt;a href=["\'](.*?)["\']&gt;(.*?)&lt;\\/a&gt;/gi, '<a href="$1" target="_blank">$2</a>')
          .replace(/\\n/g, '<br>');
        pText.innerHTML = formatted;
      } else {
        pText.innerHTML = '<span style="color:var(--text-muted); font-style:italic;">Текст вашего сообщения появится здесь...</span>';
      }

      if (photo && (photo.startsWith('http://') || photo.startsWith('https://'))) {
        pImg.src = photo;
        if (pImgWrap) pImgWrap.style.display = 'block';
        pImg.style.display = 'block';
      } else {
        if (pImgWrap) pImgWrap.style.display = 'none';
        pImg.style.display = 'none';
      }

      if (btnText) {
        pBtn.innerText = btnText;
        pBtn.href = btnUrl || '#';
        if (pBtnWrap) pBtnWrap.style.display = 'block';
      } else {
        if (pBtnWrap) pBtnWrap.style.display = 'none';
      }
    }

    async function sendCustomPost() {
      const text = document.getElementById('customText').value.trim();
      if (!text) {
        showToast("Введите текст публикации", "error");
        return;
      }
      const photo = document.getElementById('customPhoto').value.trim();
      const btnText = document.getElementById('customBtnText').value.trim();
      const btnUrl = document.getElementById('customBtnUrl').value.trim();

      showToast("Отправка кастомного поста в канал...", "info");
      try {
        const res = await fetch('/api/custom-post', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            text: text,
            photo_url: photo,
            btn_text: btnText,
            btn_url: btnUrl
          })
        });
        const data = await res.json();
        if (data.ok) {
          showToast("Пост успешно опубликован в канале!", "success");
          document.getElementById('customText').value = '';
          updateCustomPreview();
        } else {
          showToast(`Ошибка: ${data.error}`, "error");
        }
        setTimeout(fetchLogsOnly, 1000);
      } catch (e) {
        showToast("Ошибка при отправке поста", "error");
      }
    }

    async function sendTestMessage() {
      showToast("Отправка проверочного сообщения в Telegram...", "info");
      try {
        const res = await fetch('/api/test-message', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
          showToast("Сообщение успешно доставлено в канал!", "success");
        } else {
          showToast(`Ошибка отправки: ${data.error}`, "error");
        }
        setTimeout(fetchLogsOnly, 800);
      } catch (e) {
        showToast("Сетевая ошибка при отправке", "error");
      }
    }

    async function autoDetectChannel() {
      showToast("Поиск ID канала в обновлениях бота...", "info");
      try {
        const res = await fetch('/api/auto-detect-channel', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
          showToast(`Канал найден: ${data.title} (${data.chat_id})`, "success");
          document.getElementById('cfg_channel').value = data.chat_id;
          saveSettings();
        } else {
          showToast(data.error, "error", 5000);
        }
      } catch (e) {
        showToast("Ошибка при авто-детектировании", "error");
      }
    }

    async function saveSettings() {
      const payload = {
        bot_token: document.getElementById('cfg_token').value.trim(),
        channel_id: document.getElementById('cfg_channel').value.trim(),
        chat_invite_url: document.getElementById('cfg_chat').value.trim(),
        admin_id: document.getElementById('cfg_admin').value.trim(),
        interval: parseInt(document.getElementById('cfg_interval').value) || 300,
        enable_releases: document.getElementById('cfg_releases_enabled').checked,
        enable_news: document.getElementById('cfg_news_enabled').checked,
        enable_compilations: document.getElementById('cfg_compilations_enabled').checked,
        include_genre_hashtags: document.getElementById('cfg_genre_hashtags_enabled').checked,
        show_chat_button: document.getElementById('cfg_chat_button_enabled').checked,
        compilations_interval_hours: parseFloat(document.getElementById('cfg_comp_hours').value) || 6,
        cloud_storage: {
          provider: 'supabase',
          supabase_url: document.getElementById('storage_supabase_url').value.trim(),
          supabase_key: document.getElementById('storage_supabase_key').value.trim()
        }
      };

      try {
        const res = await fetch('/api/save-config', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.ok) {
          showToast("Конфигурация успешно сохранена!", "success");
          loadData();
        } else {
          showToast(`Ошибка сохранения: ${data.error}`, "error");
        }
      } catch (e) {
        showToast("Сетевая ошибка сохранения", "error");
      }
    }

    async function syncCloudNow() {
      showToast("Синхронизация с Supabase...", "info");
      try {
        const res = await fetch('/api/cloud-sync', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
          showToast("Бэкап успешно загружен в Supabase!", "success");
          loadData();
        } else {
          showToast(`Ошибка: ${data.error}`, "error", 5000);
        }
      } catch (e) {
        showToast("Ошибка синхронизации", "error");
      }
    }

    async function fetchCloudNow() {
      if (!confirm("Восстановить настройки из базы Supabase?")) return;
      showToast("Загрузка из Supabase...", "info");
      try {
        const res = await fetch('/api/cloud-fetch', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
          showToast("Настройки успешно восстановлены из Supabase!", "success");
          loadData();
        } else {
          showToast(`Ошибка: ${data.error}`, "error", 5000);
        }
      } catch (e) {
        showToast("Ошибка загрузки", "error");
      }
    }

    async function testSupabaseConnection() {
      showToast("Проверка связи с вашей базой Supabase...", "info");
      try {
        const res = await fetch('/api/test-supabase', { method: 'POST' });
        const data = await res.json();
        if (data.ok) {
          showToast("✅ Supabase успешно отвечает! (HTTP 200)", "success", 4000);
        } else {
          showToast(`❌ Ошибка Supabase: ${data.error}`, "error", 5000);
        }
      } catch (e) {
        showToast("Ошибка запроса к Supabase", "error");
      }
    }

    async function toggleDaemon() {
      try {
        const res = await fetch('/api/toggle-daemon', { method: 'POST' });
        const data = await res.json();
        if (data.paused) {
          showToast("Фоновый демон приостановлен", "info");
          document.getElementById('kpiDaemonStatus').innerText = "Пауза";
          document.getElementById('kpiDaemonStatus').style.color = "var(--warning)";
        } else {
          showToast("Фоновый демон возобновлен", "success");
          document.getElementById('kpiDaemonStatus').innerText = "Активен";
          document.getElementById('kpiDaemonStatus').style.color = "var(--success)";
        }
      } catch (e) {
        showToast("Ошибка переключения демона", "error");
      }
    }

    window.onload = () => {
      loadData();
      setInterval(fetchLogsOnly, 4000);
      previewSelectedCompTheme('must_watch');
      updateCustomPreview();

      const customArea = document.getElementById('customText');
      if (customArea) {
        customArea.addEventListener('keydown', (e) => {
          if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') {
            e.preventDefault();
            insertTag('customText', 'b');
          } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'i') {
            e.preventDefault();
            insertTag('customText', 'i');
          }
        });
      }
    };
  </script>
</body>
</html>
"""

class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
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

            last_comp = load_last_compilation_time()
            comp_hours = float(config.get('announcer', {}).get('compilations_interval_hours', 6))
            next_comp_sec = max(0, int((last_comp + comp_hours * 3600) - time.time())) if last_comp > 0 else 0

            resp = {
                "bot": cached_bot_info,
                "chat": cached_chat_info,
                "member_count": cached_member_count,
                "stats": {
                    "episodes": episodes_count,
                    "news": news_count,
                    "compilations": compilations_count
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
            from compilations_announcer import get_compilation_preview
            prev = get_compilation_preview(genre_arg, count=count_arg, refresh=refresh_arg)
            self._send_json(prev)
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
            if 'chat_invite_url' in data: app['chat_invite_url'] = data['chat_invite_url']
            if 'admin_id' in data: tg['admin_id'] = data['admin_id']
            if 'interval' in data: ann['check_interval_seconds'] = int(data['interval'])
            if 'enable_releases' in data: ann['enable_series_releases'] = bool(data['enable_releases'])
            if 'enable_news' in data: ann['enable_anime_news'] = bool(data['enable_news'])
            if 'enable_compilations' in data: ann['enable_compilations'] = bool(data['enable_compilations'])
            if 'include_genre_hashtags' in data: ann['include_genre_hashtags'] = bool(data['include_genre_hashtags'])
            if 'show_chat_button' in data: ann['show_chat_button'] = bool(data['show_chat_button'])
            if 'compilations_interval_hours' in data: ann['compilations_interval_hours'] = float(data['compilations_interval_hours'])

            if 'cloud_storage' in data and isinstance(data['cloud_storage'], dict):
                cloud.update(data['cloud_storage'])

            save_config(config, sync_to_cloud=True)
            log_event("Конфигурация успешно обновлена через веб-интерфейс", "success")
            self._send_json({"ok": True})

        elif path == "/api/test-message":
            config = load_config()
            sender = TelegramSender()
            channel = config.get('telegram', {}).get('channel_id')
            custom_text = data.get('text')
            disable_preview = data.get('disable_preview', False)

            if custom_text:
                msg_text = custom_text
            else:
                msg_text = (
                    "🤖 <b>AnimeVist — Тест подключения!</b>\n\n"
                    "Панель управления и бот успешно настроены и подключены к каналу."
                )

            res = sender.send_message(msg_text, chat_id=channel, disable_preview=disable_preview)
            if res.get('ok'):
                log_event("Сообщение успешно доставлено в канал", "success")
                self._send_json({"ok": True})
            else:
                desc = res.get('description', 'Неизвестная ошибка Telegram API')
                log_event(f"Ошибка отправки сообщения: {desc}", "error")
                self._send_json({"ok": False, "error": desc})

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
            if res.get('ok'):
                log_event("Резервная копия настроек успешно загружена в облако", "success")
            else:
                log_event(f"Ошибка облачной синхронизации: {res.get('error')}", "error")
            self._send_json(res)

        elif path == "/api/cloud-fetch":
            config = load_config()
            provider = config.get('cloud_storage', {}).get('provider', 'supabase')
            if provider == 'supabase':
                res = fetch_config_from_supabase(config)
            elif provider == 'telegram':
                res = fetch_config_from_telegram(config)
            else:
                res = fetch_config_from_supabase(config)
            
            if res.get('ok'):
                log_event("Настройки успешно восстановлены из облака", "success")
            else:
                log_event(f"Ошибка восстановления: {res.get('error')}", "error")
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
                except Exception as e:
                    log_event(f"Ошибка выполнения действия [{action_name}]: {e}", "error")

            threading.Thread(target=run_bg, args=(act, genre, count), daemon=True).start()
            self._send_json({"ok": True})
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
        if env_port:
            preferred_port = int(env_port)
            ports_to_try = [preferred_port, 5000, 7860, 5001, 8080]
        else:
            ports_to_try = [5000, 7860, 5001, 8080]
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
    print(f"  🎬 ANIME VIST — КОНСОЛЬ УПРАВЛЕНИЯ БОТОМ ЗАПУЩЕНА (24/7)")
    print(f"  🌐 Локальный веб-интерфейс: http://localhost:{actual_port}")
    print(f"================================================================\n")
    log_event(f"Веб-сервер активен на порту {actual_port}", "info")

    import webbrowser
    def open_browser():
        time.sleep(0.8)
        try:
            webbrowser.open(f"http://localhost:{actual_port}")
        except Exception:
            pass
    threading.Thread(target=open_browser, daemon=True).start()

    # Start 24/7 background worker thread
    global daemon_thread
    daemon_thread = threading.Thread(target=background_monitoring_worker, daemon=True)
    daemon_thread.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nОстановка сервера...")
        server.server_close()

if __name__ == '__main__':
    start_server()

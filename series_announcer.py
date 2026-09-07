"""
Standalone AnimeVist Series Auto Announcer.
Monitors AnimeVost & Shikimori APIs for newly released episodes
and publishes rich cards with posters and genre navigation to Telegram (#онгоинг).
"""

import os
import sys
import re
import json
import time
import urllib.request
import urllib.parse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram_sender import (
    TelegramSender,
    load_config,
    load_seen_from_supabase,
    save_seen_to_supabase
)

SEEN_FILE = os.path.join(os.path.dirname(__file__), 'seen_episodes.json')

def load_seen_episodes():
    seen = set()
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, 'r', encoding='utf-8') as f:
                seen.update(json.load(f))
        except Exception:
            pass
    try:
        remote_seen = load_seen_from_supabase(category='episode')
        seen.update(remote_seen)
    except Exception:
        pass
    return seen

def save_seen_episodes(seen_set):
    try:
        with open(SEEN_FILE, 'w', encoding='utf-8') as f:
            items = list(seen_set)[-1000:]
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    try:
        save_seen_to_supabase(seen_set, category='episode')
    except Exception:
        pass

def clean_title(raw):
    cleaned = re.sub(r'\[.*?\]', '', raw).strip()
    parts = [p.strip() for p in cleaned.split('/')]
    ru = parts[0] if len(parts) > 0 else raw
    eng = parts[1] if len(parts) > 1 else ''
    return ru, eng

def extract_latest_episode_num(raw_title, series_data):
    """
    Extracts the true latest episode number.
    Prioritizes actual uploaded episode keys from series_data to avoid internal video CDN IDs,
    and uses title brackets as a reliable secondary source.
    """
    # 1. Check keys in series_data (AnimeVost keys e.g. '1 серия', '10 серия')
    series_keys_nums = []
    if isinstance(series_data, dict):
        for k in series_data.keys():
            m = re.search(r'(\d+)', str(k))
            if m:
                val = int(m.group(1))
                if 0 < val < 2000:
                    series_keys_nums.append(val)
    elif isinstance(series_data, str) and series_data.strip():
        # Match keys before colon in json-like string: '10 серия': '1460465236'
        key_matches = re.findall(r"['\"`](\d+)[^'\"`:]*?['\"`]\s*:", series_data)
        for k in key_matches:
            val = int(k)
            if 0 < val < 2000:
                series_keys_nums.append(val)

    if series_keys_nums:
        return max(series_keys_nums)

    # 2. Fallback: Parse bracket contents in raw_title
    bracket_matches = re.findall(r'\[(.*?)\]', raw_title)
    for b in bracket_matches:
        # Ignore future schedule brackets e.g. [11 серия - 12 сентября]
        if '-' in b and any(m in b.lower() for m in ['янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек', '202']):
            continue
        # Check patterns like [1-10 из 12], [10 из 12], [10 серия]
        m = re.search(r'(?:^|\D)(?:\d+\s*-\s*)?(\d+)\s*(?:из|серия|эп|\/|$)', b, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 0 < val < 2000:
                return val

    return 1

def resolve_best_poster(shiki_poster, vost_poster):
    """
    Ensures no '404 not found' Shikimori placeholder images are ever published.
    Falls back to high-resolution direct poster from AnimeVost.
    """
    if shiki_poster and isinstance(shiki_poster, str):
        low = shiki_poster.lower()
        if 'missing' not in low and '404' not in low and low.startswith('http'):
            return shiki_poster
    if vost_poster and isinstance(vost_poster, str):
        if not vost_poster.startswith('http'):
            return f"https://animevost.org{vost_poster}"
        return vost_poster
    return "https://raw.githubusercontent.com/magver/AnimeVist/main/assets/banner.png"

def format_genre_hashtags(genre_str, ep_num=None, app_name='AnimeVist'):
    """
    Generates Russian genre navigation hashtags for rapid filtering in Telegram.
    """
    tags = []
    if genre_str:
        raw_items = re.split(r'[,/]', str(genre_str))
        for raw in raw_items:
            clean = re.sub(r'[^\w\s]', '', raw.strip()).lower().replace(' ', '_')
            if clean and len(clean) > 2 and clean not in tags:
                if clean in ('сенен', 'сенён'): clean = 'сёнэн'
                elif clean in ('седзе', 'сёдзе'): clean = 'сёдзё'
                elif clean == 'психологическое': clean = 'психология'
                tags.append(f"#{clean}")

    # Cap genres to top 4
    tags = tags[:4]

    if ep_num:
        tags.append(f"#серия{ep_num}")
    tags.append("#онгоинг")
    tags.append(f"#{app_name.lower()}")
    return " ".join(tags)

def fetch_shikimori_info(title):
    try:
        search_query = urllib.parse.quote(title)
        url = f"https://shikimori.one/api/animes?search={search_query}&limit=1"
        req = urllib.request.Request(url, headers={'User-Agent': 'AnimeVistBot/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and len(data) > 0:
                first = data[0]
                shiki_id = first.get('id')
                detail_url = f"https://shikimori.one/api/animes/{shiki_id}"
                req2 = urllib.request.Request(detail_url, headers={'User-Agent': 'AnimeVistBot/1.0'})
                with urllib.request.urlopen(req2, timeout=5) as resp2:
                    details = json.loads(resp2.read().decode('utf-8'))
                    poster_path = details.get('image', {}).get('original', '')
                    poster_url = f"https://shikimori.one{poster_path}" if poster_path else None
                    rating = details.get('score', '—')
                    genres = ", ".join([g.get('russian') or g.get('name') for g in details.get('genres', [])[:5]])
                    return {
                        'poster': poster_url,
                        'rating': rating,
                        'genres': genres
                    }
    except Exception:
        pass
    return None

def fetch_latest_episodes():
    url = "https://api.animevost.org/v1/last?page=1&quantity=15"
    req = urllib.request.Request(url, headers={'User-Agent': 'AnimeVistBot/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            res = json.loads(resp.read().decode('utf-8'))
            return res.get('data', [])
    except Exception as e:
        print(f"[Announcer] Error fetching AnimeVost: {e}")
        return []

def run_series_check(dry_run=False):
    config = load_config()
    sender = TelegramSender()
    seen = load_seen_episodes()

    items = fetch_latest_episodes()
    if not items:
        print("[Announcer] No items fetched.")
        return 0

    max_per_cycle = config.get('announcer', {}).get('max_releases_per_cycle', 3)
    published_count = 0

    # Seed on first run if empty
    if len(seen) == 0:
        print("[Announcer] Initializing seen_episodes database with current releases (first run)...")
        for it in items:
            ep_num = extract_latest_episode_num(it.get('title', ''), it.get('series'))
            seen.add(f"{it.get('id')}_{ep_num}")
        save_seen_episodes(seen)
        print("[Announcer] Initialization complete. Future new episodes will be posted automatically.")
        return 0

    for it in items:
        if published_count >= max_per_cycle:
            break

        vost_id = it.get('id')
        raw_title = it.get('title', '')
        title_ru, title_eng = clean_title(raw_title)
        latest_ep_num = extract_latest_episode_num(raw_title, it.get('series'))

        ep_key = f"{vost_id}_{latest_ep_num}"
        if ep_key in seen:
            continue

        print(f"[Announcer] Новая серия обнаружена: {title_ru} ({latest_ep_num} серия)")

        shiki_info = fetch_shikimori_info(title_ru)
        rating_str = shiki_info.get('rating', '—') if shiki_info else '—'
        genres_str = (shiki_info.get('genres') if shiki_info else None) or it.get('genre') or 'Аниме, Приключения'
        
        poster_url = resolve_best_poster(
            shiki_info.get('poster') if shiki_info else None,
            it.get('urlImagePreview')
        )

        app_name = config.get('app', {}).get('name', 'AnimeVist')
        hashtags = format_genre_hashtags(genres_str, latest_ep_num, app_name)

        eng_sub = f"🎬 <i>{title_eng}</i>\n\n" if title_eng else "\n"
        caption = (
            f"🔥 <b>Вышла {latest_ep_num} серия «{title_ru}»!</b>\n"
            f"{eng_sub}"
            f"⭐️ <b>Рейтинг:</b> {rating_str} / 10\n"
            f"🎭 <b>Жанры:</b> {genres_str}\n\n"
            f"🎙 <b>Доступно в {app_name}:</b>\n"
            f"• ⚡ <b>AnimeVost</b> (Прямой поток 1080p/720p без задержек)\n"
            f"• 💬 <b>Субтитры & Озвучка</b> (по мере выхода релиз-групп)\n\n"
            f"✨ <i>Смотрите без рекламы, со сквозной синхронизацией ПК ↔ Android и автопропуском опенингов!</i>\n\n"
            f"{hashtags}"
        )

        # Buttons configuration:
        # User requested: remove 'Смотреть в AnimeVist'.
        # Show 'Обсудить серию' only if enabled in settings and URL is configured.
        reply_markup = None
        show_chat = config.get('announcer', {}).get('show_chat_button', False)
        chat_url = config.get('app', {}).get('chat_invite_url', '').strip()
        if show_chat and chat_url and chat_url.startswith('http'):
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "💬 Обсудить серию в чате", "url": chat_url}
                    ]
                ]
            }

        if dry_run:
            print("[DRY-RUN] Preview:")
            print(caption)
            print("Poster:", poster_url)
            print("Hashtags:", hashtags)
            print("Reply markup:", reply_markup)
        else:
            res = sender.send_photo(poster_url, caption=caption, reply_markup=reply_markup)
            if res.get('ok'):
                print(f"[Announcer] ✅ Опубликовано: {ep_key}")
            else:
                print(f"[Announcer] ❌ Ошибка публикации: {res.get('description')}")
            seen.add(ep_key)
            save_seen_episodes(seen)

        published_count += 1
        time.sleep(1)

    return published_count

if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    run_series_check(dry_run=dry)

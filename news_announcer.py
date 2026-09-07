"""
Standalone AnimeVist Multi-Source Anime News Announcer.
Aggregates news, trailers, official announcements, industry reports,
and insider rumors from Shikimori, MyAnimeList, and Anime News Network.
Publishes rich cards with badges and categorized hashtags to Telegram (#новости).
"""

import os
import sys
import re
import json
import time
import html
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

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

SEEN_NEWS_FILE = os.path.join(os.path.dirname(__file__), 'seen_news.json')

def load_seen_news():
    seen = set()
    if os.path.exists(SEEN_NEWS_FILE):
        try:
            with open(SEEN_NEWS_FILE, 'r', encoding='utf-8') as f:
                seen.update(json.load(f))
        except Exception:
            pass
    try:
        remote_seen = load_seen_from_supabase(category='news')
        seen.update(remote_seen)
    except Exception:
        pass
    return seen

def save_seen_news(seen_set):
    try:
        with open(SEEN_NEWS_FILE, 'w', encoding='utf-8') as f:
            items = list(seen_set)[-500:]
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    try:
        save_seen_to_supabase(seen_set, category='news')
    except Exception:
        pass

def translate_to_ru(text):
    """
    Translates English text to Russian via Google Translate free endpoint.
    Skips if text already has significant Cyrillic content.
    """
    if not text or not text.strip():
        return text
    cyrillic_chars = len(re.findall(r'[а-яА-ЯёЁ]', text))
    if cyrillic_chars > len(text) * 0.25:
        return text
    try:
        q = urllib.parse.quote(text[:750])
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=ru&dt=t&q={q}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and data[0]:
                translated = "".join([part[0] for part in data[0] if part[0]])
                return translated.strip()
    except Exception:
        pass
    return text

def strip_markup(text):
    if not text:
        return ""
    # Strip BBCode
    text = re.sub(r'\[.*?\]', '', text)
    # Strip HTML tags
    text = re.sub(r'<.*?>', '', text)
    text = html.unescape(text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def categorize_news(title, body):
    combined = (title + " " + body).lower()
    if any(k in combined for k in ['тизер', 'трейлер', 'promo', 'trailer', 'teaser', 'pv', 'ролик', 'видео']):
        return "🎬 <b>Трейлер & Промо</b>", "#трейлер #анонс"
    elif any(k in combined for k in ['слух', 'инсайд', 'утечка', 'утек', 'rumor', 'leak', 'reportedly', 'инсайдер']):
        return "⚡ <b>Слухи & Инсайды</b>", "#слухи #инсайды"
    elif any(k in combined for k in ['премьер', 'дата выхода', 'стартует', 'выйдет', 'premiere', 'release date', 'дебют']):
        return "📅 <b>Даты & Премьеры</b>", "#дата_выхода #премьера"
    elif any(k in combined for k in ['студия', 'каст', 'сэйю', 'режиссер', 'производств', 'studio', 'cast', 'staff', 'mappa', 'wit', 'ufotable']):
        return "🎙 <b>Студии & Индустрия</b>", "#индустрия #студии"
    elif any(k in combined for k in ['анонсирован', 'экранизац', 'новый сезон', 'announced', 'adaptation', 'season']):
        return "✨ <b>Официальный анонс</b>", "#анонс #новинки"
    return "📰 <b>Новости Аниме</b>", "#новости #индустрия"

def fetch_shikimori_news(limit=4):
    items = []
    headers = {'User-Agent': 'AnimeVistBot/1.0'}
    for forum in ['news', 'animanga']:
        url = f"https://shikimori.one/api/topics?forum={forum}&limit={limit}"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=6) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                for t in data:
                    t_id = f"shiki_{t.get('id')}"
                    title = strip_markup(t.get('topic_title', ''))
                    body = strip_markup(t.get('body', ''))
                    
                    img = None
                    linked = t.get('linked') or {}
                    if isinstance(linked, dict) and linked.get('image'):
                        orig = linked['image'].get('original')
                        if orig and 'missing' not in orig:
                            img = f"https://shikimori.one{orig}"

                    items.append({
                        'id': t_id,
                        'title': title,
                        'body': body,
                        'image': img,
                        'source_url': f"https://shikimori.one/forum/{forum}/{t.get('id')}",
                        'source': 'Shikimori'
                    })
        except Exception as e:
            print(f"[News] Shikimori error ({forum}): {e}")
    return items

def fetch_mal_news(limit=3):
    items = []
    url = "https://myanimelist.net/rss/news.xml"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            root = ET.fromstring(resp.read())
            for it in root.findall('.//item')[:limit]:
                link = it.find('link').text if it.find('link') is not None else ''
                t_id = f"mal_{link.split('/')[-1].split('?')[0]}"
                title_en = it.find('title').text if it.find('title') is not None else ''
                desc_en = it.find('description').text if it.find('description') is not None else ''
                
                title_ru = translate_to_ru(strip_markup(title_en))
                desc_ru = translate_to_ru(strip_markup(desc_en)[:450])
                
                img = None
                thumb = it.find('{http://search.yahoo.com/mrss/}thumbnail')
                if thumb is not None and thumb.text:
                    img = thumb.text.strip()

                items.append({
                    'id': t_id,
                    'title': title_ru,
                    'body': desc_ru,
                    'image': img,
                    'source_url': link,
                    'source': 'MyAnimeList'
                })
    except Exception as e:
        print(f"[News] MAL error: {e}")
    return items

def fetch_ann_news(limit=3):
    items = []
    url = "https://www.animenewsnetwork.com/news/rss.xml"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            root = ET.fromstring(resp.read())
            for it in root.findall('.//item')[:limit]:
                link = it.find('link').text if it.find('link') is not None else ''
                slug = link.strip('/').split('/')[-1].split('.')[0]
                t_id = f"ann_{slug}"
                title_en = it.find('title').text if it.find('title') is not None else ''
                desc_en = it.find('description').text if it.find('description') is not None else ''
                
                title_ru = translate_to_ru(strip_markup(title_en))
                desc_ru = translate_to_ru(strip_markup(desc_en)[:450])

                items.append({
                    'id': t_id,
                    'title': title_ru,
                    'body': desc_ru,
                    'image': None,
                    'source_url': link,
                    'source': 'Anime News Network'
                })
    except Exception as e:
        print(f"[News] ANN error: {e}")
    return items

def collect_multi_source_news():
    """
    Aggregates news from all configured sources:
    Shikimori (native RU), MyAnimeList (with images & RU translate), ANN (with RU translate).
    """
    all_news = []
    # 1. Shikimori
    all_news.extend(fetch_shikimori_news(limit=4))
    # 2. MyAnimeList
    all_news.extend(fetch_mal_news(limit=3))
    # 3. ANN
    all_news.extend(fetch_ann_news(limit=2))
    return all_news

def run_news_check(dry_run=False):
    config = load_config()
    sender = TelegramSender()
    seen = load_seen_news()

    news_items = collect_multi_source_news()
    if not news_items:
        print("[News] No news fetched.")
        return 0

    # Seed on first run if database is empty
    if len(seen) == 0:
        print("[News] Initializing seen_news database with recent topics (first run)...")
        for item in news_items:
            seen.add(item['id'])
        save_seen_news(seen)
        print("[News] Initialized. Future new anime announcements will be posted automatically.")
        return 0

    published_count = 0
    max_per_cycle = 2

    for item in news_items:
        if published_count >= max_per_cycle:
            break

        item_id = item['id']
        if item_id in seen:
            continue

        title = item.get('title', 'Новость из мира аниме')
        body = item.get('body', '')
        if len(body) > 420:
            body = body[:417] + '...'

        badge, category_tags = categorize_news(title, body)
        app_name = config.get('app', {}).get('name', 'AnimeVist')

        caption = (
            f"{badge}\n\n"
            f"📌 <b>{title}</b>\n\n"
            f"{body}\n\n"
            f"💬 <i>Что думаете об этой новости? Делитесь в комментариях!</i>\n\n"
            f"#новости {category_tags} #{app_name.lower()}"
        )

        image_url = item.get('image')
        source_url = item.get('source_url')

        # Inline button: Link to original source article
        reply_markup = None
        keyboard = []
        if source_url and source_url.startswith('http'):
            keyboard.append([{"text": f"🌐 Подробнее ({item.get('source')})", "url": source_url}])
        
        # Optional chat button
        show_chat = config.get('announcer', {}).get('show_chat_button', False)
        chat_url = config.get('app', {}).get('chat_invite_url', '').strip()
        if show_chat and chat_url and chat_url.startswith('http'):
            keyboard.append([{"text": "💬 Обсудить в чате", "url": chat_url}])

        if keyboard:
            reply_markup = {"inline_keyboard": keyboard}

        print(f"[News] Новая новость ({item.get('source')}): {title[:60]}")

        if dry_run:
            print("[DRY-RUN] Preview:")
            print(caption)
            print("Image:", image_url)
            print("Reply markup:", reply_markup)
        else:
            if image_url:
                res = sender.send_photo(image_url, caption=caption, reply_markup=reply_markup)
            else:
                res = sender.send_message(caption, reply_markup=reply_markup)

            if res.get('ok'):
                print(f"[News] ✅ Опубликовано: {item_id}")
            else:
                print(f"[News] ❌ Ошибка: {res.get('description')}")

            seen.add(item_id)
            save_seen_news(seen)

        published_count += 1
        time.sleep(2)

    return published_count

if __name__ == '__main__':
    dry = '--dry-run' in sys.argv
    run_news_check(dry_run=dry)

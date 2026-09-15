import os
import json
import time
import re
from typing import Dict, List, Optional, Tuple

from telegram_sender import TelegramSender, load_config
from user_auth import get_user_subscriptions, update_user_subscription
from series_announcer import (
    fetch_latest_episodes,
    extract_latest_episode_num,
    clean_title,
    resolve_best_poster,
    format_genre_hashtags
)

COOLDOWN_CACHE_PATH = os.path.join(os.path.dirname(__file__), 'scratch', 'personal_user_cooldowns.json')

def load_user_cooldowns() -> Dict[str, float]:
    try:
        if os.path.exists(COOLDOWN_CACHE_PATH):
            with open(COOLDOWN_CACHE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def save_user_cooldown(tg_id: int, timestamp: Optional[float] = None) -> None:
    try:
        os.makedirs(os.path.dirname(COOLDOWN_CACHE_PATH), exist_ok=True)
        data = load_user_cooldowns()
        data[str(tg_id)] = timestamp or time.time()
        # Clean up entries older than 7 days
        cutoff = time.time() - (7 * 86400)
        cleaned = {k: v for k, v in data.items() if isinstance(v, (int, float)) and v >= cutoff}
        with open(COOLDOWN_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cleaned, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[PersonalNotifier] Error saving cooldown: {e}")

def is_in_quiet_hours(start_hour: int = 23, end_hour: int = 8) -> bool:
    """Check if current time is within quiet hours (MSK / UTC+3)."""
    msk_hour = time.gmtime(time.time() + 3 * 3600).tm_hour
    if start_hour > end_hour:
        # Crosses midnight, e.g. 23:00 to 08:00
        return msk_hour >= start_hour or msk_hour < end_hour
    elif start_hour < end_hour:
        # e.g. 01:00 to 07:00
        return start_hour <= msk_hour < end_hour
    return False

def normalize_title_for_match(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r'[^\w\s]', ' ', text.lower())
    return re.sub(r'\s+', ' ', cleaned).strip()

def find_matching_episode_for_sub(sub: Dict, latest_items: List[Dict], strict: bool = True) -> Optional[Dict]:
    sub_id = str(sub.get('anime_id', '')).strip().lower()
    sub_title = str(sub.get('anime_title', '')).strip()

    # Extract numeric part from sub_id (e.g. 'vost-3978' -> '3978')
    sub_num_match = re.search(r'\d+', sub_id)
    sub_num = sub_num_match.group(0) if sub_num_match else None

    norm_sub = normalize_title_for_match(sub_title)

    for item in latest_items:
        vost_id = str(item.get('id', '')).strip()
        raw_title = item.get('title', '')
        ru_title, eng_title = clean_title(raw_title)

        # 1. Exact ID match (highest confidence)
        if sub_id in [vost_id, f"vost-{vost_id}", f"shiki-{vost_id}"]:
            return item
        if sub_num and sub_num == vost_id:
            return item

        # 2. Title matching
        if norm_sub and len(norm_sub) >= 4:
            norm_ru = normalize_title_for_match(ru_title)
            norm_eng = normalize_title_for_match(eng_title)

            if strict:
                # Strict matching: require exact normalized match or high-ratio match
                if norm_sub == norm_ru or (norm_eng and norm_sub == norm_eng):
                    return item
                # Substring match only if the search string covers at least 75% of the target title
                if len(norm_ru) > 0 and norm_sub in norm_ru:
                    if len(norm_sub) / len(norm_ru) >= 0.75:
                        return item
            else:
                # Relaxed fallback
                if norm_sub in norm_ru or (norm_eng and norm_sub in norm_eng):
                    return item

    return None

def fetch_user_subscriptions_with_new_episodes(strict: bool = True) -> List[Dict]:
    """
    Check all active subscriptions in Supabase against AnimeVost latest releases.
    """
    subscriptions = get_user_subscriptions(active_only=True)
    if not subscriptions:
        return []

    latest_items = fetch_latest_episodes()
    if not latest_items:
        return []

    notifications = []
    for sub in subscriptions:
        tg_id = sub.get('telegram_user_id')
        if not tg_id:
            continue

        matched_item = find_matching_episode_for_sub(sub, latest_items, strict=strict)
        if not matched_item:
            continue

        current_ep = extract_latest_episode_num(matched_item.get('title', ''), matched_item.get('series'))
        last_notified = sub.get('last_notified_episode', 0)

        if current_ep > last_notified:
            new_count = current_ep - last_notified
            anime_id = sub.get('anime_id')
            poster = sub.get('anime_poster') or resolve_best_poster(None, matched_item.get('urlImagePreview'))

            ru_title, eng_title = clean_title(matched_item.get('title', ''))

            notifications.append({
                "telegram_user_id": tg_id,
                "animevist_user_id": sub.get('animevist_user_id'),
                "anime_id": anime_id,
                "anime_title": sub.get('anime_title') or ru_title,
                "title_en": eng_title,
                "poster_url": poster,
                "current_episode": current_ep,
                "new_episodes_count": new_count,
                "last_notified": last_notified,
                "matched_item": matched_item
            })

    return notifications

def create_personal_notification_message(notif: Dict) -> str:
    config = load_config()
    app_name = config.get('app', {}).get('name', 'AnimeVist')
    
    title = notif['anime_title']
    title_en = notif.get('title_en', '')
    ep = notif['current_episode']
    new_count = notif['new_episodes_count']
    matched = notif.get('matched_item', {})

    genres = matched.get('genre', 'Аниме')
    hashtags = format_genre_hashtags(genres, ep, app_name)

    ep_text = f"<b>{ep} серия</b>" if new_count <= 1 else f"<b>{ep} серия</b> (+{new_count} новых!)"

    msg = (
        f"🎬 <b>{title}</b>\n"
    )
    if title_en and title_en != title:
        msg += f"<i>{title_en}</i>\n\n"
    else:
        msg += "\n"

    msg += (
        f"🚀 Вышла {ep_text}!\n\n"
        f"📱 Откройте серию прямо сейчас в приложении <b>{app_name}</b> в 1080p без рекламы.\n\n"
        f"{hashtags}"
    )
    return msg

def create_notification_keyboard(anime_id: str, current_episode: int) -> Dict:
    clean_num = str(anime_id).replace('vost-', '')
    vost_key = f"vost-{clean_num}" if clean_num.isdigit() else str(anime_id)
    watch_url = f"https://magver.github.io/AnimeVist-Telegram-Bot/open.html?animeId={vost_key}&episode={current_episode}"

    return {
        "inline_keyboard": [
            [
                {"text": "▶️ Смотреть в приложении", "url": watch_url}
            ],
            [
                {"text": "✅ Отметить просмотренным", "callback_data": f"seen_{anime_id}_{current_episode}"},
                {"text": "🔕 Отписаться", "callback_data": f"unsub_{anime_id}"}
            ]
        ]
    }

def create_personal_digest_message(user_items: List[Dict]) -> Tuple[str, Dict]:
    config = load_config()
    app_name = config.get('app', {}).get('name', 'AnimeVist')
    count = len(user_items)

    msg = (
        f"🔔 <b>Свежие серии для вас ({count})</b>\n\n"
        f"В вашем списке «Смотрю» вышли новые серии:\n\n"
    )

    kb_rows = []
    for it in user_items[:5]:
        ep = it['current_episode']
        title = it['anime_title']
        a_id = it['anime_id']
        clean_num = str(a_id).replace('vost-', '')
        vost_key = f"vost-{clean_num}" if clean_num.isdigit() else str(a_id)
        watch_url = f"https://magver.github.io/AnimeVist-Telegram-Bot/open.html?animeId={vost_key}&episode={ep}"

        msg += f"• 🎬 <b>{title}</b> — <b>{ep} серия</b>\n"
        kb_rows.append([{"text": f"▶️ {title[:22]} ({ep} сер.)", "url": watch_url}])

    msg += (
        f"\n📱 Приятного просмотра в приложении <b>{app_name}</b> без рекламы!\n"
        f"<i>#анимевист #онгоинг #дайджест</i>"
    )

    return msg, {"inline_keyboard": kb_rows}

def send_personal_notifications() -> Dict:
    config = load_config()
    ann_conf = config.get('announcer', {})

    if not ann_conf.get('enable_personal_notifications', True):
        print("[PersonalNotifier] Персональные уведомления отключены в конфигурации.")
        return {"sent": 0, "failed": 0, "total": 0, "disabled": True}

    quiet_enabled = ann_conf.get('personal_quiet_hours_enabled', True)
    quiet_start = int(ann_conf.get('personal_quiet_hours_start', 23))
    quiet_end = int(ann_conf.get('personal_quiet_hours_end', 8))
    quiet_action = ann_conf.get('personal_quiet_action', 'skip')
    silent_always = ann_conf.get('personal_silent_notifications', False)

    silent_push = bool(silent_always)

    if quiet_enabled and is_in_quiet_hours(quiet_start, quiet_end):
        if quiet_action == 'skip':
            print(f"[PersonalNotifier] 🌙 Ночной тихий режим ({quiet_start}:00-{quiet_end}:00 МСК). Рассылка отложена.")
            return {"sent": 0, "failed": 0, "total": 0, "skipped_quiet_hours": True}
        elif quiet_action == 'silent':
            silent_push = True

    strict = ann_conf.get('personal_strict_matching', True)
    cooldown_hours = float(ann_conf.get('personal_user_cooldown_hours', 3.0))
    max_per_user = int(ann_conf.get('personal_max_episodes_per_user', 2))
    batch_digest = bool(ann_conf.get('personal_batch_digest', False))

    notifications = fetch_user_subscriptions_with_new_episodes(strict=strict)
    stats = {"sent": 0, "failed": 0, "total": len(notifications), "skipped_cooldown": 0}

    if not notifications:
        return stats

    # Group by telegram_user_id
    user_map: Dict[int, List[Dict]] = {}
    for n in notifications:
        user_map.setdefault(n["telegram_user_id"], []).append(n)

    cooldowns = load_user_cooldowns()
    now_ts = time.time()
    sender = TelegramSender()

    for tg_id, items in user_map.items():
        # Check cooldown
        last_sent = cooldowns.get(str(tg_id), 0)
        if cooldown_hours > 0 and (now_ts - last_sent) < (cooldown_hours * 3600):
            stats["skipped_cooldown"] += len(items)
            continue

        try:
            if batch_digest and len(items) > 1:
                # Send single composite digest
                msg, keyboard = create_personal_digest_message(items)
                first_poster = items[0].get("poster_url")
                if first_poster and first_poster.startswith("http"):
                    res = sender.send_photo(first_poster, caption=msg, chat_id=tg_id, reply_markup=keyboard, disable_notification=silent_push)
                else:
                    res = sender.send_message(msg, chat_id=tg_id, reply_markup=keyboard, disable_notification=silent_push)

                if res.get("ok"):
                    stats["sent"] += 1
                    save_user_cooldown(tg_id, now_ts)
                    for it in items:
                        update_user_subscription(
                            telegram_user_id=tg_id,
                            animevist_user_id=it.get("animevist_user_id"),
                            anime_id=it["anime_id"],
                            anime_title=it["anime_title"],
                            anime_poster=it.get("poster_url"),
                            last_notified_episode=it["current_episode"],
                            active=True
                        )
                else:
                    stats["failed"] += 1
                    print(f"[PersonalNotifier] Error sending digest to {tg_id}: {res.get('description')}")
                time.sleep(0.3)
            else:
                # Send individual posts limited to max_per_user
                items_to_send = items[:max_per_user]
                sent_any = False
                for notif in items_to_send:
                    caption = create_personal_notification_message(notif)
                    keyboard = create_notification_keyboard(notif["anime_id"], notif["current_episode"])
                    poster_url = notif.get("poster_url")

                    if poster_url and poster_url.startswith("http"):
                        res = sender.send_photo(poster_url, caption=caption, chat_id=tg_id, reply_markup=keyboard, disable_notification=silent_push)
                    else:
                        res = sender.send_message(caption, chat_id=tg_id, reply_markup=keyboard, disable_notification=silent_push)

                    if res.get("ok"):
                        stats["sent"] += 1
                        sent_any = True
                        update_user_subscription(
                            telegram_user_id=tg_id,
                            animevist_user_id=notif.get("animevist_user_id"),
                            anime_id=notif["anime_id"],
                            anime_title=notif["anime_title"],
                            anime_poster=poster_url,
                            last_notified_episode=notif["current_episode"],
                            active=True
                        )
                    else:
                        stats["failed"] += 1
                        print(f"[PersonalNotifier] Error sending to {tg_id}: {res.get('description')}")

                    time.sleep(0.3)

                if sent_any:
                    save_user_cooldown(tg_id, now_ts)

        except Exception as e:
            stats["failed"] += 1
            print(f"[PersonalNotifier] Exception for user {tg_id}: {e}")

    return stats

def run_notification_cycle(dry_run: bool = False) -> Dict:
    now_str = time.strftime('%H:%M:%S')
    if dry_run:
        config = load_config()
        strict = config.get('announcer', {}).get('personal_strict_matching', True)
        notifications = fetch_user_subscriptions_with_new_episodes(strict=strict)
        print(f"[{now_str}] [PersonalNotifier] [DRY RUN] Found {len(notifications)} notifications")
        return {"dry_run": True, "count": len(notifications)}
    else:
        stats = send_personal_notifications()
        print(f"[{now_str}] [PersonalNotifier] Sent: {stats.get('sent', 0)}, Failed: {stats.get('failed', 0)}, Skipped: {stats.get('skipped_cooldown', 0)}")
        return {"dry_run": False, "stats": stats}

if __name__ == "__main__":
    import sys
    dry = "--dry-run" in sys.argv or "--test" in sys.argv
    res = run_notification_cycle(dry_run=dry)
    print(res)
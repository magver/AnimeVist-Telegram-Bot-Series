"""
Personal Notifier for AnimeVist Telegram Bot
Sends personal notifications to users about new episodes
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, List, Optional

from telegram_sender import TelegramSender, load_config
from user_auth import get_user_subscriptions, update_user_subscription
from series_announcer import fetch_latest_episodes, extract_latest_episode_num, clean_title, resolve_best_poster, format_genre_hashtags

def fetch_user_subscriptions_with_new_episodes():
    """
    Check all user subscriptions for anime with new episodes
    Returns list of subscriptions that need notifications
    """
    config = load_config()
    app_name = config['app']['name']
    
    # Get all active subscriptions
    subscriptions = get_user_subscriptions()
    if not subscriptions:
        print("[Notifier] No active user subscriptions found")
        return []
    
    # Group subscriptions by user
    user_subscriptions = {}
    for sub in subscriptions:
        telegram_user_id = sub.get('telegram_user_id')
        anime_id = sub.get('anime_id')
        last_notified = sub.get('last_notified_episode', 0)
        
        if telegram_user_id and anime_id:
            if telegram_user_id not in user_subscriptions:
                user_subscriptions[telegram_user_id] = []
            user_subscriptions[telegram_user_id].append({
                'anime_id': anime_id,
                'anime_title': sub.get('anime_title', 'Неизвестное аниме'),
                'anime_poster': sub.get('anime_poster'),
                'last_notified': last_notified
            })
    
    # Fetch latest episodes from API
    latest_items = fetch_latest_episodes()
    if not latest_items:
        print("[Notifier] No episodes fetched from API")
        return []
    
    # Create mapping of anime_id -> latest episode number
    anime_episode_map = {}
    for item in latest_items:
        anime_id = item.get('id')
        if anime_id:
            latest_ep = extract_latest_episode_num(item.get('title', ''), item.get('series'))
            anime_episode_map[f"vost-{anime_id}"] = latest_ep
            # Also add item for reference
            item['latest_ep'] = latest_ep
            title_ru, title_eng = clean_title(item.get('title', ''))
            item['title_ru'] = title_ru
    
    # Find subscriptions with new episodes
    notifications = []
    for telegram_user_id, user_subs in user_subscriptions.items():
        for sub in user_subs:
            anime_id = sub['anime_id']
            
            # Find matching anime in latest items
            matching_anime = None
            for item in latest_items:
                if item.get('id') and f"vost-{item['id']}" == anime_id:
                    matching_anime = item
                    break
            
            if not matching_anime:
                continue
            
            latest_ep = matching_anime.get('latest_ep', 0)
            last_notified = sub['last_notified']
            
            if latest_ep > last_notified:
                new_episodes = latest_ep - last_notified
                
                notifications.append({
                    'telegram_user_id': telegram_user_id,
                    'anime_id': anime_id,
                    'anime_title': sub['anime_title'],
                    'poster_url': sub['anime_poster'] or resolve_best_poster(None, matching_anime.get('urlImagePreview')),
                    'current_episode': latest_ep,
                    'new_episodes_count': new_episodes,
                    'last_notified': last_notified,
                    'anime_data': matching_anime
                })
    
    return notifications

def create_personal_notification_message(anime_title: str, current_episode: int, new_episodes_count: int, anime_data: Dict) -> str:
    """
    Create personalized notification message for user
    """
    config = load_config()
    app_name = config['app']['name']
    app_url = "https://animevist.app"  # Default URL
    
    title_ru, title_eng = clean_title(anime_data.get('title', ''))
    genres_str = anime_data.get('genre', 'Аниме, Приключения')
    hashtags = format_genre_hashtags(genres_str, current_episode, app_name)
    
    if new_episodes_count > 1:
        message = (
            f"🎉 <b>{title_ru}</b>\n\n"
            f"Вышло <b>{new_episodes_count} новых серий</b>! 🚀\n\n"
            f"Текущая серия: <b>{current_episode}</b>\n\n"
            f"Смотрите новые серии прямо сейчас в приложении AnimeVist!\n\n"
            f"{hashtags}"
        )
    else:
        message = (
            f"🎉 <b>{title_ru}</b>\n\n"
            f"Вышла новая серия! 🎬\n\n"
            f"Серия <b>{current_episode}</b> доступна для просмотра!\n\n"
            f"Смотрите прямо сейчас в приложении AnimeVist!\n\n"
            f"{hashtags}"
        )
    
    return message

def create_notification_keyboard(anime_id: str, current_episode: int) -> Optional[Dict]:
    """
    Create inline keyboard for notification
    """
    # Create keyboard with action buttons
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Пометить как просмотренное",
                    "callback_data": f"episode_seen_{anime_id}_{current_episode}"
                }
            ]
        ]
    }

def send_personal_notifications():
    """
    Send personal notifications to all users with new episodes
    Returns statistics about sent notifications
    """
    stats = {
        'sent': 0,
        'failed': 0,
        'total_users': 0
    }
    
    config = load_config()
    bot_token = config['telegram']['bot_token']
    
    if not bot_token:
        print("[Notifier] No bot token configured")
        return stats
    
    sender = TelegramSender()
    
    # Get notifications needed
    notifications = fetch_user_subscriptions_with_new_episodes()
    if not notifications:
        print("[Notifier] No new episodes for any users")
        return stats
    
    print(f"[Notifier] Found {len(notifications)} notifications to send")
    
    # Group notifications by user
    user_notifications = {}
    for notification in notifications:
        user_id = notification['telegram_user_id']
        if user_id not in user_notifications:
            user_notifications[user_id] = []
        user_notifications[user_id].append(notification)
    
    stats['total_users'] = len(user_notifications)
    
    # Send notifications to each user
    for user_id, user_notifs in user_notifications.items():
        try:
            # Send each notification separately
            for notif in user_notifs:
                anime_id = notif['anime_id']
                anime_title = notif['anime_title']
                current_episode = notif['current_episode']
                new_episodes_count = notif['new_episodes_count']
                poster_url = notif['poster_url']
                
                # Create message and keyboard
                message = create_personal_notification_message(
                    anime_title, current_episode, new_episodes_count, notif['anime_data']
                )
                
                keyboard = create_notification_keyboard(anime_id, current_episode)
                
                # Send notification
                if poster_url and poster_url.startswith('http'):
                    # Try to send with photo first
                    result = sender.send_photo(
                        photo_url_or_path=poster_url,
                        caption=message,
                        chat_id=user_id,
                        reply_markup=keyboard
                    )
                else:
                    # Fallback to text-only message
                    result = sender.send_message(
                        text=message,
                        chat_id=user_id,
                        reply_markup=keyboard
                    )
                
                if result.get('ok'):
                    # Update subscription with last notified episode
                    # Get animevist_user_id from subscription (we need to fetch it)
                    subscriptions = get_user_subscriptions(telegram_user_id=user_id)
                    for sub in subscriptions:
                        if sub.get('anime_id') == anime_id:
                            animevist_user_id = sub.get('animevist_user_id')
                            if animevist_user_id:
                                update_user_subscription(
                                    telegram_user_id=user_id,
                                    animevist_user_id=animevist_user_id,
                                    anime_id=anime_id,
                                    last_notified_episode=current_episode
                                )
                            break
                    
                    stats['sent'] += 1
                    print(f"[Notifier] Sent notification to user {user_id}: {anime_title} ep {current_episode}")
                else:
                    stats['failed'] += 1
                    print(f"[Notifier] Failed to send to user {user_id}: {result.get('description', 'Unknown error')}")
                
                # Small delay to avoid rate limiting
                time.sleep(0.5)
            
            print(f"[Notifier] Completed notifications for user {user_id}")
            
        except Exception as e:
            stats['failed'] += len(user_notifs)
            print(f"[Notifier] Error processing user {user_id}: {str(e)}")
    
    print(f"[Notifier] Stats: {stats}")
    return stats

def run_notification_cycle(dry_run: bool = False):
    """
    Run one complete notification cycle
    """
    print(f"[Notifier] Starting notification cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if dry_run:
        print("[Notifier] DRY RUN - No notifications will be sent")
        
        # Just fetch and display what would be sent
        notifications = fetch_user_subscriptions_with_new_episodes()
        
        if notifications:
            print(f"[Notifier] Would send {len(notifications)} notifications:")
            for notif in notifications[:5]:  # Show first 5
                print(f"  • User {notif['telegram_user_id']}: {notif['anime_title']} ep {notif['current_episode']} (+{notif['new_episodes_count']})")
            
            if len(notifications) > 5:
                print(f"  ... and {len(notifications) - 5} more")
        else:
            print("[Notifier] No new episodes found for any users")
        
        return {'dry_run': True, 'notifications_count': len(notifications)}
    else:
        # Actually send notifications
        stats = send_personal_notifications()
        return {'cycle_complete': True, 'stats': stats}

if __name__ == "__main__":
    import sys
    
    dry_run = '--dry-run' in sys.argv or '--test' in sys.argv
    result = run_notification_cycle(dry_run=dry_run)
    
    if dry_run:
        print(f"[Notifier] Dry run result: {result}")
    else:
        print(f"[Notifier] Cycle result: {result}")

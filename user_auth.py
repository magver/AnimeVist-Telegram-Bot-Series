"""
User Authentication and Subscription Manager for AnimeVist Telegram Bot.
Handles Supabase GoTrue authentication, user library synchronization,
and personal subscription management in Supabase DB.
"""

import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, List, Optional, Tuple

from telegram_sender import load_config

def get_supabase_headers(access_token: Optional[str] = None) -> Tuple[str, Dict[str, str]]:
    config = load_config()
    cloud = config.get('cloud_storage', {})
    url = cloud.get('supabase_url', '').rstrip('/')
    key = cloud.get('supabase_key', '')
    
    token = access_token or key
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "AnimeVistBot/2.0"
    }
    return url, headers

def verify_user_credentials(email: str, password: str) -> Optional[Dict]:
    config = load_config()
    cs = config.get('cloud_storage', {})
    provider = cs.get('provider', 'supabase')

    if provider == 'cloudflare':
        api_url = cs.get('api_url') or cs.get('cloudflare_worker_url')
        if not api_url:
            print("[Auth] Cloudflare API URL not configured")
            return None
        endpoint = f"{api_url.rstrip('/')}/api/auth/login"
        payload = json.dumps({
            "email": email.strip().lower(),
            "password": password
        }).encode('utf-8')
        req = urllib.request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if 'user' in data and 'token' in data:
                    u = data['user']
                    return {
                        'id': u['id'],
                        'email': u.get('email', email),
                        'username': u.get('username') or email.split('@')[0],
                        'avatar_url': u.get('avatar_url'),
                        'access_token': data['token']
                    }
        except Exception as e:
            print(f"[Auth] Cloudflare login error: {e}")
        return None

    url, headers = get_supabase_headers()
    if not url or not headers.get('apikey'):
        print("[Auth] Supabase URL or key not configured")
        return None

    endpoint = f"{url}/auth/v1/token?grant_type=password"
    payload = json.dumps({
        "email": email.strip().lower(),
        "password": password
    }).encode('utf-8')

    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if 'user' in data and 'access_token' in data:
                u = data['user']
                metadata = u.get('user_metadata') or {}
                username = metadata.get('username') or metadata.get('name') or u.get('email', '').split('@')[0]
                return {
                    'id': u['id'],
                    'email': u.get('email', email),
                    'username': username,
                    'avatar_url': metadata.get('avatar_url'),
                    'access_token': data['access_token']
                }
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode('utf-8'))
            print(f"[Auth] GoTrue HTTP {e.code}: {err.get('error_description') or err.get('msg') or err}")
        except Exception:
            print(f"[Auth] GoTrue HTTP {e.code}: {e.reason}")
    except Exception as e:
        print(f"[Auth] GoTrue request error: {e}")
    return None

def get_user_library(user_id: str, access_token: Optional[str] = None) -> List[Dict]:
    config = load_config()
    cs = config.get('cloud_storage', {})
    provider = cs.get('provider', 'supabase')

    if provider == 'cloudflare':
        api_url = cs.get('api_url') or cs.get('cloudflare_worker_url')
        if not api_url:
            return []
        endpoint = f"{api_url.rstrip('/')}/api/bot/library?user_id={user_id}"
        req = urllib.request.Request(endpoint, headers={"User-Agent": "Mozilla/5.0"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                rows = json.loads(resp.read().decode('utf-8'))
                if not isinstance(rows, list):
                    return []
                results = []
                for r in rows:
                    anime_id = r.get('anime_id')
                    if not anime_id:
                        continue
                    raw_data = r.get('anime_data')
                    anime_data = {}
                    if isinstance(raw_data, str):
                        try:
                            anime_data = json.loads(raw_data)
                        except Exception:
                            anime_data = {}
                    elif isinstance(raw_data, dict):
                        anime_data = raw_data
                    title = (
                        anime_data.get('title_ru') or
                        anime_data.get('title') or
                        anime_data.get('russian') or
                        anime_data.get('name') or
                        r.get('anime_title') or
                        f"Аниме #{anime_id}"
                    )
                    poster = (
                        anime_data.get('poster') or
                        anime_data.get('poster_url') or
                        anime_data.get('urlImagePreview') or
                        anime_data.get('image') or
                        r.get('anime_poster') or
                        ''
                    )
                    if poster and not poster.startswith('http'):
                        poster = f"https://animevost.org{poster}"
                    current_ep = r.get('current_episode') or r.get('last_watched_episode') or 0
                    results.append({
                        'anime_id': str(anime_id),
                        'title': title,
                        'poster': poster,
                        'current_episode': current_ep,
                        'raw': r
                    })
                return results
        except Exception as e:
            print(f"[Auth] Cloudflare error fetching user_library: {e}")
            return []

    url, headers = get_supabase_headers(access_token)
    if not url:
        return []

    endpoint = f"{url}/rest/v1/user_library?user_id=eq.{user_id}&status=eq.watching&select=*"
    req = urllib.request.Request(endpoint, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            rows = json.loads(resp.read().decode('utf-8'))
            if not isinstance(rows, list):
                return []

            results = []
            for r in rows:
                anime_id = r.get('anime_id')
                if not anime_id:
                    continue

                raw_data = r.get('anime_data')
                anime_data = {}
                if isinstance(raw_data, str):
                    try:
                        anime_data = json.loads(raw_data)
                    except Exception:
                        anime_data = {}
                elif isinstance(raw_data, dict):
                    anime_data = raw_data

                title = (
                    anime_data.get('title_ru') or
                    anime_data.get('title') or
                    anime_data.get('russian') or
                    anime_data.get('name') or
                    r.get('anime_title') or
                    f"Аниме #{anime_id}"
                )

                poster = (
                    anime_data.get('poster') or
                    anime_data.get('poster_url') or
                    anime_data.get('urlImagePreview') or
                    anime_data.get('image') or
                    r.get('anime_poster') or
                    ''
                )
                if poster and not poster.startswith('http'):
                    poster = f"https://animevost.org{poster}"

                current_ep = r.get('current_episode') or r.get('last_watched_episode') or 0

                results.append({
                    'anime_id': str(anime_id),
                    'title': title,
                    'poster': poster,
                    'current_episode': current_ep,
                    'raw': r
                })

            return results
    except Exception as e:
        print(f"[Auth] Error fetching user_library: {e}")
        return []

def update_user_subscription(
    telegram_user_id: int,
    animevist_user_id: Optional[str],
    anime_id: str,
    anime_title: Optional[str] = None,
    anime_poster: Optional[str] = None,
    last_notified_episode: int = 0,
    active: bool = True
) -> bool:
    config = load_config()
    cs = config.get('cloud_storage', {})
    provider = cs.get('provider', 'supabase')

    if provider == 'cloudflare':
        api_url = cs.get('api_url') or cs.get('cloudflare_worker_url')
        if not api_url:
            return False
        endpoint = f"{api_url.rstrip('/')}/api/bot/subscriptions"
        payload = {
            "telegram_user_id": int(telegram_user_id),
            "animevist_user_id": animevist_user_id,
            "anime_id": str(anime_id),
            "anime_title": anime_title,
            "anime_poster": anime_poster,
            "last_notified_episode": int(last_notified_episode),
            "active": active
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return True
        except Exception as e:
            print(f"[Auth] Cloudflare subscription error: {e}")
            return False

    try:
        from turso_db import TursoClient, turso_upsert_user_subscription
        if TursoClient().is_configured():
            return turso_upsert_user_subscription(
                telegram_user_id=telegram_user_id,
                animevist_user_id=animevist_user_id,
                anime_id=anime_id,
                anime_title=anime_title,
                anime_poster=anime_poster,
                last_notified_episode=last_notified_episode,
                active=active
            )
    except Exception as e:
        print(f"[Turso] Update sub error: {e}")

    url, headers = get_supabase_headers()
    if not url:
        return False

    endpoint = f"{url}/rest/v1/user_subscriptions?on_conflict=telegram_user_id,anime_id"
    headers["Prefer"] = "resolution=merge-duplicates"

    uid = animevist_user_id
    if not uid:
        existing = get_user_subscriptions(telegram_user_id=telegram_user_id, active_only=False)
        for s in existing:
            if s.get('animevist_user_id'):
                uid = s.get('animevist_user_id')
                break

    payload_row = {
        "telegram_user_id": int(telegram_user_id),
        "anime_id": str(anime_id),
        "last_notified_episode": int(last_notified_episode),
        "active": active,
        "updated_at": time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())
    }

    if uid:
        payload_row["animevist_user_id"] = uid
    if anime_title:
        payload_row["anime_title"] = anime_title
    if anime_poster:
        payload_row["anime_poster"] = anime_poster

    data = json.dumps([payload_row]).encode('utf-8')
    req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True
    except urllib.error.HTTPError as e:
        # Fallback to PATCH if row already exists
        if e.code in (400, 409):
            try:
                patch_endpoint = f"{url}/rest/v1/user_subscriptions?telegram_user_id=eq.{telegram_user_id}&anime_id=eq.{anime_id}"
                patch_payload = {
                    "last_notified_episode": int(last_notified_episode),
                    "active": active,
                    "updated_at": time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())
                }
                if anime_title:
                    patch_payload["anime_title"] = anime_title
                if anime_poster:
                    patch_payload["anime_poster"] = anime_poster
                if uid:
                    patch_payload["animevist_user_id"] = uid

                patch_req = urllib.request.Request(
                    patch_endpoint,
                    data=json.dumps(patch_payload).encode('utf-8'),
                    headers=headers,
                    method="PATCH"
                )
                with urllib.request.urlopen(patch_req, timeout=10):
                    return True
            except Exception as patch_e:
                print(f"[Auth] Supabase fallback patch error: {patch_e}")

        err_msg = e.read().decode('utf-8', errors='replace')
        print(f"[Auth] Supabase upsert error ({e.code}): {err_msg}")
        return False
    except Exception as e:
        print(f"[Auth] Error upserting subscription: {e}")
        return False

def get_user_subscriptions(
    telegram_user_id: Optional[int] = None,
    animevist_user_id: Optional[str] = None,
    active_only: bool = True
) -> List[Dict]:
    config = load_config()
    cs = config.get('cloud_storage', {})
    provider = cs.get('provider', 'supabase')

    if provider == 'cloudflare':
        api_url = cs.get('api_url') or cs.get('cloudflare_worker_url')
        if not api_url:
            return []
        endpoint = f"{api_url.rstrip('/')}/api/bot/subscriptions"
        if telegram_user_id is not None:
            endpoint += f"?telegram_user_id={telegram_user_id}"
        req = urllib.request.Request(endpoint, headers={"User-Agent": "Mozilla/5.0"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if not isinstance(data, list):
                    return []
                if active_only:
                    data = [s for s in data if s.get('active')]
                return data
        except Exception as e:
            print(f"[Auth] Cloudflare get_subscriptions error: {e}")
            return []

    try:
        from turso_db import TursoClient, turso_get_user_subscriptions
        if TursoClient().is_configured():
            return turso_get_user_subscriptions(
                telegram_user_id=telegram_user_id,
                animevist_user_id=animevist_user_id,
                active_only=active_only
            )
    except Exception as e:
        print(f"[Turso] Get subs error: {e}")

    url, headers = get_supabase_headers()
    if not url:
        return []

    filters = []
    if telegram_user_id is not None:
        filters.append(f"telegram_user_id=eq.{telegram_user_id}")
    if animevist_user_id is not None:
        filters.append(f"animevist_user_id=eq.{animevist_user_id}")
    if active_only:
        filters.append("active=eq.true")

    query_str = f"?{'&'.join(filters)}&order=updated_at.desc" if filters else "?order=updated_at.desc"
    endpoint = f"{url}/rest/v1/user_subscriptions{query_str}&select=*"

    req = urllib.request.Request(endpoint, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[Auth] Error fetching subscriptions: {e}")
        return []

def toggle_user_subscription(telegram_user_id: int, anime_id: str, active: bool = False) -> bool:
    config = load_config()
    cs = config.get('cloud_storage', {})
    provider = cs.get('provider', 'supabase')

    if provider == 'cloudflare':
        api_url = cs.get('api_url') or cs.get('cloudflare_worker_url')
        if not api_url:
            return False
        endpoint = f"{api_url.rstrip('/')}/api/bot/subscriptions/toggle"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps({"telegram_user_id": int(telegram_user_id), "anime_id": str(anime_id), "active": active}).encode('utf-8'),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                return True
        except Exception:
            return False

    try:
        from turso_db import TursoClient, turso_toggle_user_subscription
        if TursoClient().is_configured():
            return turso_toggle_user_subscription(telegram_user_id, anime_id, active)
    except Exception as e:
        print(f"[Turso] Toggle error: {e}")

    url, headers = get_supabase_headers()
    if not url:
        return False

    endpoint = f"{url}/rest/v1/user_subscriptions?telegram_user_id=eq.{telegram_user_id}&anime_id=eq.{anime_id}"
    payload = json.dumps({
        "active": active,
        "updated_at": time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())
    }).encode('utf-8')

    req = urllib.request.Request(endpoint, data=payload, headers=headers, method="PATCH")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return True
    except Exception as e:
        print(f"[Auth] Error toggling subscription: {e}")
        return False

def delete_user_subscription(telegram_user_id: int, anime_id: str) -> bool:
    config = load_config()
    cs = config.get('cloud_storage', {})
    provider = cs.get('provider', 'supabase')

    if provider == 'cloudflare':
        api_url = cs.get('api_url') or cs.get('cloudflare_worker_url')
        if not api_url:
            return False
        endpoint = f"{api_url.rstrip('/')}/api/bot/subscriptions/delete"
        req = urllib.request.Request(
            endpoint,
            data=json.dumps({"telegram_user_id": int(telegram_user_id), "anime_id": str(anime_id)}).encode('utf-8'),
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                return True
        except Exception:
            return False

    try:
        from turso_db import TursoClient
        client = TursoClient()
        if client.is_configured():
            client.execute("DELETE FROM user_subscriptions WHERE telegram_user_id = ? AND anime_id = ?;", [int(telegram_user_id), str(anime_id)])
            return True
    except Exception as e:
        print(f"[Turso] Delete sub error: {e}")

    url, headers = get_supabase_headers()
    if not url:
        return False

    endpoint = f"{url}/rest/v1/user_subscriptions?telegram_user_id=eq.{telegram_user_id}&anime_id=eq.{anime_id}"
    req = urllib.request.Request(endpoint, headers=headers, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return True
    except Exception as e:
        print(f"[Auth] Error deleting subscription: {e}")
        return False

def get_bot_users_summary() -> Dict:
    try:
        from turso_db import TursoClient, turso_get_users_summary, turso_get_user_subscriptions
        if TursoClient().is_configured():
            summary = turso_get_users_summary()
            subs = turso_get_user_subscriptions(active_only=False)
            summary["total_subscriptions"] = len(subs)
            summary["recent_subscriptions"] = subs[:10]
            return summary
    except Exception as e:
        print(f"[Turso] Summary error: {e}")

    subs = get_user_subscriptions(active_only=False)
    unique_users = set()
    active_subs_count = 0

    for s in subs:
        uid = s.get('telegram_user_id')
        if uid:
            unique_users.add(uid)
        if s.get('active'):
            active_subs_count += 1

    return {
        "total_users": len(unique_users),
        "total_subscriptions": len(subs),
        "active_subscriptions": active_subs_count,
        "recent_subscriptions": subs[:10]
    }

def process_user_login(
    telegram_user_id: int,
    telegram_username: str,
    email: str,
    password: str
) -> Tuple[bool, str, Optional[Dict]]:
    user_info = verify_user_credentials(email, password)
    if not user_info:
        return (
            False,
            "❌ <b>Неверный email или пароль</b>\n\nПожалуйста, проверьте данные учетной записи AnimeVist и попробуйте снова.",
            None
        )

    watching_list = get_user_library(user_info['id'], user_info['access_token'])
    synced_count = 0

    for item in watching_list:
        a_id = item['anime_id']
        title = item['title']
        poster = item['poster']
        cur_ep = item['current_episode']

        ok = update_user_subscription(
            telegram_user_id=telegram_user_id,
            animevist_user_id=user_info['id'],
            anime_id=a_id,
            anime_title=title,
            anime_poster=poster,
            last_notified_episode=cur_ep,
            active=True
        )
        if ok:
            synced_count += 1

    username = user_info.get('username') or 'Пользователь'
    if synced_count > 0:
        msg = (
            f"🎉 <b>С возвращением, {username}!</b>\n\n"
            f"✅ Аккаунт AnimeVist успешно подключен: <code>{email}</code>\n"
            f"📚 Синхронизировано аниме из списка «Смотрю»: <b>{synced_count}</b>\n\n"
            f"🔔 Теперь бот будет мгновенно присылать вам в ЛС уведомления с постером и кнопками, как только выйдет новая серия любого из ваших тайтлов!"
        )
    else:
        msg = (
            f"🎉 <b>С возвращением, {username}!</b>\n\n"
            f"✅ Аккаунт успешно подключен: <code>{email}</code>\n\n"
            f"ℹ️ В вашем списке «Смотрю» пока нет активных тайтлов. Добавьте аниме в приложении AnimeVist или найдите его через поиск прямо здесь, и бот подключит уведомления!"
        )

    return True, msg, user_info
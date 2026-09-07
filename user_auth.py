"""
User Authentication for AnimeVist Telegram Bot
Authenticates users with AnimeVist credentials via Supabase GoTrue API
"""

import json
import urllib.request
import urllib.parse
import urllib.error
import base64
import time

from telegram_sender import load_config

def verify_user_credentials(email: str, password: str):
    """
    Verify AnimeVist user credentials via Supabase GoTrue API
    Returns user info if valid, None otherwise
    """
    config = load_config()
    supabase_url = config['cloud_storage']['supabase_url']
    supabase_key = config['cloud_storage']['supabase_key']
    
    if not supabase_url or not supabase_key:
        print("[Auth] Missing Supabase configuration")
        return None
    
    # GoTrue API endpoint for password sign-in
    url = f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password"
    
    # Prepare request
    auth_string = f"{supabase_key}:"
    auth_b64 = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    
    data = json.dumps({
        "email": email,
        "password": password
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            response = json.loads(resp.read().decode('utf-8'))
            
            if 'user' in response and 'access_token' in response:
                user = response['user']
                return {
                    'id': user['id'],
                    'email': user['email'],
                    'username': user['user_metadata'].get('username', user['email'].split('@')[0]),
                    'avatar_url': user['user_metadata'].get('avatar_url'),
                    'access_token': response['access_token']
                }
            else:
                print(f"[Auth] Login failed: {response.get('error_description', 'Unknown error')}")
                return None
                
    except urllib.error.HTTPError as e:
        try:
            error_data = json.loads(e.read().decode('utf-8'))
            print(f"[Auth] HTTP Error {e.code}: {error_data.get('error_description', 'Authentication failed')}")
        except:
            print(f"[Auth] HTTP Error {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"[Auth] Error: {str(e)}")
        return None

def get_user_library(user_id: str, access_token: str):
    """
    Get user's anime library from Supabase
    Returns watching list (items with status='watching')
    """
    config = load_config()
    supabase_url = config['cloud_storage']['supabase_url']
    
    if not supabase_url:
        print("[Auth] Missing Supabase URL")
        return []
    
    # Query user_library table for anime with status='watching' and app='animevist'
    url = f"{supabase_url.rstrip('/')}/rest/v1/user_library?user_id=eq.{user_id}&status=eq.watching&app=eq.animevist&select=anime_id,anime_title,anime_poster,last_aired_episode,last_watched_episode"
    
    headers = {
        "apikey": config['cloud_storage']['supabase_key'],
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            items = json.loads(resp.read().decode('utf-8'))
            return items if isinstance(items, list) else []
            
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("[Auth] Table user_library not found - run migration script first")
        else:
            print(f"[Auth] HTTP Error fetching library: {e.code}")
        return []
    except Exception as e:
        print(f"[Auth] Error fetching library: {str(e)}")
        return []

def update_user_subscription(telegram_user_id: int, animevist_user_id: str, anime_id: str, last_notified_episode: int = 0):
    """
    Create or update user subscription in Supabase
    """
    config = load_config()
    supabase_url = config['cloud_storage']['supabase_url']
    supabase_key = config['cloud_storage']['supabase_key']
    
    if not supabase_url or not supabase_key:
        print("[Auth] Missing Supabase configuration")
        return False
    
    # First, check if subscription exists
    check_url = f"{supabase_url.rstrip('/')}/rest/v1/user_subscriptions?telegram_user_id=eq.{telegram_user_id}&anime_id=eq.{anime_id}"
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    
    try:
        # Check existing
        check_req = urllib.request.Request(check_url, headers=headers, method="GET")
        with urllib.request.urlopen(check_req, timeout=5) as resp:
            existing = json.loads(resp.read().decode('utf-8'))
            
            subscription_data = {
                "telegram_user_id": telegram_user_id,
                "animevist_user_id": animevist_user_id,
                "anime_id": anime_id,
                "last_notified_episode": last_notified_episode,
                "active": True,
                "updated_at": time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())
            }
            
            # Create or update
            upsert_url = f"{supabase_url.rstrip('/')}/rest/v1/user_subscriptions"
            data = json.dumps([subscription_data]).encode('utf-8')
            
            upsert_req = urllib.request.Request(upsert_url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(upsert_req, timeout=8) as upsert_resp:
                print(f"[Auth] Updated subscription for anime {anime_id}")
                return True
                
    except Exception as e:
        print(f"[Auth] Error updating subscription: {str(e)}")
        return False

def get_user_subscriptions(telegram_user_id: int = None, animevist_user_id: str = None):
    """
    Get user subscriptions from Supabase
    """
    config = load_config()
    supabase_url = config['cloud_storage']['supabase_url']
    supabase_key = config['cloud_storage']['supabase_key']
    
    if not supabase_url or not supabase_key:
        print("[Auth] Missing Supabase configuration")
        return []
    
    # Build query
    filters = []
    if telegram_user_id:
        filters.append(f"telegram_user_id=eq.{telegram_user_id}")
    if animevist_user_id:
        filters.append(f"animevist_user_id=eq.{animevist_user_id}")
    
    if not filters:
        return []
    
    url = f"{supabase_url.rstrip('/')}/rest/v1/user_subscriptions?{'&'.join(filters)}&active=eq.true&select=*"
    
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            items = json.loads(resp.read().decode('utf-8'))
            return items if isinstance(items, list) else []
            
    except Exception as e:
        print(f"[Auth] Error fetching subscriptions: {str(e)}")
        return []

def process_user_login(telegram_user_id: int, telegram_username: str, email: str, password: str):
    """
    Complete user login process:
    1. Verify credentials via GoTrue
    2. Get user's watching list
    3. Create subscriptions for each anime
    Returns (success, message, user_data)
    """
    print(f"[Auth] Processing login for Telegram user {telegram_user_id} ({email})")
    
    # Step 1: Verify credentials
    user_info = verify_user_credentials(email, password)
    if not user_info:
        return False, "❌ Неверный email или пароль. Проверьте данные и попробуйте снова.", None
    
    # Step 2: Get user's watching list
    watching_list = get_user_library(user_info['id'], user_info['access_token'])
    if not watching_list:
        return False, f"✅ Вход выполнен успешно!\n\nПривет, {user_info['username']}! 🎉\n\nУ вас пока нет аниме в списке «Смотрю». Добавьте аниме в приложении AnimeVist, чтобы получать уведомления о новых сериях.", user_info
    
    # Step 3: Create subscriptions for each anime in watching list
    successful_subscriptions = 0
    for anime in watching_list:
        anime_id = anime.get('anime_id')
        if anime_id:
            if update_user_subscription(telegram_user_id, user_info['id'], anime_id):
                successful_subscriptions += 1
    
    return True, f"✅ Вход выполнен успешно!\n\nПривет, {user_info['username']}! 🎉\n\nТеперь вы получите уведомления о новых сериях для {successful_subscriptions} аниме из вашего списка «Смотрю»!", user_info

def test_auth():
    """Test function for authentication"""
    print("[Auth] Testing authentication module...")
    
    # Test with sample credentials (these should be replaced with real ones)
    email = "test@example.com"
    password = "testpassword"
    
    user_info = verify_user_credentials(email, password)
    if user_info:
        print(f"[Auth] Success! User: {user_info['username']} ({user_info['email']})")
        
        # Test getting library
        library = get_user_library(user_info['id'], user_info['access_token'])
        print(f"[Auth] Watching list: {len(library)} anime")
        
        # Test subscription update
        if library:
            first_anime = library[0]
            success = update_user_subscription(123456789, user_info['id'], first_anime.get('anime_id'))
            print(f"[Auth] Subscription update: {'Success' if success else 'Failed'}")
    else:
        print("[Auth] Authentication failed (expected for test credentials)")
    
    print("[Auth] Test complete")

if __name__ == "__main__":
    test_auth()

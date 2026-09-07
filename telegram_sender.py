"""
Telegram Sender Utility for Standalone AnimeVist Automation Service.
Communicates directly with Telegram Bot API via Python urllib (zero external dependencies).
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import urllib.error

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

def get_default_config():
    return {
        "telegram": {
            "bot_token": "",
            "channel_id": "",
            "admin_id": "",
            "discussion_chat_id": "",
            "pinned_message_id": None
        },
        "app": {
            "name": "AnimeVist",
            "github_repo": "magver/AnimeVist-Releases",
            "download_page_url": "https://github.com/magver/AnimeVist-Releases/releases/latest",
            "chat_invite_url": "https://t.me/animevist_chat"
        },
        "announcer": {
            "check_interval_seconds": 300,
            "enable_series_releases": True,
            "enable_anime_news": True,
            "max_releases_per_cycle": 3
        },
        "cloud_storage": {
            "provider": "local",
            "telegram_storage_chat_id": "",
            "upstash_rest_url": "",
            "upstash_rest_token": "",
            "supabase_url": "",
            "supabase_key": "",
            "last_sync": None
        }
    }

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    conf = get_default_config()

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                for section, val in loaded.items():
                    if isinstance(val, dict) and section in conf:
                        conf[section].update(val)
                    else:
                        conf[section] = val
        except Exception as e:
            print(f"[Config] Ошибка чтения config.json: {e}")

    # Fallback/Override from Environment Variables (useful for Cloud/Docker/HuggingFace/Render)
    if os.environ.get("CONFIG_JSON"):
        try:
            env_conf = json.loads(os.environ["CONFIG_JSON"])
            for section, val in env_conf.items():
                if isinstance(val, dict) and section in conf:
                    conf[section].update(val)
                else:
                    conf[section] = val
        except Exception:
            pass

    tg = conf.setdefault('telegram', {})
    if os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN"):
        tg['bot_token'] = os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")
    if os.environ.get("TELEGRAM_CHANNEL_ID") or os.environ.get("CHANNEL_ID"):
        tg['channel_id'] = os.environ.get("TELEGRAM_CHANNEL_ID") or os.environ.get("CHANNEL_ID")
    if os.environ.get("ADMIN_ID"):
        tg['admin_id'] = os.environ.get("ADMIN_ID")
    if os.environ.get("DISCUSSION_CHAT_ID"):
        tg['discussion_chat_id'] = os.environ.get("DISCUSSION_CHAT_ID")

    ann = conf.setdefault('announcer', {})
    if os.environ.get("CHECK_INTERVAL"):
        try:
            ann['check_interval_seconds'] = int(os.environ.get("CHECK_INTERVAL"))
        except ValueError:
            pass

    cloud = conf.setdefault('cloud_storage', {})
    if os.environ.get("STORAGE_CHAT_ID"):
        cloud['telegram_storage_chat_id'] = os.environ.get("STORAGE_CHAT_ID")
    if os.environ.get("UPSTASH_REST_URL"):
        cloud['upstash_rest_url'] = os.environ.get("UPSTASH_REST_URL")
    if os.environ.get("UPSTASH_REST_TOKEN"):
        cloud['upstash_rest_token'] = os.environ.get("UPSTASH_REST_TOKEN")
    if os.environ.get("SUPABASE_URL"):
        cloud['supabase_url'] = os.environ.get("SUPABASE_URL")
    if os.environ.get("SUPABASE_KEY"):
        cloud['supabase_key'] = os.environ.get("SUPABASE_KEY")

    return conf

def save_config(conf, sync_to_cloud=False):
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(conf, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Config] Ошибка записи config.json: {e}")

    if sync_to_cloud:
        try:
            sync_config_to_cloud(conf)
        except Exception as e:
            print(f"[CloudSync] Ошибка синхронизации с облаком: {e}")

def sync_config_to_cloud(conf=None):
    if conf is None:
        conf = load_config()
    provider = conf.get('cloud_storage', {}).get('provider', 'local')
    
    if provider == 'telegram':
        return sync_config_to_telegram(conf)
    elif provider == 'upstash':
        return sync_config_to_upstash(conf)
    elif provider == 'supabase':
        return sync_config_to_supabase(conf)
    return {"ok": True, "provider": "local"}

def sync_config_to_telegram(conf):
    chat_id = conf.get('cloud_storage', {}).get('telegram_storage_chat_id') or conf.get('telegram', {}).get('admin_id')
    if not chat_id:
        return {"ok": False, "error": "Не указан ID служебного чата/канала для хранения настроек (telegram_storage_chat_id или admin_id)"}
    
    sender = TelegramSender(bot_token=conf.get('telegram', {}).get('bot_token'))
    now_str = sys.modules.get('time', __import__('time')).strftime('%Y-%m-%d %H:%M:%S')
    
    # Pack clean config payload
    conf_copy = json.loads(json.dumps(conf))
    text_content = (
        f"🔐 <b>[ANIMEVIST_BOT_CONFIG_BACKUP]</b>\n"
        f"📅 <i>{now_str}</i>\n\n"
        f"<code>{json.dumps(conf_copy, ensure_ascii=False, indent=2)}</code>"
    )
    res = sender.send_message(text_content, chat_id=chat_id)
    if res.get('ok'):
        msg_id = res['result']['message_id']
        try:
            sender.pin_chat_message(msg_id, chat_id=chat_id, disable_notification=True)
        except Exception:
            pass
        conf['cloud_storage']['last_sync'] = now_str
        save_config(conf, sync_to_cloud=False)
        return {"ok": True, "message": f"Конфиг успешно сохранен в Telegram (ID сообщения: {msg_id})"}
    else:
        return {"ok": False, "error": res.get('description', 'Ошибка отправки в Telegram')}

def fetch_config_from_telegram(conf=None):
    if conf is None:
        conf = load_config()
    chat_id = conf.get('cloud_storage', {}).get('telegram_storage_chat_id') or conf.get('telegram', {}).get('admin_id')
    token = conf.get('telegram', {}).get('bot_token')
    if not token or not chat_id:
        return {"ok": False, "error": "Токен бота или ID чата хранилища не заданы"}

    url = f"https://api.telegram.org/bot{token}/getChat?chat_id={chat_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "AnimeVistBot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('ok'):
                pinned = data.get('result', {}).get('pinned_message', {})
                text = pinned.get('text', '')
                if 'ANIMEVIST_BOT_CONFIG_BACKUP' in text and '<code>' in text:
                    raw_json = text.split('<code>')[1].split('</code>')[0].strip()
                    parsed = json.loads(raw_json)
                    save_config(parsed, sync_to_cloud=False)
                    return {"ok": True, "config": parsed}
        return {"ok": False, "error": "В закрепленных сообщениях чата не найден бэкап настроек"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def sync_config_to_upstash(conf):
    url = conf.get('cloud_storage', {}).get('upstash_rest_url')
    token = conf.get('cloud_storage', {}).get('upstash_rest_token')
    if not url or not token:
        return {"ok": False, "error": "Upstash REST URL или Token не настроены"}
    
    endpoint = f"{url.rstrip('/')}/set/animevist_config"
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(conf).encode('utf-8'),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "AnimeVistBot/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            now_str = sys.modules.get('time', __import__('time')).strftime('%Y-%m-%d %H:%M:%S')
            conf['cloud_storage']['last_sync'] = now_str
            save_config(conf, sync_to_cloud=False)
            return {"ok": True, "result": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def fetch_config_from_upstash(conf=None):
    if conf is None:
        conf = load_config()
    url = conf.get('cloud_storage', {}).get('upstash_rest_url')
    token = conf.get('cloud_storage', {}).get('upstash_rest_token')
    if not url or not token:
        return {"ok": False, "error": "Upstash REST URL или Token не настроены"}
    
    endpoint = f"{url.rstrip('/')}/get/animevist_config"
    req = urllib.request.Request(
        endpoint,
        headers={"Authorization": f"Bearer {token}", "User-Agent": "AnimeVistBot/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            res_val = data.get('result')
            if res_val:
                parsed = json.loads(res_val) if isinstance(res_val, str) else res_val
                save_config(parsed, sync_to_cloud=False)
                return {"ok": True, "config": parsed}
            return {"ok": False, "error": "В Upstash нет сохраненного ключа animevist_config"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def sync_config_to_supabase(conf):
    url = conf.get('cloud_storage', {}).get('supabase_url')
    key = conf.get('cloud_storage', {}).get('supabase_key')
    if not url or not key:
        return {"ok": False, "error": "Supabase URL или Key не настроены"}
    endpoint = f"{url.rstrip('/')}/rest/v1/bot_config"
    payload = json.dumps([{"id": "animevist_main", "config": conf}]).encode('utf-8')
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
            "User-Agent": "AnimeVistBot/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            now_str = sys.modules.get('time', __import__('time')).strftime('%Y-%m-%d %H:%M:%S')
            conf['cloud_storage']['last_sync'] = now_str
            save_config(conf, sync_to_cloud=False)
            return {"ok": True, "message": "Конфиг сохранен в Supabase"}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": False, "error": "Таблица bot_config ещё не создана в базе. Запустите скрипт supabase_bot_schema.sql в Supabase SQL Editor!"}
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def fetch_config_from_supabase(conf=None):
    if conf is None:
        conf = load_config()
    url = conf.get('cloud_storage', {}).get('supabase_url')
    key = conf.get('cloud_storage', {}).get('supabase_key')
    if not url or not key:
        return {"ok": False, "error": "Supabase URL или Key не настроены"}
    endpoint = f"{url.rstrip('/')}/rest/v1/bot_config?id=eq.animevist_main&select=config"
    req = urllib.request.Request(
        endpoint,
        headers={"apikey": key, "Authorization": f"Bearer {key}", "User-Agent": "AnimeVistBot/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and len(data) > 0 and 'config' in data[0]:
                loaded_conf = data[0]['config']
                save_config(loaded_conf, sync_to_cloud=False)
                return {"ok": True, "config": loaded_conf}
            return {"ok": False, "error": "Запись конфигурации bot_config не найдена в Supabase. Нажмите 'Сделать бэкап'."}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": False, "error": "Таблица bot_config ещё не создана в Supabase. Выполните supabase_bot_schema.sql в SQL Editor!"}
        return {"ok": False, "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def load_seen_from_supabase(category='episode', days=None):
    conf = load_config()
    url = conf.get('cloud_storage', {}).get('supabase_url')
    key = conf.get('cloud_storage', {}).get('supabase_key')
    if not url or not key:
        return set()
    endpoint = f"{url.rstrip('/')}/rest/v1/bot_seen_items?category=eq.{category}&select=item_id,created_at&limit=1000"
    if days:
        import datetime
        import urllib.parse
        cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)).isoformat()
        endpoint += f"&created_at=gte.{urllib.parse.quote(cutoff)}"
    req = urllib.request.Request(
        endpoint,
        headers={"apikey": key, "Authorization": f"Bearer {key}", "User-Agent": "AnimeVistBot/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return set(str(row['item_id']) for row in data if 'item_id' in row)
    except Exception:
        return set()

def save_seen_to_supabase(item_ids, category='episode'):
    conf = load_config()
    url = conf.get('cloud_storage', {}).get('supabase_url')
    key = conf.get('cloud_storage', {}).get('supabase_key')
    if not url or not key or not item_ids:
        return False
    import datetime
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows = [{"item_id": str(i), "category": category, "created_at": now_iso} for i in list(item_ids)[-200:]]
    endpoint = f"{url.rstrip('/')}/rest/v1/bot_seen_items"
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(rows).encode('utf-8'),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
            "User-Agent": "AnimeVistBot/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True
    except Exception:
        return False

def test_supabase_connection(conf=None):
    if conf is None:
        conf = load_config()
    url = conf.get('cloud_storage', {}).get('supabase_url')
    key = conf.get('cloud_storage', {}).get('supabase_key')
    if not url or not key:
        return {"ok": False, "error": "Supabase URL или Key не заданы"}
    endpoint = f"{url.rstrip('/')}/rest/v1/user_library?select=*&limit=1"
    req = urllib.request.Request(
        endpoint,
        headers={"apikey": key, "Authorization": f"Bearer {key}", "User-Agent": "AnimeVistBot/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return {"ok": True, "status": resp.status, "message": "Подключение к вашей базе Supabase успешно!"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

class TelegramSender:
    def __init__(self, bot_token=None, channel_id=None):
        config = load_config()
        tg_conf = config.get('telegram', {})
        self.bot_token = bot_token or tg_conf.get('bot_token')
        self.channel_id = channel_id or tg_conf.get('channel_id')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_message(self, text, chat_id=None, reply_markup=None, disable_preview=False):
        target_chat = chat_id or self.channel_id
        if not self.bot_token or not target_chat:
            return {"ok": False, "description": "bot_token or chat_id not configured"}

        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_preview
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        return self._make_request("sendMessage", payload)

    def send_photo(self, photo_url_or_path, caption="", chat_id=None, reply_markup=None):
        target_chat = chat_id or self.channel_id
        if not self.bot_token or not target_chat:
            return {"ok": False, "description": "bot_token or chat_id not configured"}

        if photo_url_or_path.startswith("http://") or photo_url_or_path.startswith("https://"):
            payload = {
                "chat_id": target_chat,
                "photo": photo_url_or_path,
                "caption": caption,
                "parse_mode": "HTML"
            }
            if reply_markup:
                payload["reply_markup"] = reply_markup
            return self._make_request("sendPhoto", payload)
        elif os.path.isfile(photo_url_or_path):
            return self._send_multipart("sendPhoto", "photo", photo_url_or_path, {
                "chat_id": str(target_chat),
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(reply_markup) if reply_markup else None
            })
        else:
            return self.send_message(f"<b>[Медиа]</b>\n{caption}", chat_id=target_chat, reply_markup=reply_markup)

    def send_document(self, file_path, caption="", chat_id=None):
        target_chat = chat_id or self.channel_id
        if not os.path.isfile(file_path):
            return {"ok": False, "description": f"File not found: {file_path}"}
        return self._send_multipart("sendDocument", "document", file_path, {
            "chat_id": str(target_chat),
            "caption": caption,
            "parse_mode": "HTML"
        })

    def pin_chat_message(self, message_id, chat_id=None, disable_notification=False):
        target_chat = chat_id or self.channel_id
        if not self.bot_token or not target_chat:
            return {"ok": False, "description": "bot_token or chat_id not configured"}
        payload = {
            "chat_id": target_chat,
            "message_id": message_id,
            "disable_notification": disable_notification
        }
        return self._make_request("pinChatMessage", payload)

    def edit_message_text(self, message_id, text, chat_id=None, reply_markup=None, disable_preview=False):
        target_chat = chat_id or self.channel_id
        if not self.bot_token or not target_chat:
            return {"ok": False, "description": "bot_token or chat_id not configured"}
        payload = {
            "chat_id": target_chat,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": disable_preview
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self._make_request("editMessageText", payload)

    def get_me(self):
        return self._make_request("getMe", {})

    def get_chat(self, chat_id=None):
        target_chat = chat_id or self.channel_id
        if not self.bot_token or not target_chat:
            return {"ok": False, "description": "bot_token or chat_id not configured"}
        return self._make_request("getChat", {"chat_id": target_chat})

    def get_chat_member_count(self, chat_id=None):
        target_chat = chat_id or self.channel_id
        if not self.bot_token or not target_chat:
            return {"ok": False, "description": "bot_token or chat_id not configured"}
        return self._make_request("getChatMemberCount", {"chat_id": target_chat})

    def _make_request(self, method, payload):
        url = f"{self.base_url}/{method}"
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "AnimeVistBot/1.0"}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode('utf-8'))
            except Exception:
                return {"ok": False, "description": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"ok": False, "description": str(e)}

    def _send_multipart(self, method, file_field_name, file_path, fields):
        boundary = "----AnimeVistStandaloneBoundaryXYZ"
        url = f"{self.base_url}/{method}"
        body_parts = []

        for key, val in fields.items():
            if val is not None:
                body_parts.append(f"--{boundary}\r\n".encode('utf-8'))
                body_parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode('utf-8'))
                body_parts.append(f"{val}\r\n".encode('utf-8'))

        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        body_parts.append(f"--{boundary}\r\n".encode('utf-8'))
        body_parts.append(f'Content-Disposition: form-data; name="{file_field_name}"; filename="{filename}"\r\n'.encode('utf-8'))
        body_parts.append(b"Content-Type: application/octet-stream\r\n\r\n")
        body_parts.append(file_bytes)
        body_parts.append(b"\r\n")
        body_parts.append(f"--{boundary}--\r\n".encode('utf-8'))

        data = b"".join(body_parts)
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(data)),
                "User-Agent": "AnimeVistBot/1.0"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode('utf-8'))
            except Exception:
                return {"ok": False, "description": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"ok": False, "description": str(e)}

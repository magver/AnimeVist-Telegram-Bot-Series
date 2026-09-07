"""
AnimeVist Telegram Personal Bot — 24/7 Service with Step-by-Step Auth & Notifications
"""

import os
import sys
import json
import time
import threading
import traceback
import urllib.request
import urllib.parse
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Load configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    conf = {
        "telegram": {"bot_token": "", "channel_id": ""},
        "cloud_storage": {"supabase_url": "", "supabase_key": ""}
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                conf.update(json.load(f))
        except Exception:
            pass
    
    # Environment variables override
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        conf.setdefault('telegram', {})['bot_token'] = os.environ.get("TELEGRAM_BOT_TOKEN")
    if os.environ.get("SUPABASE_URL"):
        conf.setdefault('cloud_storage', {})['supabase_url'] = os.environ.get("SUPABASE_URL")
    if os.environ.get("SUPABASE_KEY"):
        conf.setdefault('cloud_storage', {})['supabase_key'] = os.environ.get("SUPABASE_KEY")
    return conf

class TelegramBotAPI:
    def __init__(self, token=None):
        config = load_config()
        self.token = token or config.get('telegram', {}).get('bot_token')
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def request(self, method, payload=None):
        if not self.token:
            return {"ok": False, "description": "No bot token"}
        url = f"{self.base_url}/{method}"
        headers = {"Content-Type": "application/json", "User-Agent": "AnimeVistBot/2.0"}
        data = json.dumps(payload).encode('utf-8') if payload else None
        
        try:
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode('utf-8'))
            except:
                return {"ok": False, "description": f"HTTP {e.code}"}
        except Exception as e:
            return {"ok": False, "description": str(e)}

    def send_message(self, chat_id, text, reply_markup=None, parse_mode="HTML"):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return self.request("sendMessage", payload)

    def answer_callback_query(self, callback_query_id, text="", show_alert=False):
        return self.request("answerCallbackQuery", {
            "callback_query_id": callback_query_id,
            "text": text,
            "show_alert": show_alert
        })

    def get_updates(self, offset=None, timeout=30):
        url = f"{self.base_url}/getUpdates?timeout={timeout}"
        if offset:
            url += f"&offset={offset}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AnimeVistBot/2.0"})
            with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            return {"ok": False, "error": str(e)}

# Supabase Client
class SupabaseDB:
    def __init__(self):
        config = load_config()
        cloud = config.get('cloud_storage', {})
        self.url = cloud.get('supabase_url', '').rstrip('/')
        self.key = cloud.get('supabase_key', '')

    def request(self, endpoint, method="GET", data=None, headers=None):
        if not self.url or not self.key:
            return None
        url = f"{self.url}{endpoint}"
        h = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "User-Agent": "AnimeVistBot/2.0"
        }
        if headers:
            h.update(headers)
        
        body = json.dumps(data).encode('utf-8') if data else None
        req = urllib.request.Request(url, data=body, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode('utf-8')
                return json.loads(raw) if raw else {}
        except Exception as e:
            print(f"[Supabase] Error {endpoint}: {e}")
            return None

    def sign_in(self, email, password):
        """Authenticate user with GoTrue API"""
        res = self.request("/auth/v1/token?grant_type=password", method="POST", data={
            "email": email.strip().lower(),
            "password": password
        })
        if res and 'user' in res and 'access_token' in res:
            return True, res['user'], res['access_token']
        err_msg = 'Неверный email или пароль'
        if isinstance(res, dict):
            err_msg = res.get('error_description') or res.get('msg') or res.get('error') or err_msg
        return False, err_msg, None

    def get_user_library(self, user_id):
        """Get watching anime list from user_library"""
        data = self.request(f"/rest/v1/user_library?user_id=eq.{user_id}&status=eq.watching&select=*")
        return data or []

    def bind_telegram_user(self, telegram_user_id, animevist_user_id, email):
        """Save telegram binding"""
        self.request("/rest/v1/telegram_user_bindings", method="POST", headers={"Prefer": "resolution=merge-duplicates"}, data={
            "telegram_user_id": telegram_user_id,
            "animevist_user_id": animevist_user_id,
            "email": email
        })

    def get_subscriptions(self, telegram_user_id):
        """Get user subscriptions"""
        data = self.request(f"/rest/v1/telegram_user_subscriptions?telegram_user_id=eq.{telegram_user_id}&active=eq.true&select=*")
        return data or []

    def sync_library_to_subscriptions(self, telegram_user_id, animevist_user_id):
        """Sync user_library watching items to telegram_user_subscriptions"""
        library = self.get_user_library(animevist_user_id)
        for item in library:
            anime = item.get('anime_data') or item.get('anime') or {}
            anime_id = item.get('anime_id')
            title = anime.get('title') or item.get('anime_title') or 'Аниме'
            poster = anime.get('poster') or item.get('poster') or ''
            
            if anime_id:
                self.request("/rest/v1/telegram_user_subscriptions", method="POST", headers={"Prefer": "resolution=merge-duplicates"}, data={
                    "telegram_user_id": telegram_user_id,
                    "animevist_user_id": animevist_user_id,
                    "anime_id": anime_id,
                    "anime_title": title,
                    "anime_poster": poster,
                    "active": True
                })

class BotHandler:
    def __init__(self):
        self.api = TelegramBotAPI()
        self.db = SupabaseDB()
        self.states_file = os.path.join(os.path.dirname(__file__), 'user_states.json')
        self.states = self.load_states()

    def load_states(self):
        try:
            if os.path.exists(self.states_file):
                with open(self.states_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def save_states(self):
        try:
            with open(self.states_file, 'w', encoding='utf-8') as f:
                json.dump(self.states, f, ensure_ascii=False, indent=2)
        except:
            pass

    def handle_update(self, update):
        try:
            if 'callback_query' in update:
                self.handle_callback(update['callback_query'])
                return
            
            if 'message' not in update:
                return
            
            msg = update['message']
            chat_id = msg['chat']['id']
            user_id = msg['from']['id']
            first_name = msg['from'].get('first_name', 'Друг')
            text = msg.get('text', '').strip()
            
            if not text:
                return

            # Handle commands
            if text.startswith('/'):
                cmd = text.split('@')[0][1:].lower()
                if cmd == 'start':
                    self.cmd_start(chat_id, user_id, first_name)
                elif cmd == 'login':
                    self.cmd_login_step1(chat_id, user_id)
                elif cmd == 'subscriptions':
                    self.cmd_subscriptions(chat_id, user_id)
                elif cmd == 'logout':
                    self.cmd_logout(chat_id, user_id)
                elif cmd == 'help':
                    self.cmd_help(chat_id)
                else:
                    self.api.send_message(chat_id, "❌ Неизвестная команда. Используйте /help")
                return

            # Handle step-by-step auth states
            user_state = self.states.get(str(user_id), {})
            state_name = user_state.get('state')

            if state_name == 'awaiting_email':
                self.process_email(chat_id, user_id, text)
            elif state_name == 'awaiting_password':
                self.process_password(chat_id, user_id, text)
            else:
                self.api.send_message(chat_id, "🤖 Используйте /start для начала работы или /login для входа в аккаунт.")

        except Exception as e:
            print(f"[Bot] Error handling update: {e}")
            traceback.print_exc()

    def handle_callback(self, cq):
        cq_id = cq['id']
        data = cq['data']
        chat_id = cq['message']['chat']['id']
        user_id = cq['from']['id']

        self.api.answer_callback_query(cq_id)

        if data == 'btn_login':
            self.cmd_login_step1(chat_id, user_id)
        elif data == 'btn_subs':
            self.cmd_subscriptions(chat_id, user_id)
        elif data == 'btn_help':
            self.cmd_help(chat_id)
        elif data == 'btn_logout':
            self.cmd_logout(chat_id, user_id)
        elif data == 'btn_cancel':
            if str(user_id) in self.states:
                del self.states[str(user_id)]
                self.save_states()
            self.api.send_message(chat_id, "❌ Вход отменен.", reply_markup={"inline_keyboard": [[{"text": "🔑 Войти снова", "callback_data": "btn_login"}]]})

    def cmd_start(self, chat_id, user_id, first_name):
        subs = self.db.get_subscriptions(user_id)
        
        if subs:
            text = (
                f"👋 Привет, <b>{first_name}</b>!\n\n"
                f"✅ Вы авторизованы в <b>AnimeVist</b>.\n"
                f"📚 Активных подписок на аниме: <b>{len(subs)}</b>\n\n"
                f"Бот автоматически пришлет уведомление в личные сообщения, как только выйдет новая серия из вашего списка «Смотрю»!"
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "📺 Мои подписки", "callback_data": "btn_subs"}],
                    [{"text": "🚪 Выйти", "callback_data": "btn_logout"}]
                ]
            }
        else:
            text = (
                f"👋 Привет, <b>{first_name}</b>!\n\n"
                f"🤖 Я официальный бот <b>AnimeVist</b> для личных уведомлений о новых сериях.\n\n"
                f"🔑 Для получения уведомлений войдите под своим аккаунтом AnimeVist (теми же данными, что и в приложении):"
            )
            markup = {
                "inline_keyboard": [
                    [{"text": "🔑 Войти в аккаунт", "callback_data": "btn_login"}],
                    [{"text": "❓ Помощь", "callback_data": "btn_help"}]
                ]
            }
        
        self.api.send_message(chat_id, text, reply_markup=markup)

    def cmd_login_step1(self, chat_id, user_id):
        self.states[str(user_id)] = {'state': 'awaiting_email', 'time': time.time()}
        self.save_states()
        
        markup = {"inline_keyboard": [[{"text": "❌ Отмена", "callback_data": "btn_cancel"}]]}
        self.api.send_message(chat_id, "📧 <b>Шаг 1 из 2: Вход в AnimeVist</b>\n\nПожалуйста, введите ваш <b>Email</b> от учетной записи:", reply_markup=markup)

    def process_email(self, chat_id, user_id, email):
        email = email.strip()
        if '@' not in email or '.' not in email:
            self.api.send_message(chat_id, "❌ Неверный формат Email. Попробуйте еще раз или нажмите Отмена:")
            return

        self.states[str(user_id)] = {'state': 'awaiting_password', 'email': email, 'time': time.time()}
        self.save_states()

        markup = {"inline_keyboard": [[{"text": "❌ Отмена", "callback_data": "btn_cancel"}]]}
        self.api.send_message(chat_id, f"🔑 <b>Шаг 2 из 2: Вход в AnimeVist</b>\n\nEmail: <code>{email}</code>\n\nТеперь введите ваш <b>пароль</b> от приложения:", reply_markup=markup)

    def process_password(self, chat_id, user_id, password):
        user_state = self.states.get(str(user_id), {})
        email = user_state.get('email')

        if not email:
            self.cmd_login_step1(chat_id, user_id)
            return

        self.api.send_message(chat_id, "🔄 Проверяю учетные данные в облаке AnimeVist...")

        success, user_obj, err = self.db.sign_in(email, password)
        
        # Clear state
        if str(user_id) in self.states:
            del self.states[str(user_id)]
            self.save_states()

        if not success:
            markup = {"inline_keyboard": [[{"text": "🔄 Попробовать снова", "callback_data": "btn_login"}]]}
            self.api.send_message(chat_id, f"❌ <b>Ошибка входа:</b>\n{err}\n\nПроверьте правильность email и пароля.", reply_markup=markup)
            return

        animevist_user_id = user_obj['id']
        self.db.bind_telegram_user(user_id, animevist_user_id, email)
        self.db.sync_library_to_subscriptions(user_id, animevist_user_id)

        subs = self.db.get_subscriptions(user_id)

        text = (
            f"🎉 <b>Успешный вход!</b>\n\n"
            f"📧 Аккаунт: <code>{email}</code>\n"
            f"📚 Найдено аниме в списке «Смотрю»: <b>{len(subs)}</b>\n\n"
            f"Теперь вы будете получать уведомления в личные сообщения о выходе новых серий!"
        )
        markup = {
            "inline_keyboard": [
                [{"text": "📺 Мои подписки", "callback_data": "btn_subs"}],
                [{"text": "🏠 Главное меню", "callback_data": "btn_help"}]
            ]
        }
        self.api.send_message(chat_id, text, reply_markup=markup)

    def cmd_subscriptions(self, chat_id, user_id):
        subs = self.db.get_subscriptions(user_id)
        if not subs:
            text = "📭 У вас пока нет активных подписок.\n\nДобавьте аниме в список <b>«Смотрю»</b> в приложении AnimeVist, и они появятся здесь автоматически!"
            markup = {"inline_keyboard": [[{"text": "🔑 Войти / Обновить", "callback_data": "btn_login"}]]}
        else:
            text = f"📺 <b>Ваши подписки ({len(subs)}):</b>\n\n"
            for i, s in enumerate(subs[:15], 1):
                title = s.get('anime_title', 'Аниме')
                ep = s.get('last_notified_episode', 0)
                text += f"{i}. <b>{title}</b> (серий получено: {ep})\n"
            if len(subs) > 15:
                text += f"\n...и еще {len(subs)-15} аниме"
            markup = {"inline_keyboard": [[{"text": "🔄 Обновить список", "callback_data": "btn_subs"}]]}
        
        self.api.send_message(chat_id, text, reply_markup=markup)

    def cmd_logout(self, chat_id, user_id):
        if str(user_id) in self.states:
            del self.states[str(user_id)]
            self.save_states()
        self.api.send_message(chat_id, "🚪 Вы вышли из аккаунта. Чтобы войти снова, используйте /login")

    def cmd_help(self, chat_id):
        text = (
            "📖 <b>Помощь по AnimeVist Bot</b>\n\n"
            "• /start — Главное меню\n"
            "• /login — Войти под своими данными\n"
            "• /subscriptions — Показать ваши подписки\n"
            "• /logout — Выйти из аккаунта\n\n"
            "Бот синхронизируется с вашим профилем AnimeVist и присылает уведомления о новых сериях."
        )
        markup = {"inline_keyboard": [[{"text": "🔑 Войти", "callback_data": "btn_login"}]]}
        self.api.send_message(chat_id, text, reply_markup=markup)

    def poll(self):
        print("[Bot] Starting Telegram long polling...")
        offset = None
        while True:
            try:
                res = self.api.get_updates(offset=offset, timeout=30)
                if res and res.get('ok'):
                    for update in res.get('result', []):
                        offset = update['update_id'] + 1
                        self.handle_update(update)
            except Exception as e:
                print(f"[Bot] Polling error: {e}")
                time.sleep(5)

# Simple HTTP Server for Render Health Check
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("AnimeVist Bot is running 24/7!".encode('utf-8'))

    def log_message(self, format, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 7860))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    print(f"[Server] Health check listening on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    print("="*50)
    print("🤖 AnimeVist 24/7 Telegram Personal Bot Starting...")
    print("="*50)
    
    # Start HTTP server in background thread for Render
    threading.Thread(target=run_server, daemon=True).start()
    
    # Start Telegram bot polling
    bot = BotHandler()
    bot.poll()

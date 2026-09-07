"""
Main Telegram Bot Handler for AnimeVist Personal Notifications
Handles user commands and manages personal notification system
"""

import os
import sys
import json
import time
import threading
import traceback
import urllib.request
import urllib.parse

from telegram_sender import TelegramSender, load_config
from user_auth import process_user_login, get_user_subscriptions, update_user_subscription
from personal_notifier import run_notification_cycle


class AnimeVistPersonalBot:
    """Main bot class for handling personal notifications"""
    
    def __init__(self):
        self.config = load_config()
        self.bot_token = self.config['telegram']['bot_token']
        
        if not self.bot_token:
            raise ValueError("Bot token not configured. Set TELEGRAM_BOT_TOKEN in config.json or environment.")
        
        self.sender = TelegramSender()
        self.users_file = os.path.join(os.path.dirname(__file__), 'user_states.json')
        self.user_states = self._load_user_states()
        self.running = False
        self.notification_thread = None
        
    def _load_user_states(self):
        """Load user states from file"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[Bot] Error loading user states: {e}")
        return {}
    
    def _save_user_states(self):
        """Save user states to file"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_states, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Bot] Error saving user states: {e}")
    
    def get_updates(self, offset=None, timeout=30):
        """Get updates from Telegram Bot API"""
        base_url = f"https://api.telegram.org/bot{self.bot_token}"
        url = f"{base_url}/getUpdates"
        params = {"timeout": timeout}
        if offset:
            params["offset"] = offset
        
        url += "?" + urllib.parse.urlencode(params)
        
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=timeout + 10) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except Exception as e:
            return {"ok": False, "error": str(e)}
    
    def handle_command(self, update):
        """Handle incoming Telegram update"""
        try:
            # Обработка callback_query для кнопок
            if 'callback_query' in update:
                return self.handle_callback_query(update['callback_query'])
            
            # Обработка сообщений
            if 'message' not in update:
                return None
            
            message = update['message']
            text = message.get('text', '').strip()
            chat_id = message.get('chat', {}).get('id')
            user_id = message.get('from', {}).get('id')
            username = message.get('from', {}).get('username', '')
            first_name = message.get('from', {}).get('first_name', '')
            
            if not text or not chat_id:
                return None
            
            # Parse command
            if text.startswith('/'):
                parts = text.split('@')
                command = parts[0][1:].lower()
                
                print(f"[Bot] Command '{command}' from user {user_id}")
                
                handlers = {
                    'start': self.handle_start,
                    'login': self.handle_login,
                    'logout': self.handle_logout,
                    'subscriptions': self.handle_subscriptions,
                    'help': self.handle_help,
                    'test': self.handle_test,
                }
                
                handler = handlers.get(command)
                if handler:
                    return handler(chat_id, user_id, username, first_name, text)
            
            # Check if user is in credential entry mode
            if str(user_id) in self.user_states:
                state = self.user_states[str(user_id)]
                if state.get('state') == 'awaiting_credentials':
                    return self.handle_credentials(chat_id, user_id, username, first_name, text)
            
            # Default response for non-commands
            if chat_id > 0:  # Private chat
                return self.send_default_message(chat_id)
            
            return None
            
        except Exception as e:
            print(f"[Bot] Error in handle_command: {e}")
            traceback.print_exc()
            return None
    
    def handle_callback_query(self, callback_query):
        """Handle callback query from inline buttons"""
        try:
            callback_data = callback_query.get('data', '')
            chat_id = callback_query.get('message', {}).get('chat', {}).get('id')
            user_id = callback_query.get('from', {}).get('id')
            
            print(f"[Bot] Callback: {callback_data} from user {user_id}")
            
            # Answer callback query
            self.sender.answer_callback_query(
                callback_query_id=callback_query.get('id'),
                text="Обработка запроса...",
                show_alert=False
            )
            
            # Handle specific callbacks
            if callback_data == 'login':
                return self.handle_login(chat_id, user_id, None, None, None)
            elif callback_data == 'subscriptions':
                return self.handle_subscriptions(chat_id, user_id, None, None, None)
            elif callback_data == 'cancel_login':
                if str(user_id) in self.user_states:
                    del self.user_states[str(user_id)]
                    self._save_user_states()
                return {'handled': True}
            
            return {'handled': False}
            
        except Exception as e:
            print(f"[Bot] Error in handle_callback_query: {e}")
            return {'handled': False, 'error': str(e)}
    
    def handle_start(self, chat_id, user_id, username, first_name, text):
        """Handle /start command"""
        try:
            # Check if user is already authenticated
            user_subs = get_user_subscriptions(telegram_user_id=user_id)
            
            if user_subs:
                message = (
                    f"👋 Привет, {first_name}!\n\n"
                    f"✅ Вы уже авторизованы в AnimeVist.\n\n"
                    f"Вы подписаны на {len(user_subs)} аниме:\n"
                )
                
                # List first few anime
                for sub in user_subs[:5]:
                    anime_title = sub.get('anime_title', 'Неизвестное аниме')
                    last_notified = sub.get('last_notified_episode', 0)
                    message += f"• {anime_title} (последняя: {last_notified} серия)\n"
                
                if len(user_subs) > 5:
                    message += f"• ... и еще {len(user_subs) - 5} аниме\n"
                
                message += "\nИспользуйте команды:\n"
                message += "/subscriptions - Управле��ие подписками\n"
                message += "/logout - Выйти из аккаунта\n"
                message += "/help - Помощь по командам"
            else:
                message = (
                    f"👋 Привет, {first_name}!\n\n"
                    f"🤖 Я бот AnimeVist - ваш помощник для уведомлений о новых сериях аниме.\n\n"
                    f"🔑 Для начала работы выполните вход в ваш аккаунт AnimeVist:\n\n"
                    f"Введите команду:\n"
                    f"<code>/login</code>\n\n"
                    f"Или введите ваши учетные данные в формате:\n"
                    f"<code>email:пароль</code>\n\n"
                    f"Пример: <code>user@example.com:mysecretpassword</code>"
                )
            
            keyboard = None
            if not user_subs:
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "🔑 Выполнить вход", "callback_data": "login"}
                        ]
                    ]
                }
            
            self.sender.send_message(chat_id, message, reply_markup=keyboard, parse_mode='HTML')
            return {'handled': True, 'action': 'start'}
        except Exception as e:
            print(f"[Bot] Error in handle_start: {e}")
            traceback.print_exc()
            self.sender.send_message(chat_id, f"❌ Ошибка: {str(e)}")
            return {'handled': True, 'success': False, 'error': str(e)}
    
    def handle_login(self, chat_id, user_id, username, first_name, text):
        """Handle /login command - ask for credentials"""
        try:
            message = (
                "🔐 <b>Вход в AnimeVist</b>\n\n"
                f"Введите ваш email и пароль в формате:\n"
                f"<code>email:пароль</code>\n\n"
                f"Пример: <code>user@example.com:mysecretpassword</code>"
            )
            
            keyboard = {
                "inline_keyboard": [
                    [
                        {"text": "❌ Отмена", "callback_data": "cancel_login"}
                    ]
                ]
            }
            
            # Set user state to awaiting credentials
            self.user_states[str(user_id)] = {
                'state': 'awaiting_credentials',
                'timestamp': time.time()
            }
            self._save_user_states()
            
            self.sender.send_message(chat_id, message, reply_markup=keyboard, parse_mode='HTML')
            return {'handled': True, 'action': 'awaiting_credentials'}
        except Exception as e:
            print(f"[Bot] Error in handle_login: {e}")
            traceback.print_exc()
            return {'handled': True, 'success': False, 'error': str(e)}
    
    def handle_credentials(self, chat_id, user_id, username, first_name, text):
        """Handle credentials input (email:password format)"""
        try:
            if ':' not in text:
                message = (
                    "❌ <b>Неверный формат!</b>\n\n"
                    "Введите в формате: <code>email:пароль</code>\n\n"
                    "Пример: <code>user@example.com:mysecretpassword</code>"
                )
                self.sender.send_message(chat_id, message, parse_mode='HTML')
                return {'handled': True, 'success': False, 'error': 'Invalid format'}
            
            parts = text.split(':', 1)
            email = parts[0].strip()
            password = parts[1].strip()
            
            if not email or not password:
                message = (
                    "❌ <b>Неверные данные!</b>\n\n"
                    "Email и пароль не могут быть пустыми."
                )
                self.sender.send_message(chat_id, message, parse_mode='HTML')
                return {'handled': True, 'success': False, 'error': 'Empty credentials'}
            
            # Attempt login
            success, message, user_data = process_user_login(user_id, username, email, password)
            
            # Clear user state
            if str(user_id) in self.user_states:
                del self.user_states[str(user_id)]
                self._save_user_states()
            
            # Send result
            self.sender.send_message(chat_id, message, parse_mode='HTML')
            
            if success:
                # Send welcome keyboard
                keyboard = {
                    "inline_keyboard": [
                        [
                            {"text": "📺 Мои подписки", "callback_data": "subscriptions"}
                        ]
                    ]
                }
                self.sender.send_message(chat_id, "Что хотите сделать дальше?", reply_markup=keyboard)
            
            return {'handled': True, 'success': success, 'message': message}
        except Exception as e:
            print(f"[Bot] Error in handle_credentials: {e}")
            traceback.print_exc()
            return {'handled': True, 'success': False, 'error': str(e)}
    
    def handle_logout(self, chat_id, user_id, username, first_name, text):
        """Handle /logout command"""
        try:
            message = (
                "👋 <b>Вы вышли из аккаунта</b>\n\n"
                "Спасибо за использование AnimeVist Bot!\n\n"
                "Чтобы снова получать уведомления, выполните вход командой /login"
            )
            
            self.sender.send_message(chat_id, message, parse_mode='HTML')
            return {'handled': True, 'success': True}
        except Exception as e:
            print(f"[Bot] Error in handle_logout: {e}")
            traceback.print_exc()
            return {'handled': True, 'success': False, 'error': str(e)}
    
    def handle_subscriptions(self, chat_id, user_id, username, first_name, text):
        """Handle /subscriptions command"""
        try:
            user_subs = get_user_subscriptions(telegram_user_id=user_id)
            
            if not user_subs:
                message = (
                    "📺 <b>У вас нет подписок</b>\n\n"
                    "Вы пока не подписаны ни на какие аниме.\n\n"
                    "Чтобы подписаться на уведомления:\n"
                    "1. Выполните вход /login\n"
                    "2. Добавьте аниме в список «Смотрю» в приложении AnimeVist\n"
                    "3. Подписки создадутся автоматически"
                )
            else:
                message = (
                    f"📺 <b>Ваши подписки ({len(user_subs)} аниме)</b>\n\n"
                )
                
                for i, sub in enumerate(user_subs[:10], 1):
                    anime_title = sub.get('anime_title', 'Неизвестное аниме')
                    last_notified = sub.get('last_notified_episode', 0)
                    active = sub.get('active', True)
                    status = "✅" if active else "❌"
                    message += f"{i}. {status} <b>{anime_title}</b> (последняя: {last_notified} серия)\n"
                
                if len(user_subs) > 10:
                    message += f"\n... и еще {len(user_subs) - 10} аниме"
                
                message += "\n\nПодписки обновляются автоматически при добавлении аниме в «Смотрю»."
            
            self.sender.send_message(chat_id, message, parse_mode='HTML')
            return {'handled': True, 'subscriptions': user_subs}
        except Exception as e:
            print(f"[Bot] Error in handle_subscriptions: {e}")
            traceback.print_exc()
            return {'handled': True, 'success': False, 'error': str(e)}
    
    def handle_help(self, chat_id, user_id, username, first_name, text):
        """Handle /help command"""
        try:
            message = (
                "📖 <b>Помощь по боту AnimeVist</b>\n\n"
                "Доступные команды:\n\n"
                "<b>Основные команды:</b>\n"
                "/start - Начать работу с ботом\n"
                "/help - Показать эту справку\n"
                "/login - Вход в аккаунт AnimeVist\n\n"
                "<b>После входа:</b>\n"
                "/subscriptions - Управление подписками\n"
                "/logout - Выйти из аккаунта\n\n"
                "<b>Формат входа:</b>\n"
                "<code>email:пароль</code>\n\n"
                "<b>Пример:</b>\n"
                "<code>user@example.com:mysecretpassword</code>\n\n"
                "<b>Примечание:</b>\n"
                "Бот автоматически подписывает вас на уведомления для всех аниме в списке «Смотрю»."
            )
            
            self.sender.send_message(chat_id, message, parse_mode='HTML')
            return {'handled': True, 'action': 'help'}
        except Exception as e:
            print(f"[Bot] Error in handle_help: {e}")
            traceback.print_exc()
            return {'handled': True, 'success': False, 'error': str(e)}
    
    def handle_test(self, chat_id, user_id, username, first_name, text):
        """Handle /test command - test notifications"""
        try:
            message = "🧪 <b>Тест уведомлений</b>\n\n"
            message += "Запускаю тестовый цикл уведомлений..."
            
            self.sender.send_message(chat_id, message, parse_mode='HTML')
            
            # Run notification cycle in background
            def run_test():
                result = run_notification_cycle(dry_run=True)
                test_message = "✅ <b>Тест завершен</b>\n\n"
                
                if result.get('dry_run'):
                    count = result.get('notifications_count', 0)
                    if count > 0:
                        test_message += f"Найдено {count} аниме с новыми сериями для уведомлений.\n"
                        test_message += "В реальном режиме уведомления были бы отправлены."
                    else:
                        test_message += "Новых серий для уведомлений не найдено."
                else:
                    test_message += "Произошла ошибка при тестировании."
                
                self.sender.send_message(chat_id, test_message, parse_mode='HTML')
            
            threading.Thread(target=run_test, daemon=True).start()
            return {'handled': True, 'action': 'test'}
        except Exception as e:
            print(f"[Bot] Error in handle_test: {e}")
            traceback.print_exc()
            return {'handled': True, 'success': False, 'error': str(e)}
    
    def send_default_message(self, chat_id):
        """Send default message for non-commands"""
        try:
            message = (
                "🤖 <b>AnimeVist Bot</b>\n\n"
                "Я бот для уведомлений о новых сериях аниме.\n\n"
                "Используйте команды:\n"
                "/start - Начать работу\n"
                "/help - Помощь по командам\n"
                "/login - Вход в аккаунт"
            )
            
            self.sender.send_message(chat_id, message, parse_mode='HTML')
            return {'handled': True}
        except Exception as e:
            print(f"[Bot] Error in send_default_message: {e}")
            traceback.print_exc()
            return {'handled': False, 'error': str(e)}
    
    def process_updates(self):
        """Process Telegram updates"""
        print("[Bot] Starting bot...")
        
        # Clear previous offset
        offset = 0
        
        while self.running:
            try:
                # Get updates from Telegram
                updates = self.get_updates(offset=offset, timeout=30)
                
                if 'result' in updates:
                    for update in updates['result']:
                        offset = update['update_id'] + 1
                        
                        # Handle the update
                        result = self.handle_command(update)
                        
                        if result:
                            print(f"[Bot] Handled update: {result.get('action', 'unknown')}")
                
                # Clean old user states (older than 10 minutes)
                current_time = time.time()
                to_remove = []
                for user_id, state in self.user_states.items():
                    if current_time - state.get('timestamp', 0) > 600:  # 10 minutes
                        to_remove.append(user_id)
                
                for user_id in to_remove:
                    del self.user_states[user_id]
                
                if to_remove:
                    self._save_user_states()
                
            except KeyboardInterrupt:
                print("[Bot] Stopping by user request...")
                self.running = False
                break
            except Exception as e:
                print(f"[Bot] Error: {e}")
                traceback.print_exc()
                time.sleep(5)
    
    def start_notification_scheduler(self, interval_minutes=5):
        """Start background notification scheduler"""
        def scheduler():
            while self.running:
                try:
                    print(f"[Scheduler] Running notification cycle at {time.strftime('%Y-%m-%d %H:%M:%S')}")
                    result = run_notification_cycle(dry_run=False)
                    print(f"[Scheduler] Cycle result: {result}")
                except Exception as e:
                    print(f"[Scheduler] Error: {e}")
                    traceback.print_exc()
                
                # Wait for next interval
                time.sleep(interval_minutes * 60)
        
        self.notification_thread = threading.Thread(target=scheduler, daemon=True)
        self.notification_thread.start()
        print(f"[Bot] Started notification scheduler with {interval_minutes} minute interval")
    
    def start(self):
        """Start the bot"""
        self.running = True
        
        # Start notification scheduler
        self.start_notification_scheduler(interval_minutes=5)
        
        # Start processing updates
        self.process_updates()
    
    def stop(self):
        """Stop the bot"""
        self.running = False
        print("[Bot] Stopped")


def main():
    """Main entry point"""
    print("=" * 60)
    print("🤖 AnimeVist Personal Notification Bot")
    print("=" * 60)
    
    # Load config
    config = load_config()
    bot_token = config['telegram']['bot_token']
    supabase_url = config['cloud_storage']['supabase_url']
    supabase_key = config['cloud_storage']['supabase_key']
    
    if not bot_token:
        print("❌ Error: Bot token not configured")
        print("Set TELEGRAM_BOT_TOKEN in config.json or environment variable")
        return
    
    if not supabase_url or not supabase_key:
        print("⚠️  Warning: Supabase URL/key not fully configured")
        print("Some features may not work correctly")
    
    print(f"Bot Token: {'✓ Configured' if bot_token else '✗ Missing'}")
    print(f"Supabase URL: {'✓ Configured' if supabase_url else '✗ Missing'}")
    print(f"Supabase Key: {'✓ Configured' if supabase_key else '✗ Missing'}")
    print("\nStarting bot...")
    
    try:
        bot = AnimeVistPersonalBot()
        bot.start()
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Error starting bot: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()

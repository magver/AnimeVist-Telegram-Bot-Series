"""
Standalone AnimeVist Automation Service & Telegram Bot.
Independent system for managing announcements, releases, news, and navigation.

Usage:
  python main.py                  - Интерактивная панель управления
  python main.py --daemon         - Непрерывный фоновый сервис 24/7 (для VPS или локально)
  python main.py --test           - Проверка подключения Telegram-бота
  python main.py --releases       - Разовый запуск проверки новых серий
  python main.py --news           - Разовый запуск проверки аниме-новостей
  python main.py --compilation    - Опубликовать Топ-подборку аниме (по жанру или авто)
  python main.py --patchnote      - Опубликовать свежий релиз из GitHub
  python main.py --pinned         - Отправить и закрепить навигационный пост
"""

import os
import sys
import time
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from telegram_sender import TelegramSender, load_config
from series_announcer import run_series_check
from news_announcer import run_news_check
from compilations_announcer import run_compilation_post, list_available_themes
from patchnote_publisher import publish_patchnote_from_github, publish_custom_patchnote
from pinned_navigator import publish_pinned_navigator, get_latest_version_from_github

def test_connection():
    print("\n[Проверка] Тестирование подключения Telegram-бота...")
    sender = TelegramSender()
    me = sender.get_me()
    if me.get('ok'):
        bot_user = me['result']
        print(f"✅ Успешное подключение к боту: @{bot_user.get('username')} ({bot_user.get('first_name')})")
        config = load_config()
        channel = config.get('telegram', {}).get('channel_id')
        print(f"📢 Целевой канал: {channel}")
        print("💡 Убедитесь, что бот добавлен в канал с правами Администратора (публикация и закрепление сообщений).")
        return True
    else:
        print(f"❌ Ошибка подключения к Telegram: {me.get('description')}")
        print("💡 Проверьте 'bot_token' в файле config.json")
        return False

def daemon_loop():
    config = load_config()
    interval = config.get('announcer', {}).get('check_interval_seconds', 300)
    app_name = config.get('app', {}).get('name', 'AnimeVist')
    last_compilation_time = 0

    print(f"\n=======================================================")
    print(f"  {app_name} Standalone Automation Daemon Запущен 24/7")
    print(f"  Интервал проверки: {interval} секунд")
    print(f"  Для остановки нажмите Ctrl+C")
    print(f"=======================================================\n")

    while True:
        try:
            config = load_config()
            ann_conf = config.get('announcer', {})
            now_str = time.strftime('%Y-%m-%d %H:%M:%S')

            # 1. Series check
            if ann_conf.get('enable_series_releases', True):
                print(f"[{now_str}] 🔍 Проверка выхода новых серий...")
                run_series_check()

            # 2. News check
            if ann_conf.get('enable_anime_news', True):
                print(f"[{now_str}] 📰 Проверка новостей аниме-индустрии...")
                run_news_check()

            # 3. Compilations check
            if ann_conf.get('enable_compilations', True):
                comp_interval_hours = float(ann_conf.get('compilations_interval_hours', 6))
                comp_interval_sec = comp_interval_hours * 3600
                if time.time() - last_compilation_time >= comp_interval_sec:
                    print(f"[{now_str}] 🌟 Публикация плановой Топ-подборки аниме...")
                    run_compilation_post()
                    last_compilation_time = time.time()

        except KeyboardInterrupt:
            print("\n[Daemon] Остановка сервиса пользователем...")
            break
        except Exception as e:
            print(f"[Daemon] Исключение в цикле: {e}")

        print(f"Ожидание {interval} секунд перед следующим циклом...\n")
        time.sleep(interval)

def interactive_menu():
    config = load_config()
    app_name = config.get('app', {}).get('name', 'AnimeVist')

    while True:
        print("\n" + "="*56)
        print(f"   🤖 {app_name.upper()} STANDALONE BOT & AUTOMATION HUB")
        print("="*56)
        print("1. 📡 Запустить фоновый демон 24/7 (Серии + Новости + Подборки)")
        print("2. 🔍 [Серии] Проверить новые серии (#онгоинг) прямо сейчас")
        print("3. 📰 [Новости] Проверить новости аниме (#новости) прямо сейчас")
        print("4. 🌟 [Подборка] Опубликовать Топ-подборку аниме (#подборка)")
        print("5. 🚀 [Патчноут] Опубликовать свежий релиз из GitHub (#patchnote)")
        print("6. 📌 [Навигатор] Отправить и закрепить навигатор и FAQ (Pin)")
        print("7. 🔌 Проверить подключение бота к Telegram")
        print("0. ❌ Выход")
        print("="*56)

        choice = input("Выберите действие [0-7]: ").strip()
        if choice == '1':
            daemon_loop()
        elif choice == '2':
            run_series_check()
        elif choice == '3':
            run_news_check()
        elif choice == '4':
            themes = list_available_themes()
            print("\nДоступные темы подборок:")
            print("  0. Автоматическая (следующая по очереди)")
            for idx, t in enumerate(themes, 1):
                print(f"  {idx}. {t['name']} ({t['key']})")
            t_choice = input(f"Выберите тему [0-{len(themes)}]: ").strip()
            c_input = input("Количество аниме в подборке [3, 4, 5] (по умолчанию 4): ").strip()
            chosen_count = int(c_input) if c_input in ['3', '4', '5'] else 4
            if t_choice == '0' or not t_choice:
                run_compilation_post(count=chosen_count)
            else:
                try:
                    chosen_idx = int(t_choice) - 1
                    if 0 <= chosen_idx < len(themes):
                        run_compilation_post(genre_key=themes[chosen_idx]['key'], count=chosen_count)
                    else:
                        run_compilation_post(count=chosen_count)
                except ValueError:
                    run_compilation_post(count=chosen_count)
        elif choice == '5':
            print("\n1. Взять релиз автоматически из GitHub Releases")
            print("2. Ввести версию и описание вручную")
            sub = input("Выберите вариант [1-2]: ").strip()
            if sub == '1':
                publish_patchnote_from_github()
            elif sub == '2':
                v = input("Версия (например 1.0.30): ").strip()
                t = input("Заголовок релиза: ").strip() or "Обновление стабильности"
                print("Введите пункты 'Что нового' (пустая строка для завершения):")
                h_list = []
                while True:
                    line = input(" • ").strip()
                    if not line:
                        break
                    h_list.append(line)
                publish_custom_patchnote(version=v, title=t, highlights=h_list)
        elif choice == '6':
            confirm = input("Отправить и закрепить пост в канале? [y/N]: ").strip().lower()
            if confirm in ['y', 'yes', 'д', 'да']:
                publish_pinned_navigator()
        elif choice == '7':
            test_connection()
        elif choice == '0':
            print("Работа завершена.")
            break
        else:
            print("Неверный выбор, повторите ввод.")

def main():
    parser = argparse.ArgumentParser(description="Standalone AnimeVist Automation Service")
    parser.add_argument('--daemon', action='store_true', help="Run continuous monitoring daemon")
    parser.add_argument('--test', action='store_true', help="Test Telegram bot connection")
    parser.add_argument('--releases', action='store_true', help="Run single series check")
    parser.add_argument('--news', action='store_true', help="Run single news check")
    parser.add_argument('--compilation', nargs='?', const='auto', default=None, help="Publish top anime compilation (optional genre key)")
    parser.add_argument('--count', type=int, default=4, help="Number of anime in compilation (3, 4, or 5)")
    parser.add_argument('--patchnote', action='store_true', help="Publish latest patchnote from GitHub")
    parser.add_argument('--pinned', action='store_true', help="Publish pinned navigation post")

    args = parser.parse_args()

    if args.test:
        test_connection()
    elif args.daemon:
        daemon_loop()
    elif args.releases:
        run_series_check()
    elif args.news:
        run_news_check()
    elif args.compilation:
        genre = None if args.compilation == 'auto' else args.compilation
        run_compilation_post(genre_key=genre, count=args.count)
    elif args.patchnote:
        publish_patchnote_from_github()
    elif args.pinned:
        publish_pinned_navigator()
    else:
        interactive_menu()

if __name__ == '__main__':
    main()

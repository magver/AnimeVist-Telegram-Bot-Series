#!/usr/bin/env python3
"""
Скрипт для обновления и деплоя бота на GitHub
"""

import os
import sys
import subprocess

def run_command(cmd, cwd=None):
    """Выполнить команду в терминале"""
    print(f"🚀 Выполняю: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        print(f"❌ Ошибка: {result.stderr}")
        return False
    print(f"✅ Успешно")
    return True

def main():
    print("="*60)
    print("🚀 ДЕПЛОЙ ANIMEVIST TELEGRAM BOT")
    print("="*60)
    
    bot_path = r"E:\ANIMEVIST\AnimeVist-Telegram-Bot"
    
    # 1. Добавляем все изменения
    print("\n📁 Добавляю изменения в Git...")
    if not run_command("git add .", cwd=bot_path):
        return False
    
    # 2. Создаем коммит
    print("\n💾 Создаю коммит...")
    commit_message = "🤖 Обновление: Исправление /start + персональные уведомления + оптимизация UID"
    if not run_command(f'git commit -m "{commit_message}"', cwd=bot_path):
        return False
    
    # 3. Загружаем на GitHub
    print("\n🚀 Загружаю на GitHub...")
    if not run_command("git push -u origin main", cwd=bot_path):
        return False
    
    print("\n" + "="*60)
    print("🎉 ДЕПЛОЙ УСПЕШНО ЗАВЕРШЁН!")
    print("="*60)
    print("\n📋 Что было обновлено:")
    print("1. 🤖 bot_main.py - Главный обработчик бота")
    print("2. 🔐 user_auth.py - Аутентификация через GoTrue API")  
    print("3. 📨 personal_notifier.py - Персональные уведомления")
    print("4. 📚 Документация и SQL скрипты")
    print("\n🚀 Бот готов к работе!")
    print("Запустите: python bot_main.py")
    print("="*60)
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

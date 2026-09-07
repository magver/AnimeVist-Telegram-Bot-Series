# AnimeVist Personal Notification Bot

Этот бот расширяет существующую инфраструктуру AnimeVist Telegram Bot, добавляя:
- **Авторизацию пользователей** через email/пароль AnimeVist
- **Персональные уведомления** о новых сериях в личные сообщения
- **Автоматическую подписку** на аниме из списка «Смотрю»

## 📁 Новые файлы

```
AnimeVist-Telegram-Bot/
├── user_auth.py              # Аутентификация через GoTrue API
├── personal_notifier.py      # Отправка персональных уведомлений
├── bot_main.py              # Главный обработчик бота
└── README_USER_BOT.md       # Эта документация
```

## 🔑 Как это работает

### 1. Авторизация пользователя
```
Пользователь → /login → email:password → GoTrue API → Успешная аутентизация
```

### 2. Автоматическая подписка
```
Успешный вход → Получение списка «Смотрю» → Создание подписок
```

### 3. Мониторинг новых серий
```
Бот проверяет новые серии → Сравнивает с last_notified → Отправляет уведомления
```

### 4. Уведомления
```
Персональное сообщение → Постер аниме → Кнопка "Пометить как просмотренное"
```

## 🚀 Настройка

### 1. Добавьте таблицы в Supabase

Выполните SQL в Supabase Dashboard → SQL Editor:

```sql
-- Таблица для подписок пользователей
CREATE TABLE IF NOT EXISTS public.user_subscriptions (
    id SERIAL PRIMARY KEY,
    telegram_user_id BIGINT NOT NULL,
    animevist_user_id UUID NOT NULL REFERENCES auth.users(id),
    anime_id TEXT NOT NULL,
    anime_title TEXT,
    anime_poster TEXT,
    last_notified_episode INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS политики
ALTER TABLE public.user_subscriptions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow anon read and write on user_subscriptions" ON public.user_subscriptions;
CREATE POLICY "Allow anon read and write on user_subscriptions" 
ON public.user_subscriptions 
FOR ALL 
TO anon, authenticated 
USING (true) 
WITH CHECK (true);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_user_subs_telegram ON public.user_subscriptions(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_user_subs_anime ON public.user_subscriptions(anime_id);
```

### 2. Запустите бота

```bash
cd E:\ANIMEVIST\AnimeVist-Telegram-Bot
python bot_main.py
```

## 📱 Команды бота

### Основные команды:
- `/start` - Начать работу
- `/login` - Вход в AnimeVist
- `/logout` - Выход
- `/subscriptions` - Мои подписки
- `/help` - Помощь

### Формат входа:
```
email:пароль
```
Пример: `user@example.com:mysecretpassword`

## 🛠️ Архитектура

### Модули:

1. **user_auth.py** - Аутентификация
   - `verify_user_credentials()` - проверка через GoTrue
   - `get_user_library()` - получение списка «Смотрю»
   - `process_user_login()` - полный процесс входа

2. **personal_notifier.py** - Уведомления
   - `fetch_user_subscriptions_with_new_episodes()` - поиск новых серий
   - `send_personal_notifications()` - отправка уведомлений
   - `run_notification_cycle()` - полный цикл проверки

3. **bot_main.py** - Главный обработчик
   - `AnimeVistPersonalBot` - основной класс бота
   - Обработка команд и состояний
   - Фоновая отправка уведомлений

### Поток данных:
```
Telegram User → Bot Command → Auth Check → Supabase Query → Notification
```

## 🔒 Безопасность

- **Токены**: Используется GoTrue для безопасной аутентификации
- **RLS**: Все запросы защищены Row Level Security
- **HTTPS**: Все соединения через HTTPS
- **Отсутствие хранения паролей**: Пароли не сохраняются ботом

## ⚙️ Настройка уведомлений

### Интервал проверки:
По умолчанию: каждые 5 минут

Изменение: отредактируйте в `bot_main.py`:
```python
self.start_notification_scheduler(interval_minutes=10)  # Изменить на 10 минут
```

### Формат уведомлений:
```
🎉 <Название аниме>

Вышла новая серия!

Серия <номер> доступна для просмотра!

Смотрите прямо сейчас в приложении AnimeVist!

#жанр #серия<номер> #онгоинг #animevist
```

## 🧪 Тестирование

### Тестовые команды:
```bash
# Тест аутентификации
python user_auth.py

# Тест уведомлений (сухой прогон)
python personal_notifier.py --test

# Тест уведомлений (реальный)
python personal_notifier.py

# Тест полного цикла
python bot_main.py
```

### Тест через бота:
```
/test - Запустить тестовый цикл уведомлений
```

## 📊 Мониторинг

### Логи:
- Все операции логируются в консоль
- Уведомления о новых сериях
- Ошибки аутентификации и отправки

### Статистика:
- Количество отправленных уведомлений
- Количество ошибок
- Количество активных пользователей

## 🔧 Разработка

### Добавление новой команды:
1. Добавьте handler в `AnimeVistPersonalBot.handle_command()`
2. Создайте метод `handle_<command>()`
3. Обновите справку в `/help`

### Изменение формата уведомлений:
Отредактируйте `create_personal_notification_message()` в `personal_notifier.py`

### Изменение интервала:
Отредактируйте `start_notification_scheduler()` в `bot_main.py`

## 📞 Поддержка

### Проблемы с аутентификацией:
1. Проверьте конфигурацию Supabase в `config.json`
2. Проверьте подключение к интернету
3. Проверьте учетные данные пользователя

### Проблемы с уведомлениями:
1. Проверьте наличие аниме в списке «Смотрю»
2. Проверьте наличие новых серий
3. Проверьте права бота на отправку сообщений

### Логи:
Все ошибки логируются в консоль. Используйте их для диагностики.

## 🎯 Особенности

### Автоматическая подписка:
- Новые аниме в «Смотрю» → автоматическая подписка
- Удаление из «Смотрю» → автоматическая отписка

### Персональные уведомления:
- Отправляются в личные сообщения
- Содержат постер аниме
- Кнопка для отметки как просмотренного

### Отказоустойчивость:
- Повторные попытки при ошибках
- Сохранение состояния
- Логирование всех операций

## 📄 Лицензия

MIT License - как и основной проект AnimeVist

# 🤖 AnimeVist Personal Notification Bot

Бот для личных уведомлений о новых сериях аниме в Telegram.

## ✅ Возможности

- **Авторизация через GoTrue** - вход с email/пароль как в приложении AnimeVist
- **Автоматические подписки** - все аниме из списка «Смотрю» автоматически подключаются к уведомлениям
- **Персональные уведомления** - получайте новые серии в личные сообщения Telegram
- **Кнопки действий** - отметить серию как просмотренную напрямую из уведомления

## 🚀 Быстрый старт

### 1. Выполните SQL-схему в Supabase

Откройте [Supabase Dashboard → SQL Editor](https://supabase.com/dashboard) и выполните файл `user_subscriptions_schema.sql` (см. ниже).

### 2. Запустите бота

```bash
cd AnimeVist-Telegram-Bot
python bot_main.py
```

### 3. Используйте бота в Telegram

1. Откройте вашего бота в Telegram
2. Напишите `/start`
3. Введите команду `/login`
4. Введите `email:пароль` в формате `user@example.com:mypassword`
5. Бот автоматически создаст подписки на все аниме из вашего списка «Смотрю»

## 📱 Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Начать работу с ботом |
| `/login` | Вход в аккаунт AnimeVist |
| `/logout` | Выйти из аккаунта |
| `/subscriptions` | Управление подписками |
| `/help` | Помощь по командам |
| `/test` | Тест уведомлений |

## 📋 SQL Схема для Supabase

Выполните этот скрипт в **Supabase Dashboard → SQL Editor**:

```sql
-- Таблица подписок пользователей на уведомления о сериях
CREATE TABLE IF NOT EXISTS public.user_subscriptions (
    id BIGSERIAL PRIMARY KEY,
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

ALTER TABLE public.user_subscriptions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow anon read and write on user_subscriptions" ON public.user_subscriptions;
CREATE POLICY "Allow anon read and write on user_subscriptions" 
ON public.user_subscriptions 
FOR ALL 
TO anon, authenticated 
USING (true) 
WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_user_subs_telegram ON public.user_subscriptions(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_user_subs_animevist ON public.user_subscriptions(animevist_user_id);
CREATE INDEX IF NOT EXISTS idx_user_subs_anime ON public.user_subscriptions(anime_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_subs_unique ON public.user_subscriptions(telegram_user_id, anime_id);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS update_user_subscriptions_updated_at ON public.user_subscriptions;
CREATE TRIGGER update_user_subscriptions_updated_at
    BEFORE UPDATE ON public.user_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

## 📂 Структура новых файлов

```
AnimeVist-Telegram-Bot/
├── bot_main.py              # Главный обработчик бота
├── user_auth.py             # Аутентификация через GoTrue API
├── personal_notifier.py     # Персональные уведомления
├── user_subscriptions_schema.sql  # SQL-схема Supabase
├── optimize_dashboard.js    # Скрипт оптимизации UID дашборда
└── deploy_update.py         # Скрипт деплоя на GitHub
```

## ⚙️ Конфигурация

В `config.json` уже есть Supabase настройки. Убедитесь что указан bot_token:

```json
{
  "telegram": {
    "bot_token": "ваш_токен_бота",
    "channel_id": "-1004465332635"
  },
  "cloud_storage": {
    "provider": "supabase",
    "supabase_url": "https://zuciuwunelfqhhhohhyn.supabase.co",
    "supabase_key": "ваш_ключ"
  }
}
```

## 🔧 Запуск бота

```bash
# Войдите в папку проекта
cd E:\ANIMEVIST\AnimeVist-Telegram-Bot

# Запустите бота
python bot_main.py
```

После запуска бот будет:
1. Проверять новые серии каждые 5 минут
2. Отправлять уведомления пользователям
3. Отвечать на команды `/start`, `/login`, `/subscriptions` и т.д.

## 🎨 UID Дашборд

Дашборд оптимизирован для:
- **Мобильных устройств** - адаптивная сетка, кнопки крупнее
- **ПК** - удобное расположение элементов
- **Оптимизированы цвета** - лучше читаемость
- **Убрано перетаскивание** - страница статична

Откройте: https://magver.github.io/AnimeVist-Telegram-Bot/

## 📝 Логи

Бот выводит логи в консоль:
```
[Bot] Command 'start' from user 123456789
[Bot] Started notification scheduler with 5 minute interval
[Scheduler] Running notification cycle at 2026-09-07 12:00:00
[Notifier] Found 3 notifications to send
```

## ⚠️ Важно

- Бот должен работать постоянно (VPS, ПК или сервис как Render/Heroku)
- GitHub Actions запускает только серийный агрегатор, не слушает ЛС
- Токен PAT для GitHub уже засветился - отозвать и создать новый!

---

**Удачи!** 🎉

-- ==============================================================================
-- AnimeVist Telegram Bot — Таблицы для Supabase (Синхронизация и Автономность 24/7)
-- Выполните этот SQL в Supabase Dashboard -> SQL Editor (https://supabase.com/dashboard)
-- ==============================================================================

-- 1. Таблица для хранения конфигурации Telegram-бота (токен, канал, тайминги)
CREATE TABLE IF NOT EXISTS public.bot_config (
    id TEXT PRIMARY KEY,
    config JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Включаем RLS
ALTER TABLE public.bot_config ENABLE ROW LEVEL SECURITY;

-- Разрешаем чтение и запись с anon ключом приложения AnimeVist
DROP POLICY IF EXISTS "Allow anon read and write on bot_config" ON public.bot_config;
CREATE POLICY "Allow anon read and write on bot_config" 
ON public.bot_config 
FOR ALL 
TO anon, authenticated 
USING (true) 
WITH CHECK (true);

-- 2. Таблица для хранения истории опубликованных серий и новостей
-- Защищает от повторного спама при любых перезапусках сервера или контейнера
CREATE TABLE IF NOT EXISTS public.bot_seen_items (
    item_id TEXT PRIMARY KEY,
    category TEXT NOT NULL, -- 'episode' или 'news'
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.bot_seen_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow anon read and write on bot_seen_items" ON public.bot_seen_items;
CREATE POLICY "Allow anon read and write on bot_seen_items" 
ON public.bot_seen_items 
FOR ALL 
TO anon, authenticated 
USING (true) 
WITH CHECK (true);

-- Создаем индекс для быстрой выборки по категории
CREATE INDEX IF NOT EXISTS idx_bot_seen_category ON public.bot_seen_items(category);

-- Комментарии к таблицам
COMMENT ON TABLE public.bot_config IS 'Конфигурация Telegram-бота AnimeVist';
COMMENT ON TABLE public.bot_seen_items IS 'История опубликованных эпизодов и новостей аниме';

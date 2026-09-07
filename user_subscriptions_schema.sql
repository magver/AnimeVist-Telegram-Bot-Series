-- ==============================================================================
-- SQL Схема для таблицы подписок пользователей
-- Запустите в Supabase Dashboard → SQL Editor
-- ==============================================================================

-- 1. Таблица для подписок пользователей на уведомления
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

-- Включаем RLS
ALTER TABLE public.user_subscriptions ENABLE ROW LEVEL SECURITY;

-- Политика: разрешаем чтение и запись для анонимного доступа (бот)
DROP POLICY IF EXISTS "Allow anon read and write on user_subscriptions" ON public.user_subscriptions;
CREATE POLICY "Allow anon read and write on user_subscriptions" 
ON public.user_subscriptions 
FOR ALL 
TO anon, authenticated 
USING (true) 
WITH CHECK (true);

-- Политика: пользователи могут видеть только свои подписки
DROP POLICY IF EXISTS "Users can view own subscriptions" ON public.user_subscriptions;
CREATE POLICY "Users can view own subscriptions" 
ON public.user_subscriptions 
FOR SELECT 
TO authenticated 
USING (auth.uid() = animevist_user_id);

-- 2. Индексы для быстрого поиска
-- По Telegram ID пользователя
CREATE INDEX IF NOT EXISTS idx_user_subs_telegram 
ON public.user_subscriptions(telegram_user_id);

-- По ID пользователя AnimeVist
CREATE INDEX IF NOT EXISTS idx_user_subs_animevist 
ON public.user_subscriptions(animevist_user_id);

-- По ID аниме
CREATE INDEX IF NOT EXISTS idx_user_subs_anime 
ON public.user_subscriptions(anime_id);

-- Для поиска активных подписок с новыми сериями
CREATE INDEX IF NOT EXISTS idx_user_subs_active_new 
ON public.user_subscriptions(active, last_notified_episode);

-- Для уникальной подписки пользователя на аниме
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_subs_unique 
ON public.user_subscriptions(telegram_user_id, anime_id);

-- 3. Триггер для обновления updated_at
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

-- 4. Комментарии к таблице
COMMENT ON TABLE public.user_subscriptions IS 'Подписки пользователей на уведомления о новых сериях аниме';
COMMENT ON COLUMN public.user_subscriptions.telegram_user_id IS 'ID пользователя в Telegram';
COMMENT ON COLUMN public.user_subscriptions.animevist_user_id IS 'ID пользователя в AnimeVist (auth.users)';
COMMENT ON COLUMN public.user_subscriptions.anime_id IS 'ID аниме (например vost-3978)';
COMMENT ON COLUMN public.user_subscriptions.last_notified_episode IS 'Последняя серия, о которой было отправлено уведомление';
COMMENT ON COLUMN public.user_subscriptions.active IS 'Активна ли подписка (true/false)';

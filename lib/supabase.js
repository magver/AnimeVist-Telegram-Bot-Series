import { fetch } from 'sdk';

const SUPABASE_URL = 'https://zuciuwunelfqhhhohhyn.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp1Y2l1d3VuZWxmcWhoaG9oaHluIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODgwODgwOTcsImV4cCI6MjEwMzY2NDA5N30.JTxCO-GWXtLLBWLwE5I6AsmXvKrGNGQ9J6sS7QM4ITQ';

export async function signIn(email, password) {
  try {
    const res = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
      method: 'POST',
      headers: {
        'apikey': SUPABASE_KEY,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email: email.trim().toLowerCase(), password }),
    });
    const data = await res.json();
    if (res.ok && data.user && data.access_token) {
      return { success: true, user: data.user };
    }
    return { success: false, error: data.error_description || data.msg || data.error || 'Неверный email или пароль' };
  } catch (e) {
    return { success: false, error: e.message || 'Ошибка сети' };
  }
}

export async function getWatchingLibrary(userId) {
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/user_library?user_id=eq.${userId}&status=eq.watching&select=*`, {
      headers: {
        'apikey': SUPABASE_KEY,
        'Authorization': `Bearer ${SUPABASE_KEY}`,
      }
    });
    if (res.ok) {
      return await res.json();
    }
    return [];
  } catch {
    return [];
  }
}

export async function bindTelegramUser(telegramUserId, animevistUserId, email) {
  try {
    await fetch(`${SUPABASE_URL}/rest/v1/telegram_user_bindings`, {
      method: 'POST',
      headers: {
        'apikey': SUPABASE_KEY,
        'Authorization': `Bearer ${SUPABASE_KEY}`,
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates'
      },
      body: JSON.stringify({
        telegram_user_id: telegramUserId,
        animevist_user_id: animevistUserId,
        email: email
      })
    });
  } catch (e) {
    console.error('Error binding tg user:', e);
  }
}

export async function syncSubscriptions(telegramUserId, animevistUserId) {
  try {
    const library = await getWatchingLibrary(animevistUserId);
    for (const item of library) {
      const anime = item.anime_data || item.anime || {};
      const animeId = item.anime_id;
      const title = anime.title || item.anime_title || 'Аниме';
      const poster = anime.poster || item.poster || '';
      
      if (animeId) {
        await fetch(`${SUPABASE_URL}/rest/v1/telegram_user_subscriptions`, {
          method: 'POST',
          headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': `Bearer ${SUPABASE_KEY}`,
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates'
          },
          body: JSON.stringify({
            telegram_user_id: telegramUserId,
            animevist_user_id: animevistUserId,
            anime_id: animeId,
            anime_title: title,
            anime_poster: poster,
            active: true
          })
        });
      }
    }
    return library.length;
  } catch (e) {
    console.error('Error syncing subs:', e);
    return 0;
  }
}

export async function getSubscriptions(telegramUserId) {
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/telegram_user_subscriptions?telegram_user_id=eq.${telegramUserId}&active=eq.true&select=*`, {
      headers: {
        'apikey': SUPABASE_KEY,
        'Authorization': `Bearer ${SUPABASE_KEY}`,
      }
    });
    if (res.ok) {
      return await res.json();
    }
    return [];
  } catch {
    return [];
  }
}

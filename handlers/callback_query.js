import { callbackQuery } from 'sdk';
import { db } from 'sdk/db';
import { userStates } from '../schema.js';
import { getSubscriptions, syncSubscriptions } from '../lib/supabase.js';

callbackQuery(async (ctx) => {
  const chatId = ctx.chat.id;
  const data = ctx.data;

  if (data === 'btn_login') {
    await db.insert(userStates).values({ chatId, state: 'awaiting_email', email: '' }).onConflictDoUpdate({ target: userStates.chatId, set: { state: 'awaiting_email', email: '' } }).run();
    await ctx.answer();
    await ctx.reply('📧 Введите ваш <b>email</b> от аккаунта AnimeVist:', {
      parse_mode: 'HTML',
      reply_markup: {
        inline_keyboard: [[{ text: '❌ Отмена', callback_data: 'btn_cancel' }]]
      }
    });
    return;
  }

  if (data === 'btn_subs') {
    await ctx.answer();
    const subs = await getSubscriptions(chatId);
    if (subs.length === 0) {
      await ctx.reply('📭 У вас пока нет активных подписок. Добавьте аниме в раздел "Смотрю" в приложении AnimeVist!', {
        reply_markup: {
          inline_keyboard: [[{ text: '🔄 Обновить', callback_data: 'btn_subs' }, { text: '🔑 Войти / Сменить аккаунт', callback_data: 'btn_login' }]]
        }
      });
    } else {
      let msg = '📋 <b>Ваши подписки (Смотрю):</b>\n\n';
      subs.forEach((s, index) => {
        msg += `${index + 1}. <b>${s.anime_title}</b>\n`;
      });
      await ctx.reply(msg, {
        parse_mode: 'HTML',
        reply_markup: {
          inline_keyboard: [[{ text: '🔄 Синхронизировать подписки', callback_data: 'btn_sync' }, { text: '🚪 Выйти', callback_data: 'btn_logout' }]]
        }
      });
    }
    return;
  }

  if (data === 'btn_sync') {
    await ctx.answer('Синхронизация...');
    // We need animevist_user_id or can fetch from binding table if stored, but let's do quick fetch or message user
    // For simplicity, let's fetch subscription or prompt re-login if needed
    const subs = await getSubscriptions(chatId);
    if (subs.length > 0 && subs[0].animevist_user_id) {
      const count = await syncSubscriptions(chatId, subs[0].animevist_user_id);
      await ctx.reply(`✅ Подписки успешно синхронизированы! Активных: <b>${count}</b>`, {
        parse_mode: 'HTML',
        reply_markup: {
          inline_keyboard: [[{ text: '📋 Мои подписки', callback_data: 'btn_subs' }]]
        }
      });
    } else {
      await ctx.reply('⚠️ Пожалуйста, войдите в аккаунт заново через /login', {
        reply_markup: {
          inline_keyboard: [[{ text: '🔑 Войти', callback_data: 'btn_login' }]]
        }
      });
    }
    return;
  }

  if (data === 'btn_logout') {
    await db.delete(userStates).where({ chatId }).run();
    await ctx.answer('Вы вышли');
    await ctx.reply('🚪 Вы вышли из аккаунта. Для повторного входа нажмите кнопку ниже:', {
      reply_markup: {
        inline_keyboard: [[{ text: '🔑 Войти', callback_data: 'btn_login' }]]
      }
    });
    return;
  }

  if (data === 'btn_cancel') {
    await db.delete(userStates).where({ chatId }).run();
    await ctx.answer('Отменено');
    await ctx.reply('❌ Действие отменено. Главное меню — /start');
    return;
  }

  if (data === 'btn_help') {
    await ctx.answer();
    await ctx.reply(
      'ℹ️ <b>Справка по боту AnimeVist:</b>\n\n' +
      '1. Нажмите <b>«🔑 Войти»</b> и введите свои учетные данные (email и пароль) от приложения <b>AnimeVist</b>.\n' +
      '2. Бот автоматически привяжет ваш Telegram к вашему аккаунту и загрузит список аниме со статусом <b>«Смотрю»</b>.\n' +
      '3. Как только в AnimeVist выходит новая серия по вашему аниме, бот пришлет вам уведомление в личные сообщения!\n\n' +
      'Команды:\n' +
      '/start — Главное меню\n' +
      '/login — Войти в аккаунт\n' +
      '/subscriptions — Мои подписки\n' +
      '/logout — Выйти',
      { parse_mode: 'HTML', reply_markup: { inline_keyboard: [[{ text: '🏠 Главное меню', callback_data: 'btn_subs' }]] } }
    );
    return;
  }

  await ctx.answer();
});

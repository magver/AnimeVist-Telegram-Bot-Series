import { message } from 'sdk';
import { db } from 'sdk/db';
import { userStates } from '../schema.js';
import { signIn, bindTelegramUser, syncSubscriptions, getSubscriptions } from '../lib/supabase.js';

message(async (ctx) => {
  const chatId = ctx.chat.id;
  const text = ctx.text ? ctx.text.trim() : '';

  // Check current user state in database
  let stateRecord = await db.select().from(userStates).where({ chatId }).get();

  // Handle commands
  if (text.startsWith('/start') || text.startsWith('/help')) {
    await db.delete(userStates).where({ chatId }).run();
    
    // Check if already bound in Supabase
    const subs = await getSubscriptions(chatId);
    
    let welcomeText = '👋 <b>Добро пожаловать в AnimeVist Bot!</b>\n\n' +
      'Я буду присылать вам уведомления о выходе новых серий ваших любимых аниме, на которые вы подписаны в приложении.\n\n';
    
    if (subs.length > 0) {
      welcomeText += `✅ Вы авторизованы! Активных подписок: <b>${subs.length}</b>.\n\nИспользуйте кнопки ниже для управления:`;
    } else {
      welcomeText += '🔑 Пожалуйста, войдите в свой аккаунт AnimeVist, чтобы получать уведомления о новых сериях.';
    }

    const inlineKeyboard = subs.length > 0 ? [
      [{ text: '📋 Мои подписки', callback_data: 'btn_subs' }, { text: '🚪 Выйти', callback_data: 'btn_logout' }],
      [{ text: 'ℹ️ Помощь', callback_data: 'btn_help' }]
    ] : [
      [{ text: '🔑 Войти в аккаунт', callback_data: 'btn_login' }],
      [{ text: 'ℹ️ Помощь', callback_data: 'btn_help' }]
    ];

    await ctx.reply(welcomeText, {
      parse_mode: 'HTML',
      reply_markup: { inline_keyboard }
    });
    return;
  }

  if (text.startsWith('/login')) {
    await db.insert(userStates).values({ chatId, state: 'awaiting_email', email: '' }).onConflictDoUpdate({ target: userStates.chatId, set: { state: 'awaiting_email', email: '' } }).run();
    await ctx.reply('📧 Введите ваш <b>email</b> от аккаунта AnimeVist:', {
      parse_mode: 'HTML',
      reply_markup: {
        inline_keyboard: [[{ text: '❌ Отмена', callback_data: 'btn_cancel' }]]
      }
    });
    return;
  }

  if (text.startsWith('/subscriptions')) {
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

  if (text.startsWith('/logout')) {
    await db.delete(userStates).where({ chatId }).run();
    // Also remove binding from supabase if needed
    await ctx.reply('🚪 Вы вышли из аккаунта. Для повторного входа используйте /login', {
      reply_markup: {
        inline_keyboard: [[{ text: '🔑 Войти', callback_data: 'btn_login' }]]
      }
    });
    return;
  }

  // Handle conversational state (Email / Password input)
  if (stateRecord && stateRecord.state === 'awaiting_email') {
    if (!text.includes('@')) {
      await ctx.reply('❌ Пожалуйста, введите корректный email адрес:');
      return;
    }
    await db.update(userStates).set({ state: 'awaiting_password', email: text }).where({ chatId }).run();
    await ctx.reply('🔑 Теперь введите ваш <b>пароль</b> от аккаунта AnimeVist:', {
      parse_mode: 'HTML',
      reply_markup: {
        inline_keyboard: [[{ text: '❌ Отмена', callback_data: 'btn_cancel' }]]
      }
    });
    return;
  }

  if (stateRecord && stateRecord.state === 'awaiting_password') {
    const email = stateRecord.email;
    const password = text;

    // Delete state record immediately for security
    await db.delete(userStates).where({ chatId }).run();

    const processingMsg = await ctx.reply('⏳ Выполняется авторизация...');

    const result = await signIn(email, password);
    if (!result.success) {
      await ctx.reply(`❌ Ошибка входа: ${result.error}\n\nПопробуйте снова с помощью /login`, {
        reply_markup: {
          inline_keyboard: [[{ text: '🔑 Попробовать снова', callback_data: 'btn_login' }]]
        }
      });
      return;
    }

    const user = result.user;
    await bindTelegramUser(chatId, user.id, email);
    const count = await syncSubscriptions(chatId, user.id);

    await ctx.reply(`✅ <b>Авторизация успешна!</b>\n\nСинхронизировано подписок ("Смотрю"): <b>${count}</b>\n\nТеперь вы будете получать уведомления о выходе новых серий в личные сообщения!`, {
      parse_mode: 'HTML',
      reply_markup: {
        inline_keyboard: [
          [{ text: '📋 Мои подписки', callback_data: 'btn_subs' }],
          [{ text: '🚪 Выйти', callback_data: 'btn_logout' }]
        ]
      }
    });
    return;
  }

  // Default fallback message
  await ctx.reply('❓ Неизвестная команда. Используйте /start для главного меню или /help для справки.');
});

import { table, integer, text, sql } from 'sdk/db';

export const userStates = table('user_states', {
  chatId: integer('chat_id').primaryKey(),
  state: text('state'), // 'awaiting_email', 'awaiting_password'
  email: text('email'),
  updatedAt: integer('updated_at').default(sql`(unixepoch())`),
});

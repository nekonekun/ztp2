from aiogram import Bot


class Progresser:
    def __init__(self, token: str, *args):
        self.token = token
        self.msg_ids = {chat_id: None for chat_id in args}
        self.bot: Bot | None = None
        self.done: str = ''

    def startup(self):
        self.bot = Bot(self.token)

    async def shutdown(self):
        await self.bot.session.close()

    async def greet(self, greeting_text: str):
        self.done = greeting_text + '\n'
        for chat_id in self.msg_ids:
            message = await self.bot.send_message(chat_id, self.done)
            self.msg_ids[chat_id] = message.message_id

    def update_done(self, done_step: str):
        self.done += '☒ ' + done_step + '\n'

    async def send_step(self, current_step: str):
        text = self.done + '☐ ' + current_step
        for chat_id, message_id in self.msg_ids.items():
            await self.bot.edit_message_text(text, chat_id, message_id)

    async def finish(self, goodbye_text: str):
        self.done += '☒ ' + goodbye_text
        text = self.done
        for chat_id, message_id in self.msg_ids.items():
            await self.bot.edit_message_text(text, chat_id, message_id)

    async def alert(self, alert_text):
        for chat_id, message_id in self.msg_ids.items():
            if chat_id < 0:
                await self.bot.send_message(chat_id=chat_id, text=alert_text,
                                            reply_to_message_id=message_id)

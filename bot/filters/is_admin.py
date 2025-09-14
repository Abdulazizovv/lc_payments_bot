from aiogram import types
from aiogram.dispatcher.filters import BoundFilter
from bot.loader import db


class IsAdmin(BoundFilter):
    async def check(self, message: types.Message):
        if await db.is_admin(message.from_user.id):
            return True
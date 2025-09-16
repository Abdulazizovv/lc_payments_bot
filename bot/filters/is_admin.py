from aiogram import types
from aiogram.dispatcher.filters import BoundFilter
from bot.loader import db


class IsAdmin(BoundFilter):
    async def check(self, *args, **kwargs):
        # Aiogram can pass different update objects: Message, CallbackQuery, InlineQuery, etc.
        message: types.Message = kwargs.get("message")
        callback_query: types.CallbackQuery = kwargs.get("callback_query")
        inline_query: types.InlineQuery = kwargs.get("inline_query")

        obj = message or callback_query or inline_query or (args[0] if args else None)

        user = None
        if isinstance(obj, types.Message):
            user = obj.from_user
        elif isinstance(obj, types.CallbackQuery):
            user = obj.from_user
        elif isinstance(obj, types.InlineQuery):
            user = obj.from_user

        if user is None:
            return False

        return await db.is_admin(user.id)
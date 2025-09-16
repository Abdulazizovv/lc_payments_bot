from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from bot.loader import dp, db
from bot.data.config import FINANCE_PASSWORD


@dp.message_handler(Command("admin"), state="*")
async def make_admin_with_password(message: types.Message, state: FSMContext):
    # Usage: /admin <password>
    await state.finish()
    parts = (message.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return
    pwd = parts[1].strip()
    if not FINANCE_PASSWORD:
        await message.answer("Parol sozlanmagan.")
        return
    if pwd != FINANCE_PASSWORD:
        await message.answer("❌ Noto'g'ri parol.")
        return
    # Create or update bot user and grant admin
    user = message.from_user
    # ensure user exists
    await db.create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    await db.update_user(user_id=user.id, is_admin=True)
    await message.answer("✅ Siz admin qilib tayinlandingiz.")

from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import CommandStart
from bot.loader import dp, db
from bot.filters import IsAdmin
from bot.keyboards.inline.admin import admin_main_menu_kb


@dp.message_handler(CommandStart(), IsAdmin(), state="*")
async def bot_start_admin(message: types.Message, state: FSMContext):
    await state.finish()
    
    # register user
    user = message.from_user
    await db.create_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )

    text = (
        f"Assalomu alaykum, <b>{user.full_name}</b>!\n"
        f"Siz botning admin panelidasiz.\n\n"
    )
    
    await message.answer(text, reply_markup=admin_main_menu_kb())
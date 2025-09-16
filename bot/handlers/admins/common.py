from aiogram.types import CallbackQuery
from aiogram.dispatcher import FSMContext
from bot.loader import dp
from bot.filters import IsAdmin
from bot.keyboards.inline.admin import admin_main_menu_kb


@dp.callback_query_handler(IsAdmin(), text='adm:back:home', state='*')
async def back_to_home(call: CallbackQuery, state: FSMContext):
    await state.finish()
    # If callback came from a regular message
    if call.message:
        try:
            await call.message.edit_text("Asosiy menyu:")
            await call.message.edit_reply_markup(admin_main_menu_kb())
        except Exception:
            await call.message.answer("Asosiy menyu:", reply_markup=admin_main_menu_kb())
    else:
        # Inline mode: no message object; edit via inline_message_id or send new
        try:
            await dp.bot.edit_message_text(
                text="Asosiy menyu:",
                inline_message_id=call.inline_message_id,
                reply_markup=admin_main_menu_kb(),
            )
        except Exception:
            await dp.bot.send_message(call.from_user.id, "Asosiy menyu:", reply_markup=admin_main_menu_kb())
    await call.answer()
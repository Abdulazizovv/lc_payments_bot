from aiogram import types
from aiogram.dispatcher import FSMContext
from bot.loader import dp, db
from bot.filters import IsAdmin


@dp.callback_query_handler(state="*")
async def debug_handler(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.answer("Debugging...")
    print(call.data)
    

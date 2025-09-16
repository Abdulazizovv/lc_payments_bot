from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.loader import dp, db
from bot.filters import IsAdmin


@dp.inline_handler(IsAdmin())
async def inline_search_students(query: types.InlineQuery):
    q = (query.query or '').strip()

    students = await db.search_students(query=q, limit=25) if q else await db.search_students(query='', limit=25)

    results = []
    for s in students:
        kb = InlineKeyboardMarkup(row_width=2)
        kb.add(
            InlineKeyboardButton("O'quvchini ochish", callback_data=f"adm:student:{s.id}"),
            InlineKeyboardButton("💵 To'lov qilish", callback_data=f"pay:st:{s.id}"),
        )
        results.append(
            types.InlineQueryResultArticle(
                id=f"student-{s.id}",
                title=s.full_name,
                description=s.phone_number or '-',
                input_message_content=types.InputTextMessageContent(
                    message_text=f"👤 {s.full_name} — {s.phone_number or '-'}"
                ),
                reply_markup=kb,
            )
        )

    await query.answer(results, cache_time=1, is_personal=True)

from aiogram import types
from aiogram.dispatcher import FSMContext
from asgiref.sync import sync_to_async

from bot.loader import dp
from bot.filters import IsAdmin
from bot.keyboards.inline.admin import payments_list_kb
from main.models import Payment

PAGE_SIZE = 10


async def paginate(qs, page: int, page_size: int = PAGE_SIZE):
    total = await sync_to_async(qs.count)()
    total_pages = max((total + page_size - 1) // page_size, 1)
    page = max(min(page, total_pages), 1)
    offset = (page - 1) * page_size
    items = await sync_to_async(lambda: list(qs.select_related('enrollment__student', 'enrollment__group').order_by('-paid_at')[offset:offset+page_size]))()
    return items, total_pages, page


async def build_payments_page(page: int = 1):
    qs = Payment.objects.all()
    items, total_pages, page = await paginate(qs, page)
    if not items:
        text = "To'lovlar topilmadi."
        kb = payments_list_kb(page, total_pages)
        return text, kb

    lines = ["So'nggi to'lovlar:"]
    for p in items:
        lines.append(f"• {p.enrollment.student.full_name} — {p.enrollment.group.title}: {p.amount} so'm (oy: {p.month.strftime('%Y-%m')})")
    text = "\n".join(lines)
    kb = payments_list_kb(page, total_pages)
    return text, kb


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('adm:payments:p:'), state='*')
async def payments_paged(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    page = int(call.data.split(':')[-1])

    text, kb = await build_payments_page(page)
    await call.message.edit_text(text)
    await call.message.edit_reply_markup(kb)
    await call.answer()

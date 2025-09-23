from aiogram import types
from aiogram.dispatcher import FSMContext
from asgiref.sync import sync_to_async

from bot.loader import dp
from bot.filters import IsAdmin
from bot.keyboards.inline.admin import payments_list_kb
from main.models import Payment
from django.utils import timezone
from django.db.models import Sum
from aiogram.dispatcher.filters.state import StatesGroup, State

PAGE_SIZE = 10


class PaymentsFilter(StatesGroup):
    wait_creator = State()
    wait_dfrom = State()
    wait_dto = State()
    wait_month = State()


def fmt_amount(n: int) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return str(n)


def build_filters_kb(current: dict) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    creator = current.get('c')
    dfrom = current.get('df')
    dto = current.get('dt')
    pmonth = current.get('m')
    lines = []
    lines.append(f"👤 Yaratgan: {creator or '—'}")
    lines.append(f"📅 Sana (dan): {dfrom or '—'}")
    lines.append(f"📅 Sana (gacha): {dto or '—'}")
    lines.append(f"🗓 To'lov oyi: {pmonth or '—'}")

    kb.add(
        types.InlineKeyboardButton("👤 Yaratgan (username)", callback_data="adm:payments:filters:set:c"),
        types.InlineKeyboardButton("🗓 To'lov oyi (YYYY-MM)", callback_data="adm:payments:filters:set:m"),
    )
    kb.add(
        types.InlineKeyboardButton("📅 Sana dan (YYYY-MM-DD)", callback_data="adm:payments:filters:set:df"),
        types.InlineKeyboardButton("📅 Sana gacha (YYYY-MM-DD)", callback_data="adm:payments:filters:set:dt"),
    )
    # Apply and clear
    kb.add(
        types.InlineKeyboardButton("♻️ Filterlarni tozalash", callback_data="adm:payments:filters:clear"),
        types.InlineKeyboardButton("✅ Yopish", callback_data="adm:payments:p:1"),
    )
    return "\n".join(lines), kb


def apply_filters(qs, f: dict):
    # f: {c:creator_username, df:date_from, dt:date_to, m:payment_month}
    if f.get('c'):
        qs = qs.filter(created_by__username=f['c'])
    if f.get('df'):
        try:
            df = timezone.datetime.strptime(f['df'], "%Y-%m-%d")
            qs = qs.filter(paid_at__date__gte=df.date())
        except Exception:
            pass
    if f.get('dt'):
        try:
            dt = timezone.datetime.strptime(f['dt'], "%Y-%m-%d")
            qs = qs.filter(paid_at__date__lte=dt.date())
        except Exception:
            pass
    if f.get('m'):
        try:
            m = timezone.datetime.strptime(f['m'], "%Y-%m").date()
            qs = qs.filter(month=m)
        except Exception:
            pass
    return qs


async def paginate(qs, page: int, page_size: int = PAGE_SIZE):
    total = await sync_to_async(qs.count)()
    total_pages = max((total + page_size - 1) // page_size, 1)
    page = max(min(page, total_pages), 1)
    offset = (page - 1) * page_size
    items = await sync_to_async(lambda: list(
        qs.select_related('enrollment__student', 'enrollment__group', 'created_by')
          .order_by('-paid_at')[offset:offset+page_size]
    ))()
    return items, total_pages, page


async def build_payments_page(page: int = 1, filters: dict | None = None):
    qs = Payment.objects.all()
    if filters:
        qs = apply_filters(qs, filters)
    items, total_pages, page = await paginate(qs, page)

    now = timezone.now()
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def agg_from(start_dt):
        base = Payment.objects.filter(paid_at__gte=start_dt)
        base = apply_filters(base, filters) if filters else base
        return base.aggregate(total=Sum('amount')).get('total') or 0

    today_total, month_total = await sync_to_async(agg_from)(start_today), await sync_to_async(agg_from)(start_month)

    if not items:
        text = (
            "💳 To'lovlar\n"
            f"Bugun: {fmt_amount(today_total)} so'm | Oy: {fmt_amount(month_total)} so'm\n\n"
            "Hozircha to'lovlar mavjud emas."
        )
        kb = payments_list_kb(page, total_pages)
        return text, kb

    lines = [
        "💳 So'nggi to'lovlar",
        f"Bugun: {fmt_amount(today_total)} so'm | Oy: {fmt_amount(month_total)} so'm",
        f"Sahifa: {page}/{total_pages}",
        "",
    ]

    for p in items:
        student = p.enrollment.student
        group = p.enrollment.group
        creator = None
        if getattr(p, 'created_by', None):
            creator = p.created_by.username or getattr(p.created_by, 'full_name', None) or str(p.created_by)
        lines += [
            f"• {student.full_name}",
            f"  Guruh: {group.title}",
            f"  Oy: {p.month.strftime('%Y-%m')}",
            f"  Summa: {fmt_amount(p.amount)} so'm",
            f"  Sana: {p.paid_at.strftime('%Y-%m-%d %H:%M')}",
        ]
        if creator:
            lines.append(f"  Qabul qilgan: {creator}")
        lines.append("")

    text = "\n".join(lines).rstrip()
    kb = payments_list_kb(page, total_pages)
    return text, kb


@dp.callback_query_handler(IsAdmin(), text='adm:payments:filters', state='*')
async def payments_filters(call: types.CallbackQuery, state: FSMContext):
    # Do not finish state to preserve existing filter data
    current = await state.get_data()
    # Read existing filters from state (keys: c, df, dt, m)
    f = {k: current.get(k) for k in ('c','df','dt','m') if current.get(k)}
    text, kb = build_filters_kb(f)
    await call.message.edit_text(text)
    await call.message.edit_reply_markup(kb)
    await call.answer()


@dp.callback_query_handler(IsAdmin(), text='adm:payments:filters:clear', state='*')
async def payments_filters_clear(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(c=None, df=None, dt=None, m=None)
    text, kb = await build_payments_page(page=1, filters=None)
    await call.message.edit_text(text)
    await call.message.edit_reply_markup(kb)
    await call.answer("Tozalandi")


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('adm:payments:p:'), state='*')
async def payments_paged(call: types.CallbackQuery, state: FSMContext):
    page = int(call.data.split(':')[-1])
    current = await state.get_data()
    filters = {k: current.get(k) for k in ('c','df','dt','m') if current.get(k)} or None
    text, kb = await build_payments_page(page, filters=filters)
    await call.message.edit_text(text)
    await call.message.edit_reply_markup(kb)
    await call.answer()


# ============== Filter prompts (no inline queries) ==============

@dp.callback_query_handler(IsAdmin(), text='adm:payments:filters:set:c', state='*')
async def payments_filter_set_creator_prompt(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await PaymentsFilter.wait_creator.set()
    await call.message.answer("👤 Yaratgan admin username'ini kiriting (masalan: johndoe). @ ishorasiz yozing:")


@dp.message_handler(IsAdmin(), state=PaymentsFilter.wait_creator, content_types=types.ContentTypes.TEXT)
async def payments_filter_set_creator_value(message: types.Message, state: FSMContext):
    username = (message.text or '').strip().lstrip('@')
    await state.update_data(c=username if username else None)
    current = await state.get_data()
    f = {k: current.get(k) for k in ('c','df','dt','m') if current.get(k)}
    text, kb = build_filters_kb(f)
    await state.reset_state(with_data=False)
    await message.answer("✅ Yaratgan filtr o'rnatildi.")
    await message.answer(text, reply_markup=kb)


@dp.callback_query_handler(IsAdmin(), text='adm:payments:filters:set:df', state='*')
async def payments_filter_set_dfrom_prompt(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await PaymentsFilter.wait_dfrom.set()
    await call.message.answer("📅 Boshlanish sanasini kiriting (YYYY-MM-DD):")


@dp.message_handler(IsAdmin(), state=PaymentsFilter.wait_dfrom, content_types=types.ContentTypes.TEXT)
async def payments_filter_set_dfrom_value(message: types.Message, state: FSMContext):
    text = (message.text or '').strip()
    try:
        _ = timezone.datetime.strptime(text, "%Y-%m-%d")
    except Exception:
        await message.answer("❗️ Noto'g'ri format. Iltimos, YYYY-MM-DD ko'rinishida kiriting (masalan: 2025-09-01).")
        return
    await state.update_data(df=text)
    current = await state.get_data()
    f = {k: current.get(k) for k in ('c','df','dt','m') if current.get(k)}
    text_out, kb = build_filters_kb(f)
    await state.reset_state(with_data=False)
    await message.answer("✅ Sana (dan) o'rnatildi.")
    await message.answer(text_out, reply_markup=kb)


@dp.callback_query_handler(IsAdmin(), text='adm:payments:filters:set:dt', state='*')
async def payments_filter_set_dto_prompt(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await PaymentsFilter.wait_dto.set()
    await call.message.answer("📅 Tugash sanasini kiriting (YYYY-MM-DD):")


@dp.message_handler(IsAdmin(), state=PaymentsFilter.wait_dto, content_types=types.ContentTypes.TEXT)
async def payments_filter_set_dto_value(message: types.Message, state: FSMContext):
    text = (message.text or '').strip()
    try:
        _ = timezone.datetime.strptime(text, "%Y-%m-%d")
    except Exception:
        await message.answer("❗️ Noto'g'ri format. Iltimos, YYYY-MM-DD ko'rinishida kiriting (masalan: 2025-09-30).")
        return
    await state.update_data(dt=text)
    current = await state.get_data()
    f = {k: current.get(k) for k in ('c','df','dt','m') if current.get(k)}
    text_out, kb = build_filters_kb(f)
    await state.reset_state(with_data=False)
    await message.answer("✅ Sana (gacha) o'rnatildi.")
    await message.answer(text_out, reply_markup=kb)


@dp.callback_query_handler(IsAdmin(), text='adm:payments:filters:set:m', state='*')
async def payments_filter_set_month_prompt(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    await PaymentsFilter.wait_month.set()
    await call.message.answer("🗓 To'lov oyini kiriting (YYYY-MM), masalan: 2025-09:")


@dp.message_handler(IsAdmin(), state=PaymentsFilter.wait_month, content_types=types.ContentTypes.TEXT)
async def payments_filter_set_month_value(message: types.Message, state: FSMContext):
    text = (message.text or '').strip()
    try:
        # validate format
        _ = timezone.datetime.strptime(text, "%Y-%m")
    except Exception:
        await message.answer("❗️ Noto'g'ri format. Iltimos, YYYY-MM ko'rinishida kiriting (masalan: 2025-09).")
        return
    await state.update_data(m=text)
    current = await state.get_data()
    f = {k: current.get(k) for k in ('c','df','dt','m') if current.get(k)}
    text_out, kb = build_filters_kb(f)
    await state.reset_state(with_data=False)
    await message.answer("✅ To'lov oyi o'rnatildi.")
    await message.answer(text_out, reply_markup=kb)

from aiogram import types
from aiogram.dispatcher import FSMContext
from asgiref.sync import sync_to_async

from bot.loader import dp
from bot.filters import IsAdmin
from bot.keyboards.inline.admin import groups_list_kb, group_item_kb, group_students_kb, admin_main_menu_kb, pager_buttons
from main.models import Group, Student, Payment, Enrollment
from bot.states.admin import CreateGroupState

PAGE_SIZE = 10

# Reply keyboard labels
CANCEL_TEXT = "❌ Bekor qilish"
BACK_TEXT = "⬅️ Orqaga"
SKIP_TEXT = "⏭ Skip"


def _norm(t: str | None) -> str:
    return (t or '').strip().lower()


def kb_cancel():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(CANCEL_TEXT)
    return kb


def kb_back_cancel():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(BACK_TEXT, CANCEL_TEXT)
    return kb


def kb_skip_back_cancel():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(SKIP_TEXT)
    kb.row(BACK_TEXT, CANCEL_TEXT)
    return kb


async def paginate(qs, page: int, page_size: int = PAGE_SIZE):
    total = await sync_to_async(qs.count)()
    total_pages = max((total + page_size - 1) // page_size, 1)
    page = max(min(page, total_pages), 1)
    offset = (page - 1) * page_size
    items = await sync_to_async(lambda: list(qs.order_by('-created_at')[offset:offset+page_size]))()
    return items, total_pages, page


async def show_groups_page_message(message: types.Message, page: int = 1):
    qs = Group.objects.all()
    items, total_pages, page = await paginate(qs, page)
    if not items:
        await message.answer("Guruhlar topilmadi.", reply_markup=types.ReplyKeyboardRemove())
        return
    await message.answer("Guruhlar ro'yxati:", reply_markup=groups_list_kb(items, page, total_pages))


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('adm:groups:p:'), state='*')
async def groups_paged(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    page = int(call.data.split(':')[-1])

    qs = Group.objects.all()
    items, total_pages, page = await paginate(qs, page)

    if not items:
        await call.message.edit_text("Guruhlar topilmadi.")
        await call.answer()
        return

    await call.message.edit_text("Guruhlar ro'yxati:")
    await call.message.edit_reply_markup(groups_list_kb(items, page, total_pages))
    await call.answer()


@dp.callback_query_handler(IsAdmin(), lambda c: c.data == 'adm:groups:create', state='*')
async def group_create_start(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.answer("Guruh nomini kiriting:", reply_markup=kb_cancel())
    await CreateGroupState.title.set()
    await call.answer()


# Cancel within CreateGroupState -> go to Home
@dp.message_handler(
    IsAdmin(),
    lambda m: _norm(m.text) in {_norm(CANCEL_TEXT), 'bekor qilish', 'cancel'},
    state=[CreateGroupState.title, CreateGroupState.description, CreateGroupState.chat_id, CreateGroupState.monthly_fee]
)
async def group_create_cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Asosiy menyu:", reply_markup=types.ReplyKeyboardRemove())
    await message.answer("Tanlang:", reply_markup=admin_main_menu_kb())


# Back handler
@dp.message_handler(
    IsAdmin(),
    lambda m: _norm(m.text) in {_norm(BACK_TEXT), 'orqaga', 'back'},
    state=[CreateGroupState.description, CreateGroupState.chat_id, CreateGroupState.monthly_fee]
)
async def group_create_back(message: types.Message, state: FSMContext):
    cur = await state.get_state()
    if cur == CreateGroupState.description.state:
        await CreateGroupState.title.set()
        await message.answer("Guruh nomini kiriting:", reply_markup=kb_cancel())
    elif cur == CreateGroupState.chat_id.state:
        await CreateGroupState.description.set()
        await message.answer("Guruh tavsifi (ixtiyoriy). Skip uchun tugmadan foydalaning.", reply_markup=kb_skip_back_cancel())
    elif cur == CreateGroupState.monthly_fee.state:
        await CreateGroupState.chat_id.set()
        await message.answer("Guruh chat_id (ixtiyoriy). Skip uchun tugmadan foydalaning.", reply_markup=kb_skip_back_cancel())


# Skip handler
@dp.message_handler(
    IsAdmin(),
    lambda m: _norm(m.text) in {_norm(SKIP_TEXT), 'skip'},
    state=[CreateGroupState.description, CreateGroupState.chat_id]
)
async def group_create_skip(message: types.Message, state: FSMContext):
    cur = await state.get_state()
    if cur == CreateGroupState.description.state:
        await state.update_data(description='')
        await CreateGroupState.chat_id.set()
        await message.answer("Guruh chat_id (ixtiyoriy). Skip uchun tugmadan foydalaning.", reply_markup=kb_skip_back_cancel())
    elif cur == CreateGroupState.chat_id.state:
        await state.update_data(chat_id=None)
        await CreateGroupState.monthly_fee.set()
        await message.answer("Oy to'lovi (so'm):", reply_markup=kb_back_cancel())


@dp.message_handler(IsAdmin(), state=CreateGroupState.title)
async def group_create_title(message: types.Message, state: FSMContext):
    if _norm(message.text) in {_norm(CANCEL_TEXT), _norm(BACK_TEXT)}:
        return  # handled
    await state.update_data(title=message.text.strip())
    await message.answer("Guruh tavsifi (ixtiyoriy). Skip uchun tugmadan foydalaning.", reply_markup=kb_skip_back_cancel())
    await CreateGroupState.description.set()


@dp.message_handler(IsAdmin(), state=CreateGroupState.description)
async def group_create_description(message: types.Message, state: FSMContext):
    if _norm(message.text) in {_norm(CANCEL_TEXT), _norm(BACK_TEXT), _norm(SKIP_TEXT)}:
        return  # handled
    await state.update_data(description=message.text.strip())
    await message.answer("Guruh chat_id (ixtiyoriy). Skip uchun tugmadan foydalaning.", reply_markup=kb_skip_back_cancel())
    await CreateGroupState.chat_id.set()


@dp.message_handler(IsAdmin(), state=CreateGroupState.chat_id)
async def group_create_chat_id(message: types.Message, state: FSMContext):
    if _norm(message.text) in {_norm(CANCEL_TEXT), _norm(BACK_TEXT), _norm(SKIP_TEXT)}:
        return  # handled
    await state.update_data(chat_id=message.text.strip())
    await message.answer("Oy to'lovi (so'm):", reply_markup=kb_back_cancel())
    await CreateGroupState.monthly_fee.set()


@dp.message_handler(IsAdmin(), state=CreateGroupState.monthly_fee)
async def group_create_fee(message: types.Message, state: FSMContext):
    if _norm(message.text) in {_norm(CANCEL_TEXT), _norm(BACK_TEXT)}:
        return  # handled
    try:
        fee = int(message.text.replace(' ', '').replace(',', ''))
    except Exception:
        await message.answer("Noto'g'ri qiymat. Qayta kiriting:", reply_markup=kb_back_cancel())
        return
    data = await state.get_data()
    group = await sync_to_async(Group.objects.create)(
        title=data.get('title'), description=data.get('description') or '', monthly_fee=fee, chat_id=data.get('chat_id')
    )
    await state.finish()
    await message.answer("✅ Guruh yaratildi.", reply_markup=types.ReplyKeyboardRemove())

    # Show next-step buttons
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ Yangi guruh", callback_data="adm:groups:create"),
        types.InlineKeyboardButton("👥 Guruh", callback_data=f"adm:group:{group.id}"),
    )
    kb.add(types.InlineKeyboardButton("🏠 Asosiy menyu", callback_data="adm:back:home"))
    await message.answer("Keyingi amalni tanlang:", reply_markup=kb)


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('adm:group:'), state='*')
async def group_actions(call: types.CallbackQuery, state: FSMContext):
    parts = call.data.split(':')
    group_id = int(parts[2])

    # adm:group:{id}
    if len(parts) == 3:
        g = await sync_to_async(Group.objects.get)(id=group_id)
        students_count = await sync_to_async(g.students.count)()
        # Finance block for group
        from django.db.models import Sum
        from django.utils import timezone
        now = timezone.now()
        cur_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        enr_qs = g.enrollments.filter(is_active=True)
        expected_current = await sync_to_async(lambda: enr_qs.aggregate(total=Sum('monthly_fee')).get('total') or 0)()
        collected_current = await sync_to_async(lambda: Payment.objects.filter(enrollment__in=enr_qs, month=cur_month.date()).aggregate(total=Sum('amount')).get('total') or 0)()
        # Debtors
        def enrollment_debt_this_month(enr):
            paid = Payment.objects.filter(enrollment=enr, month=cur_month.date()).aggregate(total=Sum('amount')).get('total') or 0
            return max((enr.monthly_fee or 0) - paid, 0)
        def enrollment_debt_total(enr):
            joined_m = cur_month.replace(year=enr.joined_at.year, month=enr.joined_at.month)
            # months including current
            months = max((cur_month.year - joined_m.year) * 12 + (cur_month.month - joined_m.month) + 1, 1)
            expected = months * (enr.monthly_fee or 0)
            paid = Payment.objects.filter(enrollment=enr, month__gte=joined_m.date(), month__lte=cur_month.date()).aggregate(total=Sum('amount')).get('total') or 0
            return max(expected - paid, 0)
        debtors = []
        for enr in await sync_to_async(list)(enr_qs.select_related('student')):
            dm = enrollment_debt_this_month(enr)
            dt = enrollment_debt_total(enr)
            if dm > 0 or dt > 0:
                debtors.append((enr.student.full_name, dm, dt))

        text = (
            f"<b>{g.title}</b>\n"
            f"Oyiga to'lov: {g.monthly_fee} so'm\n"
            f"Holat: {'Aktiv' if g.is_active else 'Nofaol'}\n"
            f"O'quvchilar: {students_count}\n\n"
            f"💰 Joriy oy: kerak {expected_current} | yig'ildi {collected_current}\n"
        )
        if debtors:
            text += "\nQarzdorlar (joriy / jami):\n" + "\n".join([f"• {name}: {dm} / {dt}" for name, dm, dt in debtors[:10]])
            if len(debtors) > 10:
                text += f"\n... va yana {len(debtors)-10} ta"
        await call.message.edit_text(text)
        await call.message.edit_reply_markup(group_item_kb(g.id))
        await call.answer()
        return

    # adm:group:{id}:students:p:{page}
    if len(parts) >= 5 and parts[3] == 'students' and parts[4] == 'p':
        page = int(parts[5]) if len(parts) >= 6 else 1
        qs = Student.objects.filter(enrollments__group_id=group_id).distinct()
        total = await sync_to_async(qs.count)()
        page_size = 10
        total_pages = max((total + page_size - 1) // page_size, 1)
        page = max(min(page, total_pages), 1)
        offset = (page - 1) * page_size
        students = await sync_to_async(lambda: list(qs.order_by('full_name')[offset:offset+page_size]))()

        lines = ["Guruhdagi o'quvchilar:"]
        for s in students:
            # oxirgi to'lov (ixtiyoriy)
            last_payment = await sync_to_async(lambda: Payment.objects.filter(enrollment__student=s, enrollment__group_id=group_id).order_by('-paid_at').first())()
            last_info = f" — oxirgi to'lov: {last_payment.amount} {last_payment.paid_at.date()}" if last_payment else ""
            lines.append(f"• {s.full_name}{last_info}")

        await call.message.edit_text("\n".join(lines))
        await call.message.edit_reply_markup(group_students_kb(group_id, page, total_pages))
        await call.answer()
        return

    # adm:group:{id}:debtors:p:{page}
    if len(parts) >= 5 and parts[3] == 'debtors' and parts[4] == 'p':
        page = int(parts[5]) if len(parts) >= 6 else 1
        from django.utils import timezone
        from django.db.models import Sum
        now = timezone.now()
        cur_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        enr_qs = Enrollment.objects.filter(group_id=group_id, is_active=True).select_related('student')
        students = await sync_to_async(lambda: list(enr_qs))()
        # compute debts
        items = []
        for e in students:
            paid_m = await sync_to_async(lambda: Payment.objects.filter(enrollment=e, month=cur_month.date()).aggregate(total=Sum('amount')).get('total') or 0)()
            due_m = max((e.monthly_fee or 0) - paid_m, 0)
            joined_m = cur_month.replace(year=e.joined_at.year, month=e.joined_at.month)
            months = max((cur_month.year - joined_m.year) * 12 + (cur_month.month - joined_m.month) + 1, 1)
            expected = months * (e.monthly_fee or 0)
            paid_total = await sync_to_async(lambda: Payment.objects.filter(enrollment=e, month__gte=joined_m.date(), month__lte=cur_month.date()).aggregate(total=Sum('amount')).get('total') or 0)()
            debt_total = max(expected - paid_total, 0)
            if due_m > 0 or debt_total > 0:
                items.append((e.student.full_name, due_m, debt_total))
        # sort by total debt desc
        items.sort(key=lambda x: (x[2], x[1]), reverse=True)
        total = len(items)
        page_size = 10
        total_pages = max((total + page_size - 1) // page_size, 1)
        page = max(min(page, total_pages), 1)
        offset = (page - 1) * page_size
        page_items = items[offset:offset+page_size]

        lines = ["Qarzdorlar (joriy / jami):"]
        for name, dm, dt in page_items:
            lines.append(f"• {name}: {dm} / {dt}")
        if not page_items:
            lines.append("Qarzdorlar yo'q")

        # pager kb
        kb = types.InlineKeyboardMarkup(row_width=2)
        nav = pager_buttons(f"adm:group:{group_id}:debtors", page, total_pages)
        if nav:
            kb.row(*nav)
        kb.add(
            types.InlineKeyboardButton("⬅️ Guruhga qaytish", callback_data=f"adm:group:{group_id}"),
            types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="adm:back:home"),
        )

        await call.message.edit_text("\n".join(lines))
        await call.message.edit_reply_markup(kb)
        await call.answer()
        return

from aiogram import types
from aiogram.dispatcher import FSMContext
from bot.loader import dp, db
from bot.filters import IsAdmin
from bot.keyboards.inline.admin import simple_pager, admin_main_menu_kb
from asgiref.sync import sync_to_async
from main.models import Student, Enrollment, Payment, Group
from django.db import models
from bot.states.students import StudentEdit
from bot.states.admin import AddStudentToGroupState, CreateStudentState

PAGE_SIZE = 10

# Reply keyboard labels for create student
ST_CANCEL = "❌ Bekor qilish"
ST_BACK = "⬅️ Orqaga"
ST_SKIP = "⏭ Skip"


def _norm(t: str | None) -> str:
    return (t or '').strip().lower()


def st_kb_cancel():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(ST_CANCEL)
    return kb


def st_kb_skip_back_cancel():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(ST_SKIP)
    kb.row(ST_BACK, ST_CANCEL)
    return kb


def st_kb_back_cancel():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(ST_BACK, ST_CANCEL)
    return kb


def fmt_amount(n: int) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return str(n)


async def safe_edit(call: types.CallbackQuery, text: str, kb: types.InlineKeyboardMarkup | None = None):
    if call.message:
        try:
            await call.message.edit_text(text, reply_markup=kb, parse_mode=None)
        except Exception:
            try:
                await call.message.delete()
            except Exception:
                pass
            await call.message.answer(text, reply_markup=kb, parse_mode=None)
    else:
        # inline_message (no message object), edit via inline_message_id
        try:
            await dp.bot.edit_message_text(text=text, inline_message_id=call.inline_message_id, reply_markup=kb, parse_mode=None)
        except Exception:
            await dp.bot.send_message(call.from_user.id, text, reply_markup=kb, parse_mode=None)


@dp.callback_query_handler(IsAdmin(), text='adm:students', state='*')
async def students_root(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await show_students_page(call.message, 1)
    await call.answer()


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('adm:students:p:'), state='*')
async def students_paged(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    page = int(call.data.split(':')[-1])
    await show_students_page(call.message, page)
    await call.answer()


async def show_students_page(msg: types.Message, page: int):
    items, total_pages, page, total = await db.get_students(page=page, page_size=PAGE_SIZE)

    if not items:
        await msg.edit_text("Hozircha o'quvchilar mavjud emas.")
        await msg.edit_reply_markup(simple_pager('adm:students', page, total_pages))
        return

    text = f"O'quvchilar ro'yxati (jami: {total})\nTanlang:"

    kb = types.InlineKeyboardMarkup(row_width=1)
    for s in items:
        kb.add(types.InlineKeyboardButton(f"{s.full_name} — {s.phone_number or '-'}", callback_data=f"adm:student:{s.id}"))
    nav = simple_pager('adm:students', page, total_pages)
    if nav and nav.inline_keyboard:
        for row in nav.inline_keyboard:
            kb.row(*row)
    # add create button
    kb.add(types.InlineKeyboardButton("➕ Yangi o'quvchi", callback_data="adm:students:create"))
    kb.add(types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="adm:back:home"))

    try:
        await msg.edit_text(text)
        await msg.edit_reply_markup(kb)
    except Exception:
        await msg.answer(text, reply_markup=kb)


@dp.callback_query_handler(IsAdmin(), regexp=r'^adm:student:\d+$', state='*')
async def student_detail(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    sid = int(call.data.split(':')[-1])
    student = await sync_to_async(Student.objects.get)(id=sid)

    enrollments = await sync_to_async(lambda: list(Enrollment.objects.select_related('group').filter(student_id=sid)))()
    payments_count = await sync_to_async(Payment.objects.filter(enrollment__student_id=sid).count)()
    total_paid = await sync_to_async(lambda: Payment.objects.filter(enrollment__student_id=sid).aggregate(total=models.Sum('amount')).get('total') or 0)()
    last_payments = await sync_to_async(lambda: list(Payment.objects.select_related('enrollment__group', 'created_by').filter(enrollment__student_id=sid).order_by('-paid_at')[:5]))()

    from django.utils import timezone
    now = timezone.now()
    cur_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    lines = [
        f"👤 {student.full_name}",
        f"📞 {student.phone_number or '-'}",
        "",
    ]
    if enrollments:
        lines.append("🏷️ Guruhlar (joriy oy):")
        for e in enrollments:
            paid_m = await sync_to_async(lambda: Payment.objects.filter(enrollment=e, month=cur_month.date()).aggregate(total=models.Sum('amount')).get('total') or 0)()
            need_m = e.monthly_fee or 0
            due_m = max(need_m - paid_m, 0)
            lines += [
                f"• {e.group.title}",
                f"  Kerak: {fmt_amount(need_m)} so'm | To'langan: {fmt_amount(paid_m)} so'm",
                f"  Qolgan: {fmt_amount(due_m)} so'm",
            ]
    else:
        lines.append("🏷️ Guruhlar: yo'q")

    # Total arrears since joining
    def total_arrears():
        debt = 0
        for e in enrollments:
            joined_m = cur_month.replace(year=e.joined_at.year, month=e.joined_at.month)
            months = max((cur_month.year - joined_m.year) * 12 + (cur_month.month - joined_m.month) + 1, 1)
            expected = months * (e.monthly_fee or 0)
            paid = Payment.objects.filter(enrollment=e, month__gte=joined_m.date(), month__lte=cur_month.date()).aggregate(total=models.Sum('amount')).get('total') or 0
            d = expected - paid
            if d > 0:
                debt += d
        return debt

    arrears_total = await sync_to_async(total_arrears)()

    lines += [
        "",
        "📊 Umumiy ma'lumot:",
        f"  • To'lovlar soni: {payments_count}",
        f"  • Jami to'langan: {fmt_amount(total_paid)} so'm",
        f"  • Umumiy qarz: {fmt_amount(arrears_total)} so'm",
    ]

    if last_payments:
        lines += ["", "🧾 Oxirgi to'lovlar:"]
        for p in last_payments:
            creator = None
            if getattr(p, 'created_by', None):
                creator = p.created_by.username or getattr(p.created_by, 'full_name', None) or str(p.created_by)
            lines += [
                f"• Oy: {p.month.strftime('%Y-%m')}",
                f"  Guruh: {p.enrollment.group.title}",
                f"  Summa: {fmt_amount(p.amount)} so'm",
                f"  Sana: {p.paid_at.strftime('%Y-%m-%d %H:%M')}",
            ]
            if creator:
                lines.append(f"  Qabul qilgan: {creator}")
            lines.append("")

    text = "\n".join([l for l in lines if l is not None]).rstrip()

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✏️ Ma'lumotlarini o'zgartirish", callback_data=f"adm:student:{sid}:edit"),
        types.InlineKeyboardButton("👥 Guruhlarini ko'rish", callback_data=f"adm:student:{sid}:groups"),
    )
    kb.add(
        types.InlineKeyboardButton("➕ Yangi to'lov", callback_data=f"pay:st:{sid}"),
        types.InlineKeyboardButton("➕ Guruhga qo'shish", callback_data=f"adm:student:{sid}:add_to_group"),
    )
    kb.add(types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="adm:back:home"))

    await safe_edit(call, text, kb)


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('adm:student:') and c.data.endswith(':groups'), state='*')
async def student_groups_view(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    parts = call.data.split(':')
    sid = int(parts[2])
    student = await sync_to_async(Student.objects.get)(id=sid)
    enrollments = await sync_to_async(lambda: list(Enrollment.objects.select_related('group').filter(student_id=sid)))()

    lines = [f"👤 {student.full_name} — guruhlari:"]
    if enrollments:
        for e in enrollments:
            lines.append(f"• {e.group.title} — oy: {fmt_amount(e.monthly_fee)} so'm")
    else:
        lines.append("Guruhlar yo'q")

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("⬅️ O'quvchi", callback_data=f"adm:student:{sid}"),
        types.InlineKeyboardButton("⬅️ O'quvchilar", callback_data="adm:students:p:1"),
    )
    kb.add(types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="adm:back:home"))

    await safe_edit(call, "\n".join(lines), kb)


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('adm:student:') and c.data.endswith(':edit'), state='*')
async def student_edit_menu(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    sid = int(call.data.split(':')[2])
    await state.update_data(student_id=sid)
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✏️ Ismni o'zgartirish", callback_data="adm:student:edit:name"),
        types.InlineKeyboardButton("📞 Telefonni o'zgartirish", callback_data="adm:student:edit:phone"),
    )
    kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data=f"adm:student:{sid}"))
    await safe_edit(call, "Qaysi ma'lumotni o'zgartiramiz?", kb)


@dp.callback_query_handler(IsAdmin(), text='adm:student:edit:name', state='*')
async def student_edit_name_start(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if 'student_id' not in data:
        await call.answer("Avval o'quvchini tanlang.", show_alert=True)
        return
    await (call.message.answer if call.message else dp.bot.send_message)(call.from_user.id, "Yangi F.I.Sh ni kiriting:")
    await StudentEdit.full_name.set()
    await call.answer()


@dp.callback_query_handler(IsAdmin(), text='adm:student:edit:phone', state='*')
async def student_edit_phone_start(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if 'student_id' not in data:
        await call.answer("Avval o'quvchini tanlang.", show_alert=True)
        return
    await (call.message.answer if call.message else dp.bot.send_message)(call.from_user.id, "Yangi telefon raqamini kiriting (masalan, +99890...):")
    await StudentEdit.phone.set()
    await call.answer()


@dp.message_handler(IsAdmin(), state=StudentEdit.full_name)
async def student_edit_name_save(message: types.Message, state: FSMContext):
    new_name = message.text.strip()
    data = await state.get_data()
    sid = data.get('student_id')
    await sync_to_async(Student.objects.filter(id=sid).update)(full_name=new_name)
    await state.finish()
    await message.answer("✅ Ism yangilandi.")


@dp.message_handler(IsAdmin(), state=StudentEdit.phone)
async def student_edit_phone_save(message: types.Message, state: FSMContext):
    new_phone = message.text.strip()
    data = await state.get_data()
    sid = data.get('student_id')
    await sync_to_async(Student.objects.filter(id=sid).update)(phone_number=new_phone)
    await state.finish()
    await message.answer("✅ Telefon yangilandi.")


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('adm:student:') and c.data.endswith(':add_to_group'), state='*')
async def student_add_to_group(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    sid = int(call.data.split(':')[2])
    await state.update_data(student_id=sid)

    groups = await sync_to_async(lambda: list(Group.objects.all().order_by('title')))()
    if not groups:
        await call.answer("Guruhlar mavjud emas.", show_alert=True)
        return

    kb = types.InlineKeyboardMarkup(row_width=2)
    for g in groups:
        kb.insert(types.InlineKeyboardButton(g.title, callback_data=f"adm:add_to_group:{g.id}"))
    kb.add(types.InlineKeyboardButton("⬅️ Orqaga", callback_data=f"adm:student:{sid}"))

    await safe_edit(call, "Guruhni tanlang:", kb)
    await AddStudentToGroupState.group_id.set()
    await call.answer()


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('adm:add_to_group:'), state=AddStudentToGroupState.group_id)
async def student_add_to_group_save(call: types.CallbackQuery, state: FSMContext):
    gid = int(call.data.split(':')[-1])
    data = await state.get_data()
    sid = data.get('student_id')

    # Create enrollment if not exists
    def _create():
        obj, created = Enrollment.objects.get_or_create(student_id=sid, group_id=gid)
        if created:
            obj.save()
        return created
    created = await sync_to_async(_create)()

    await state.finish()
    # Show confirmation with next-step buttons
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ Yangi o'quvchi", callback_data="adm:students:create"),
        types.InlineKeyboardButton("👤 O'quvchi", callback_data=f"adm:student:{sid}"),
    )
    kb.add(types.InlineKeyboardButton("🏠 Asosiy menyu", callback_data="adm:back:home"))
    await safe_edit(call, ("✅ O'quvchi guruhga qo'shildi." if created else "ℹ️ O'quvchi allaqachon shu guruhda."), kb)
    await call.answer()


@dp.callback_query_handler(IsAdmin(), text='adm:students:create', state='*')
async def create_student_start(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.answer("Yangi o'quvchi F.I.Sh ni kiriting:", reply_markup=st_kb_cancel())
    await CreateStudentState.full_name.set()
    await call.answer()


# Cancel within CreateStudentState -> go to Home
@dp.message_handler(
    IsAdmin(),
    lambda m: _norm(m.text) in {_norm(ST_CANCEL), 'bekor qilish', 'cancel'},
    state=[CreateStudentState.full_name, CreateStudentState.phone]
)
async def create_student_cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("Asosiy menyu:", reply_markup=types.ReplyKeyboardRemove())
    await message.answer("Tanlang:", reply_markup=admin_main_menu_kb())


# Back handler
@dp.message_handler(
    IsAdmin(),
    lambda m: _norm(m.text) in {_norm(ST_BACK), 'orqaga', 'back'},
    state=[CreateStudentState.phone]
)
async def create_student_back(message: types.Message, state: FSMContext):
    await CreateStudentState.full_name.set()
    await message.answer("Yangi o'quvchi F.I.Sh ni kiriting:", reply_markup=st_kb_cancel())


@dp.message_handler(IsAdmin(), state=CreateStudentState.full_name)
async def create_student_name(message: types.Message, state: FSMContext):
    if _norm(message.text) in {_norm(ST_CANCEL), _norm(ST_BACK)}:
        return
    await state.update_data(full_name=message.text.strip())
    await message.answer("Telefon raqami (ixtiyoriy, +998..). O'tkazib yuborish uchun ⏭ Skip ni bosing:", reply_markup=st_kb_skip_back_cancel())
    await CreateStudentState.phone.set()


@dp.message_handler(
    IsAdmin(),
    lambda m: _norm(m.text) in {_norm(ST_SKIP), 'skip'},
    state=CreateStudentState.phone
)
async def create_student_phone_skip(message: types.Message, state: FSMContext):
    data = await state.get_data()
    full_name = data.get('full_name')
    student = await sync_to_async(Student.objects.create)(full_name=full_name)
    await state.finish()
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ Guruhga qo'shish", callback_data=f"adm:student:{student.id}:add_to_group"),
        types.InlineKeyboardButton("⬅️ O'quvchi", callback_data=f"adm:student:{student.id}"),
    )
    await message.answer("✅ O'quvchi yaratildi. Guruhga qo'shasizmi?", reply_markup=types.ReplyKeyboardRemove())
    await message.answer("Quyidagi variantlardan birini tanlang:", reply_markup=kb)


@dp.message_handler(IsAdmin(), state=CreateStudentState.phone)
async def create_student_save(message: types.Message, state: FSMContext):
    if _norm(message.text) in {_norm(ST_CANCEL), _norm(ST_BACK), _norm(ST_SKIP)}:
        return
    data = await state.get_data()
    full_name = data.get('full_name')
    phone = message.text.strip() if message.text else None
    student = await sync_to_async(Student.objects.create)(full_name=full_name, phone_number=phone)
    await state.finish()
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("➕ Guruhga qo'shish", callback_data=f"adm:student:{student.id}:add_to_group"),
        types.InlineKeyboardButton("⬅️ O'quvchi", callback_data=f"adm:student:{student.id}"),
    )
    await message.answer("✅ O'quvchi yaratildi. Guruhga qo'shasizmi?", reply_markup=types.ReplyKeyboardRemove())
    await message.answer("Quyidagi variantlardan birini tanlang:", reply_markup=kb)


# =================== Global Debtors (Main menu) ===================

@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('adm:debtors:p:'), state='*')
async def global_debtors_paged(call: types.CallbackQuery, state: FSMContext):
    from django.utils import timezone
    from django.db.models import Sum
    now = timezone.now()
    cur_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Build student -> (due_current_sum, debt_total_sum)
    enr_qs = Enrollment.objects.filter(is_active=True).select_related('student')

    # Accumulate per student
    def compute_items():
        agg = {}
        for e in enr_qs:
            paid_m = Payment.objects.filter(enrollment=e, month=cur_month.date()).aggregate(total=Sum('amount')).get('total') or 0
            need_m = e.monthly_fee or 0
            due_m = max(need_m - paid_m, 0)
            joined_m = cur_month.replace(year=e.joined_at.year, month=e.joined_at.month)
            months = max((cur_month.year - joined_m.year) * 12 + (cur_month.month - joined_m.month) + 1, 1)
            expected = months * (e.monthly_fee or 0)
            paid_total = Payment.objects.filter(enrollment=e, month__gte=joined_m.date(), month__lte=cur_month.date()).aggregate(total=Sum('amount')).get('total') or 0
            debt_total = max(expected - paid_total, 0)
            sid = e.student_id
            name = e.student.full_name
            if sid not in agg:
                agg[sid] = [name, 0, 0]
            agg[sid][1] += due_m
            agg[sid][2] += debt_total
        # Prepare items, filter those with any debt
        items = [(name, dm, dt) for _, (name, dm, dt) in agg.items() if dm > 0 or dt > 0]
        # Sort by total debt desc, then current due desc, then name
        items.sort(key=lambda x: (x[2], x[1], x[0]), reverse=True)
        return items

    items = await sync_to_async(compute_items)()

    page = int(call.data.split(':')[-1])
    total = len(items)
    page_size = 10
    total_pages = max((total + page_size - 1) // page_size, 1)
    page = max(min(page, total_pages), 1)
    offset = (page - 1) * page_size
    page_items = items[offset:offset+page_size]

    lines = [
        "💳 Qarzdorlar (eng ko'pdan kamga):",
        f"Sahifa: {page}/{total_pages}",
        "",
    ]
    if page_items:
        for name, dm, dt in page_items:
            lines += [
                f"• {name}",
                f"  Joriy oy: {fmt_amount(dm)} so'm",
                f"  Jami qarz: {fmt_amount(dt)} so'm",
                "",
            ]
    else:
        lines.append("Qarzdorlar yo'q")

    text = "\n".join([l for l in lines if l is not None]).rstrip()

    kb = types.InlineKeyboardMarkup(row_width=2)
    nav = simple_pager('adm:debtors', page, total_pages)
    if nav and nav.inline_keyboard:
        for row in nav.inline_keyboard:
            kb.row(*row)
    kb.add(types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="adm:back:home"))

    await safe_edit(call, text, kb)
    await call.answer()
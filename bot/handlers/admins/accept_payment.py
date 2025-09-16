from aiogram import types
from aiogram.dispatcher import FSMContext
from datetime import datetime, date
import calendar

from bot.loader import dp, db
from bot.filters import IsAdmin
from bot.states.payments import AcceptPayment
from asgiref.sync import sync_to_async
from main.models import Student, Group, Enrollment, Payment
from bot.keyboards.inline.admin import admin_main_menu_kb
from .payments import build_payments_page


def fmt_amount(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def month_label(d: date) -> str:
    uz_months = [
        "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
        "Iyul", "Avgust", "Sentabr", "Oktyabr", "Noyabr", "Dekabr",
    ]
    return f"{uz_months[d.month-1]} {d.year}"


async def safe_edit_cb(call: types.CallbackQuery, text: str, kb: types.InlineKeyboardMarkup | None = None):
    if call.message:
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            try:
                await call.message.delete()
            except Exception:
                pass
            await call.message.answer(text, reply_markup=kb)
    else:
        # inline callback
        try:
            await dp.bot.edit_message_text(text=text, inline_message_id=call.inline_message_id, reply_markup=kb)
        except Exception:
            await dp.bot.send_message(call.from_user.id, text, reply_markup=kb)


# Command shortcuts
from aiogram.dispatcher.filters import Command

@dp.message_handler(Command(['new_payment', 'payment', 'pay']), IsAdmin(), state='*')
async def cmd_new_payment(message: types.Message, state: FSMContext):
    await state.finish()
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🧑‍🎓 O'quvchilar", callback_data="adm:students"))
    kb.add(types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="adm:back:home"))
    await message.answer("To'lov qabul qilish uchun o'quvchini tanlang:", reply_markup=kb)


@dp.message_handler(Command(['new_group', 'group']), IsAdmin(), state='*')
async def cmd_new_group(message: types.Message, state: FSMContext):
    await state.finish()
    # simulate pressing create group
    class _Call:
        def __init__(self, message):
            self.data = 'adm:groups:create'
            self.message = message
            self.inline_message_id = None
            self.from_user = message.from_user
    from .groups import group_create_start
    await group_create_start(_Call(message), state)


@dp.message_handler(Command(['new_student', 'student']), IsAdmin(), state='*')
async def cmd_new_student(message: types.Message, state: FSMContext):
    await state.finish()
    class _Call:
        def __init__(self, message):
            self.data = 'adm:students:create'
            self.message = message
            self.inline_message_id = None
            self.from_user = message.from_user
    from .students import create_student_start
    await create_student_start(_Call(message), state)


@dp.callback_query_handler(IsAdmin(), text='adm:pay:start', state='*')
async def pay_start(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("🧑‍🎓 O'quvchilar", callback_data="adm:students"))
    kb.add(types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="adm:back:home"))
    await call.message.answer("To'lov qabul qilish uchun avval o'quvchini tanlang (O'quvchilar bo'limidan tanlang):", reply_markup=kb)
    await call.answer()


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('pay:enr:'), state=AcceptPayment.select_student)
async def pay_selected_enrollment(call: types.CallbackQuery, state: FSMContext):
    enr_id = int(call.data.split(':')[-1])
    enrollment = await sync_to_async(Enrollment.objects.select_related('student','group').get)(id=enr_id)
    await state.update_data(student_id=enrollment.student_id, enrollment_id=enrollment.id)

    # add cancel reply keyboard for amount entry later
    await call.message.answer(
        f"Tanlandi:\n👤 {enrollment.student.full_name}\n🏷️ Guruh: {enrollment.group.title}\nEndi summani kiriting (so'mda, masalan 250000):",
        reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add("❌ Bekor qilish")
    )
    await AcceptPayment.enter_amount.set()
    await call.answer()


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('pay:st:'), state='*')
async def pay_start_for_student(call: types.CallbackQuery, state: FSMContext):
    # Start or continue payment for a given student id from anywhere (including inline mode)
    sid = int(call.data.split(':')[-1])
    await state.finish()
    await AcceptPayment.select_student.set()
    student = await sync_to_async(Student.objects.get)(id=sid)
    await state.update_data(student_id=student.id)

    groups = await sync_to_async(lambda: list(student.groups.all()))()
    if not groups:
        await safe_edit_cb(call, "Bu o'quvchi hech qanday guruhga yozilmagan.")
        await state.finish()
        await call.answer()
        return

    kb = types.InlineKeyboardMarkup(row_width=2)
    for g in groups:
        kb.insert(types.InlineKeyboardButton(g.title, callback_data=f"pay:gr:{g.id}"))
    await safe_edit_cb(call, "Guruhni tanlang:", kb)
    await AcceptPayment.select_group.set()
    await call.answer()


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('pay:enr:'), state='*')
async def pay_selected_enrollment_any(call: types.CallbackQuery, state: FSMContext):
    # Allow selecting enrollment from anywhere
    await state.finish()
    await AcceptPayment.select_student.set()
    await pay_selected_enrollment(call, state)


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('pay:gr:'), state=AcceptPayment.select_group)
async def pay_group_selected(call: types.CallbackQuery, state: FSMContext):
    gid = int(call.data.split(':')[-1])
    data = await state.get_data()
    sid = int(data['student_id'])

    enrollment = await sync_to_async(Enrollment.objects.get)(student_id=sid, group_id=gid)
    await state.update_data(enrollment_id=enrollment.id)

    base = date.today().replace(day=1)
    await safe_edit_cb(call, "Qaysi oy uchun to'lov?", build_months_kb(base))
    await AcceptPayment.select_month.set()
    await call.answer()


def build_months_kb(base: date) -> types.InlineKeyboardMarkup:
    today = base
    prev_month = (today.replace(month=today.month - 1, year=today.year) if today.month > 1 else today.replace(month=12, year=today.year - 1))
    next_month = (today.replace(month=today.month + 1, year=today.year) if today.month < 12 else today.replace(month=1, year=today.year + 1))

    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton(f"📅 {month_label(today)} (joriy)", callback_data=f"pay:month:{today.strftime('%Y-%m')}"))
    kb.row(
        types.InlineKeyboardButton(f"⬅️ {month_label(prev_month)}", callback_data=f"pay:month:{prev_month.strftime('%Y-%m')}"),
        types.InlineKeyboardButton(f"{month_label(next_month)} ➡️", callback_data=f"pay:month:{next_month.strftime('%Y-%m')}"),
    )
    kb.add(types.InlineKeyboardButton("Boshqa oy (YYYY-MM)", callback_data="pay:month:custom"))
    kb.add(types.InlineKeyboardButton("❌ Bekor qilish", callback_data="pay:cancel_flow"))
    return kb


@dp.callback_query_handler(IsAdmin(), lambda c: c.data.startswith('pay:month:'), state=AcceptPayment.select_month)
async def pay_month_selected(call: types.CallbackQuery, state: FSMContext):
    val = call.data.split(':')[-1]
    if val == 'custom':
        await safe_edit_cb(call, "Oy kiritish: YYYY-MM")
        await AcceptPayment.enter_custom_month.set()
        await call.answer()
        return
    month = datetime.strptime(val, "%Y-%m").date().replace(day=1)
    await state.update_data(month=month)
    await safe_edit_cb(call, f"Tanlangan oy: {month_label(month)}\nEndi summani kiriting (so'mda):")
    # add cancel reply keyboard for amount entry (force plain text to avoid parse mode issues)
    kb_cancel = types.ReplyKeyboardMarkup(resize_keyboard=True).add("❌ Bekor qilish")
    if call.message:
        await dp.bot.send_message(call.message.chat.id, "Summani kiriting (so'mda):", reply_markup=kb_cancel, parse_mode=None)
    else:
        await dp.bot.send_message(call.from_user.id, "Summani kiriting (so'mda):", reply_markup=kb_cancel, parse_mode=None)
    await AcceptPayment.enter_amount.set()
    await call.answer()


# Cancel during amount entry
@dp.message_handler(IsAdmin(), lambda m: m.text and m.text.strip().lower() in {"❌ bekor qilish".lower(), "cancel", "bekor qilish"}, state=AcceptPayment.enter_amount)
async def pay_amount_cancel(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer("To'lov bekor qilindi.", reply_markup=types.ReplyKeyboardRemove())
    # Back to main menu
    await message.answer("Asosiy menyu:", reply_markup=admin_main_menu_kb())


async def show_confirm_inline(call: types.CallbackQuery | None, message: types.Message | None, state: FSMContext):
    data = await state.get_data()
    enrollment = await sync_to_async(Enrollment.objects.select_related('student', 'group').get)(id=data['enrollment_id'])
    text = (
        "Tasdiqlaysizmi?\n"
        f"O'quvchi: {enrollment.student.full_name}\n"
        f"Guruh: {enrollment.group.title}\n"
        f"Oy: {data['month'].strftime('%Y-%m')}\n"
        f"Summa: {fmt_amount(int(data['amount']))} so'm"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Tasdiqlash", callback_data="pay:confirm"),
        types.InlineKeyboardButton("❌ Bekor qilish", callback_data="pay:cancel"),
    )
    if call is not None:
        await safe_edit_cb(call, text, kb)
    elif message is not None:
        await message.answer(text, reply_markup=kb)


@dp.message_handler(IsAdmin(), state=AcceptPayment.enter_custom_month)
async def pay_enter_custom_month(message: types.Message, state: FSMContext):
    try:
        month = datetime.strptime(message.text.strip(), "%Y-%m").date().replace(day=1)
    except Exception:
        await message.answer("❌ Format noto'g'ri. Qayta kiriting (YYYY-MM):")
        return
    await state.update_data(month=month)
    await message.answer(f"Tanlangan oy: {month_label(month)}\nEndi summani kiriting (so'mda):")
    await AcceptPayment.enter_amount.set()


@dp.message_handler(IsAdmin(), state=AcceptPayment.enter_amount)
async def pay_enter_amount(message: types.Message, state: FSMContext):
    text_val = message.text.replace(' ', '').replace(',', '')
    try:
        amount = int(text_val)
        if amount <= 0:
            raise ValueError
    except Exception:
        await message.answer("❌ Noto'g'ri summa. Qayta kiriting:")
        return

    await state.update_data(amount=amount)
    await show_confirm_inline(None, message, state)
    await AcceptPayment.confirm.set()


@dp.callback_query_handler(IsAdmin(), text='pay:cancel', state=AcceptPayment.confirm)
async def pay_cancel_cb(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await safe_edit_cb(call, "Bekor qilindi.")
    await call.answer()


@dp.callback_query_handler(IsAdmin(), text='pay:confirm', state=AcceptPayment.confirm)
async def pay_confirm_cb(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    enrollment_id = data['enrollment_id']
    amount = int(data['amount'])
    month = data['month']

    # Load enrollment with relations for notification
    enrollment = await sync_to_async(Enrollment.objects.select_related('student', 'group').get)(id=enrollment_id)

    # Map telegram user to BotUser
    creator = None
    try:
        creator = await db.get_user(call.from_user.id)
    except Exception:
        creator = None

    await sync_to_async(Payment.objects.create)(
        enrollment_id=enrollment_id,
        amount=amount,
        month=month,
        created_by=creator if creator else None,
    )



    await state.finish()
    # Show payments page after successful accept
    text, kb = await build_payments_page(page=1)
    await safe_edit_cb(call, text, kb)
    await call.answer()
    # Notify group chat if chat_id is available
    chat_id = (enrollment.group.chat_id or enrollment.chat_id or '').strip()
    print("Chat ID:", chat_id)
    if chat_id:
        notify_text = (
            "✅ To'lov qabul qilindi\n"
            f"O'quvchi: {str(enrollment.student.full_name).capitalize()}\n"
            f"Guruh: {enrollment.group.title if enrollment.group else 'Belgilanmagan'}\n"
            f"Oy: {month_label(month)}\n"
        )
        try:
            await dp.bot.send_message(chat_id, notify_text, disable_notification=True)
        except Exception as err:
            # Ignore if bot cannot send to the group
            print(f"Error sending payment notification: {err}")
            pass


@dp.callback_query_handler(IsAdmin(), text='pay:cancel_flow', state='*')
async def pay_cancel_flow(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await safe_edit_cb(call, "Bekor qilindi.", admin_main_menu_kb())
    await call.answer()

from aiogram import types
from aiogram.dispatcher import FSMContext
from bot.loader import dp
from bot.filters import IsAdmin
from bot.states.finance import FinanceAuth
from bot.data.config import FINANCE_PASSWORD
from asgiref.sync import sync_to_async
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta
from main.models import Payment, Group, Enrollment


def fmt_amount(n: int) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return str(n)


def month_start(dt):
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def months_between(a, b):
    # number of months from a to b, where a and b are first day of month; b >= a
    return (b.year - a.year) * 12 + (b.month - a.month)


@dp.callback_query_handler(IsAdmin(), text='adm:finance', state='*')
async def finance_entry(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    if not FINANCE_PASSWORD:
        await call.message.answer("Moliya bo'limi paroli sozlanmagan. Administrator bilan bog'laning.")
        await call.answer()
        return
    await call.message.answer("Moliya bo'limi uchun parolni kiriting. (To'g'ri kiritilganda xabar maxfiylik uchun o'chiriladi)")
    await FinanceAuth.waiting_password.set()
    await call.answer()


@dp.message_handler(IsAdmin(), state=FinanceAuth.waiting_password)
async def finance_check_password(message: types.Message, state: FSMContext):
    if message.text.strip() != FINANCE_PASSWORD:
        await message.answer("❌ Noto'g'ri parol. Qaytadan kiriting yoki /cancel bilan bekor qiling.")
        return
    # Correct password: delete the entered message for privacy
    try:
        await message.delete()
    except Exception:
        pass
    await state.finish()
    await show_finance_dashboard(message)


async def show_finance_dashboard(msg: types.Message):
    now = timezone.now()
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_week = (start_today - timedelta(days=start_today.weekday()))
    start_month = start_today.replace(day=1)

    def agg_range(start_dt):
        return Payment.objects.filter(paid_at__gte=start_dt).aggregate(total=Sum('amount')).get('total') or 0

    today_total = await sync_to_async(agg_range)(start_today)
    week_total = await sync_to_async(agg_range)(start_week)
    month_total = await sync_to_async(agg_range)(start_month)

    # Per-creator for today/week/month
    def per_creator(start_dt):
        qs = (
            Payment.objects.filter(paid_at__gte=start_dt)
            .values('created_by__username', 'created_by__first_name', 'created_by__last_name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )
        return list(qs)

    creators_today, creators_week, creators_month = await sync_to_async(per_creator)(start_today), await sync_to_async(per_creator)(start_week), await sync_to_async(per_creator)(start_month)

    # Per-group current month expected vs collected and past arrears
    cur_month = month_start(now)

    def group_summaries():
        groups = list(Group.objects.filter(is_active=True).order_by('title'))
        data = []
        for g in groups:
            enr_qs = Enrollment.objects.filter(group=g, is_active=True)
            expected_current = enr_qs.aggregate(total=Sum('monthly_fee')).get('total') or 0
            collected_current = Payment.objects.filter(enrollment__in=enr_qs, month=cur_month.date()).aggregate(total=Sum('amount')).get('total') or 0
            # past arrears up to previous month
            def _enr_past_debt(enr: Enrollment):
                joined_m = month_start(enr.joined_at)
                months_prior = max(months_between(joined_m, cur_month), 0)
                if months_prior <= 0:
                    return 0
                expected_past = months_prior * (enr.monthly_fee or 0)
                paid_past = Payment.objects.filter(enrollment=enr, month__gte=joined_m.date(), month__lt=cur_month.date()).aggregate(total=Sum('amount')).get('total') or 0
                d = expected_past - paid_past
                return d if d > 0 else 0
            arrears_past = 0
            for enr in enr_qs:
                arrears_past += _enr_past_debt(enr)
            data.append((g.title, expected_current, collected_current, arrears_past))
        return data

    groups_data = await sync_to_async(group_summaries)()

    lines = [
        "📊 Moliya hisobotlari",
        f"Bugun: {fmt_amount(today_total)} so'm",
        f"Hafta boshidan: {fmt_amount(week_total)} so'm",
        f"Oy boshidan: {fmt_amount(month_total)} so'm",
        "",
        "👤 Yaratganlar bo'yicha (bugun):",
    ]
    if creators_today:
        for c in creators_today:
            name = c['created_by__username'] or f"{(c['created_by__first_name'] or '')} {(c['created_by__last_name'] or '')}".strip() or "Noma'lum"
            lines.append(f"• {name}: {fmt_amount(c['total'])} so'm")
    else:
        lines.append("Ma'lumot yo'q")

    lines += ["", "👤 Yaratganlar bo'yicha (hafta):"]
    if creators_week:
        for c in creators_week:
            name = c['created_by__username'] or f"{(c['created_by__first_name'] or '')} {(c['created_by__last_name'] or '')}".strip() or "Noma'lum"
            lines.append(f"• {name}: {fmt_amount(c['total'])} so'm")
    else:
        lines.append("Ma'lumot yo'q")

    lines += ["", "👤 Yaratganlar bo'yicha (oy):"]
    if creators_month:
        for c in creators_month:
            name = c['created_by__username'] or f"{(c['created_by__first_name'] or '')} {(c['created_by__last_name'] or '')}".strip() or "Noma'lum"
            lines.append(f"• {name}: {fmt_amount(c['total'])} so'm")
    else:
        lines.append("Ma'lumot yo'q")

    lines += ["", "🏷️ Guruhlar bo'yicha (joriy oy):"]
    if groups_data:
        for title, expected_current, collected_current, arrears_past in groups_data:
            lines.append(f"• {title}: kerak {fmt_amount(expected_current)} | yig'ildi {fmt_amount(collected_current)} | o'tgan qarz {fmt_amount(arrears_past)}")
    else:
        lines.append("Guruhlar yo'q")

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🔄 Yangilash", callback_data="fin:refresh"),
        types.InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="adm:back:home"),
    )

    await msg.answer("\n".join(lines), reply_markup=kb)


@dp.callback_query_handler(IsAdmin(), text='fin:refresh', state='*')
async def finance_refresh(call: types.CallbackQuery, state: FSMContext):
    await show_finance_dashboard(call.message)
    await call.answer("Yangilandi")

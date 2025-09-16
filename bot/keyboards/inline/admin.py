from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# Main admin menu
def admin_main_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("👥 Guruhlar", callback_data="adm:groups:p:1"),
        InlineKeyboardButton("🧑‍🎓 O'quvchilar", callback_data="adm:students"),
    )
    kb.add(
        InlineKeyboardButton("💵 To'lov qabul qilish", switch_inline_query_current_chat=""),
        InlineKeyboardButton("📊 Moliya", callback_data="adm:finance"),
    )
    kb.add(InlineKeyboardButton("💳 To'lovlar", callback_data="adm:payments:p:1"))
    return kb


# Finance menu

def finance_menu_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📈 Joriy oy to'lovlari", callback_data="fin:report:month"),
        InlineKeyboardButton("📄 Barcha to'lovlar", callback_data="fin:payments:p:1"),
    )
    kb.add(
        InlineKeyboardButton("⬅️ Orqaga", callback_data="adm:back:home"),
    )
    return kb


def pager_buttons(prefix: str, page: int, total_pages: int, extra: str = ""):
    # prefix example: adm:groups or adm:students
    btns = []
    if page > 1:
        btns.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"{prefix}:p:{page-1}{extra}"))
    if page < total_pages:
        btns.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"{prefix}:p:{page+1}{extra}"))
    return btns


# Groups

def groups_list_kb(groups, page: int, total_pages: int):
    kb = InlineKeyboardMarkup(row_width=1)
    for g in groups:
        kb.add(InlineKeyboardButton(f"{g.title}", callback_data=f"adm:group:{g.id}"))
    kb.add(InlineKeyboardButton("➕ Yangi guruh", callback_data="adm:groups:create"))
    # Pagination row
    nav = pager_buttons("adm:groups", page, total_pages)
    if nav:
        kb.row(*nav)
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="adm:back:home"))
    return kb


def group_item_kb(group_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🧑‍🎓 O'quvchilar", callback_data=f"adm:group:{group_id}:students:p:1"),
        InlineKeyboardButton("💳 Qarzdorlar", callback_data=f"adm:group:{group_id}:debtors:p:1"),
    )
    kb.add(
        InlineKeyboardButton("⬅️ Guruhlarga qaytish", callback_data="adm:groups:p:1"),
        InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="adm:back:home"),
    )
    return kb


def group_students_kb(group_id: int, page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    nav = pager_buttons(f"adm:group:{group_id}:students", page, total_pages)
    if nav:
        kb.row(*nav)
    kb.add(
        InlineKeyboardButton("⬅️ Guruhga qaytish", callback_data=f"adm:group:{group_id}"),
        InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="adm:back:home"),
    )
    return kb


# Students

def students_list_kb(students, page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for s in students:
        kb.add(InlineKeyboardButton(f"{s.full_name}", callback_data=f"adm:student:{s.id}"))
    kb.add(InlineKeyboardButton("➕ Yangi o'quvchi", callback_data="adm:students:create"))
    nav = pager_buttons("adm:students", page, total_pages)
    if nav:
        kb.row(*nav)
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="adm:back:home"))
    return kb


def student_item_kb(student_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("⬅️ O'quvchilar ro'yxati", callback_data="adm:students:p:1"))
    kb.add(InlineKeyboardButton("⬅️ Asosiy menyu", callback_data="adm:back:home"))
    return kb


# Payments

def payments_list_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    nav = pager_buttons("adm:payments", page, total_pages)
    if nav:
        kb.row(*nav)
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="adm:back:home"))
    return kb


# Search keyboards

def search_students_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🔎 O'quvchini tanlash", switch_inline_query_current_chat=""),
    )
    kb.add(InlineKeyboardButton("⬅️ Orqaga", callback_data="adm:back:home"))
    return kb


# Generic simple pager (optional helper)

def simple_pager(prefix: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    nav = pager_buttons(prefix, page, total_pages)
    if nav:
        kb.row(*nav)
    return kb
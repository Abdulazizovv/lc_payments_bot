from aiogram.dispatcher.filters.state import StatesGroup, State


class AcceptPayment(StatesGroup):
    select_student = State()
    select_group = State()
    enter_amount = State()
    select_month = State()  # choose from suggested months via inline
    enter_custom_month = State()  # optional manual entry YYYY-MM
    confirm = State()

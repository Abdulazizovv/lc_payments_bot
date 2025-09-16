from aiogram.dispatcher.filters.state import StatesGroup, State


class FinanceAuth(StatesGroup):
    waiting_password = State()
    menu = State()

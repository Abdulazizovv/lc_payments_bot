from aiogram.dispatcher.filters.state import StatesGroup, State


class StudentEdit(StatesGroup):
    full_name = State()
    phone = State()

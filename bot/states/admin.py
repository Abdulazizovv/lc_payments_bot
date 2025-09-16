from aiogram.dispatcher.filters.state import StatesGroup, State


class CreateGroupState(StatesGroup):
    title = State()
    description = State()
    chat_id = State()
    monthly_fee = State()


class CreateStudentState(StatesGroup):
    full_name = State()
    phone = State()


class AddStudentToGroupState(StatesGroup):
    student_id = State()
    group_id = State()

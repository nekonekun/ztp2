from aiogram.fsm.state import StatesGroup, State


class Manage(StatesGroup):
    selecting_switch = State()
    main = State()

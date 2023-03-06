from aiogram.fsm.state import StatesGroup, State


class PreMode(StatesGroup):
    waiting_for_serial = State()
    waiting_for_mac = State()
    waiting_for_employee = State()


class Mode(StatesGroup):
    waiting_for_ip_address = State()
    waiting_for_parent = State()
    waiting_for_task = State()
    waiting_for_node = State()

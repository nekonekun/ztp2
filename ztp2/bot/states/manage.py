from aiogram.fsm.state import StatesGroup, State


class Manage(StatesGroup):
    selecting_switch = State()
    main = State()
    waiting_for_employee = State()
    waiting_for_mac = State()
    waiting_for_ip = State()
    waiting_for_parent = State()
    waiting_for_descriptions = State()
    waiting_for_vlans = State()
    waiting_for_movements = State()
    waiting_for_vlanids = State()
    waiting_for_ports = State()

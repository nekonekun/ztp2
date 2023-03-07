from aiogram.filters.callback_data import CallbackData


class ChangeData(CallbackData, prefix='add_change'):
    field: str


class ModeData(CallbackData, prefix='add_mode'):
    mode: str


class ConfirmationData(CallbackData, prefix='add_confirm'):
    confirm: bool

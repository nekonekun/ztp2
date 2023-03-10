from aiogram.filters.callback_data import CallbackData


class SelectData(CallbackData, prefix='manage_selecting_filter'):
    field: str
    action: str


class ManageData(CallbackData, prefix='manage'):
    cat: str
    action: str
    params: str | None


class ScreenData(CallbackData, prefix='manage_goto'):
    screen: str
    save: bool = False

from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from ..callbacks.add import ChangeData, ModeData


def gathering_data_keyboard(is_serial_specified: bool = False,
                            is_mac_specified: bool = False):
    builder = InlineKeyboardBuilder()
    if is_mac_specified and is_serial_specified:
        change_switch = InlineKeyboardButton(
            text='Замена',
            callback_data=ModeData(mode='change_switch').pack())
        new_switch = InlineKeyboardButton(
            text='Доп',
            callback_data=ModeData(mode='new_switch').pack())
        new_house = InlineKeyboardButton(
            text='Запуск',
            callback_data=ModeData(mode='new_house').pack())
        builder.row(change_switch, new_switch, new_house)
    builder.row(InlineKeyboardButton(
        text='Другой сотрудник',
        callback_data=ChangeData(field='employee_id').pack()))
    if is_serial_specified:
        builder.row(InlineKeyboardButton(
            text='Другой серийный номер',
            callback_data=ChangeData(field='serial_number').pack()))
    if is_mac_specified:
        builder.row(InlineKeyboardButton(
            text='Другой MAC адрес',
            callback_data=ChangeData(field='mac_address').pack()))
    return builder.as_markup()



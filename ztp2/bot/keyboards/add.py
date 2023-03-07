from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from ..callbacks.add import ChangeData, ModeData, ConfirmationData


def gathering_data_keyboard(is_employee_specified: bool = False,
                            is_serial_specified: bool = False,
                            is_mac_specified: bool = False):
    builder = InlineKeyboardBuilder()
    if not is_employee_specified:
        builder.row(InlineKeyboardButton(
            text='Другой сотрудник',
            callback_data=ChangeData(field='employee_id').pack()))
        return builder.as_markup()
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


def confirmation_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text='Всё правильно',
        callback_data=ConfirmationData(confirm=True).pack()))
    builder.row(InlineKeyboardButton(
        text='Хочу что-нибудь изменить',
        callback_data=ConfirmationData(confirm=False).pack()))
    return builder.as_markup()

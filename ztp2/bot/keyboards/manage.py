from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from ..callbacks.manage import SelectData, ManageData


def selecting_keyboard(is_employee_specified: bool = True,
                       is_all_shown: bool = True):
    builder = InlineKeyboardBuilder()
    first_row = [
        InlineKeyboardButton(
            text='Меньше',
            callback_data=SelectData(field='limit', action='dec').pack()),
        InlineKeyboardButton(
            text='Больше',
            callback_data=SelectData(field='limit', action='inc').pack()),
    ]
    if is_employee_specified:
        first_row.append(InlineKeyboardButton(
            text='Все',
            callback_data=SelectData(field='employee',
                                     action='nullify').pack()))
    else:
        first_row.append(InlineKeyboardButton(
            text='Мои',
            callback_data=SelectData(field='employee',
                                     action='specify').pack()))
    if is_all_shown:
        second_row = [
            InlineKeyboardButton(
                text='Спрятать готовые',
                callback_data=SelectData(field='status',
                                         action='waiting').pack())
        ]
    else:
        second_row = [
            InlineKeyboardButton(
                text='Показать готовые',
                callback_data=SelectData(field='status',
                                         action='all').pack())
        ]
    builder.row(*first_row)
    builder.row(*second_row)
    return builder.as_markup()


def main_keyboard(is_ztp_started: bool,
                  is_own_switch: bool,
                  is_config_prepared):
    builder = InlineKeyboardBuilder()
    if is_ztp_started:
        row = [
            InlineKeyboardButton(
                text='Остановить ZTP',
                callback_data=ManageData(cat='ztp', action='stop').pack())
        ]
    else:
        row = [
            InlineKeyboardButton(
                text='Начать ZTP',
                callback_data=ManageData(cat='ztp', action='start').pack())
        ]
    builder.row(*row)
    return builder.as_markup()

from aiogram.utils.keyboard import InlineKeyboardBuilder, InlineKeyboardButton
from ..callbacks.manage import SelectData, ManageData, ScreenData


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


def main_keyboard(is_ztp_started: bool):
    builder = InlineKeyboardBuilder()
    if is_ztp_started:
        builder.row(
            InlineKeyboardButton(
                text='Остановить ZTP',
                callback_data=ManageData(cat='ztp', action='stop_ztp').pack()))
    else:
        builder.row(
            InlineKeyboardButton(
                text='Начать ZTP',
                callback_data=ManageData(cat='ztp', action='start_ztp').pack()))
    builder.row(
        InlineKeyboardButton(
            text='Настройки',
            callback_data=ScreenData(screen='parameters').pack()),
        InlineKeyboardButton(
            text='Конфиг',
            callback_data=ScreenData(screen='configuration').pack()))
    builder.row(
        InlineKeyboardButton(
            text='Доделать',
            callback_data=ManageData(cat='cfg', action='push').pack()))
    builder.row(
        InlineKeyboardButton(
            text='Другой свич',
            callback_data=ScreenData(screen='select').pack()))
    return builder.as_markup()


def parameters_keyboard(is_own_switch: bool = True):
    builder = InlineKeyboardBuilder()
    if is_own_switch:
        builder.row(InlineKeyboardButton(
            text='Отдать другу',
            callback_data=ManageData(cat='params', action='transfer').pack()))
    else:
        builder.row(InlineKeyboardButton(
            text='Забрать себе',
            callback_data=ManageData(cat='params',
                                     action='transfer_self').pack()))
    builder.row(
        InlineKeyboardButton(
            text='Изменить мак',
            callback_data=ManageData(cat='params', action='edit_mac').pack()),
        InlineKeyboardButton(
            text='Изменить IP',
            callback_data=ManageData(cat='params', action='edit_ip').pack()))
    builder.row(InlineKeyboardButton(
        text='Изменить вышестоящий свич',
        callback_data=ManageData(cat='params', action='edit_parent').pack()))
    builder.row(
        InlineKeyboardButton(
            text='Сохранить и выйти',
            callback_data=ScreenData(screen='main', save=True).pack()))
    builder.row(
        InlineKeyboardButton(
            text='Выйти без сохранения',
            callback_data=ScreenData(screen='main').pack()))
    return builder.as_markup()


def configuration_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text='Подписи',
            callback_data=ManageData(cat='config', action='edit_ports').pack()),
        InlineKeyboardButton(
            text='Вланы',
            callback_data=ManageData(cat='config', action='edit_vlans').pack())
    )
    builder.row(
        InlineKeyboardButton(
            text='Сохранить и выйти',
            callback_data=ScreenData(screen='main', save=True).pack()))
    builder.row(
        InlineKeyboardButton(
            text='Выйти без сохранения',
            callback_data=ScreenData(screen='main').pack()))
    return builder.as_markup()

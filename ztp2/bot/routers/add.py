from aiogram import Router, types, flags, F
import aiogram.exceptions
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
import aiohttp
import logging

from ..states.add import PreMode, Mode
from ..utils import add as utils
from ..keyboards import add as keyboards
from ..callbacks import add as callbacks
from ...remote_apis.userside import UsersideAPI
from ...utils.userside import get_inventory_item


router = Router()
logger = logging.getLogger("aiogram.event")


@router.message(Command(commands=['add']), state=None)
@router.message(Command(commands=['add']), state=PreMode)
@flags.authorization
async def start_add_process(message: types.Message,
                            state: FSMContext,
                            current_user: dict[str, str | int]):
    try:
        await message.delete()
        data = {'_is_admin': True}
    except aiogram.exceptions.TelegramBadRequest:
        data = {'_is_admin': False}
    data['employee_id'] = current_user['userside_id']
    data['serial_number'] = None
    data['mac_address'] = None
    data['_duplicate'] = False
    data['_user'] = current_user
    text = utils.make_pre_mode_select_message(data)
    reply_markup = keyboards.gathering_data_keyboard(
        data['serial_number'] is not None,
        data['mac_address'] is not None)
    msg = await message.answer(text=text, reply_markup=reply_markup)
    data['_msg'] = msg
    await state.set_data(data)
    await state.set_state(PreMode.waiting_for_serial)


@router.message(state=PreMode.waiting_for_serial)
@flags.is_using_userside
@flags.is_using_api_session
async def serial_number_spec(message: types.Message,
                             state: FSMContext,
                             api_session: aiohttp.ClientSession,
                             userside_api: UsersideAPI):
    data = await state.get_data()
    if data['_is_admin']:
        await message.delete()
    data['serial_number'] = None
    data['mac_address'] = None
    serial_number = message.text
    async with api_session.get(
            '/entries/',
            params={'serial_number': serial_number}) as response:
        duplicates = await response.json()
    data['_duplicate'] = bool(duplicates)
    try:
        async with userside_api:
            inventory_item = await get_inventory_item(serial_number,
                                                      userside_api)
    except RuntimeError:
        text = utils.make_pre_mode_select_message(data)
        text += f'\nСвич с серийным номером {serial_number} ' \
                'не найден на складе. Попробуй ещё раз'
        reply_markup = keyboards.gathering_data_keyboard(
            data['serial_number'] is not None,
            data['mac_address'] is not None)
        await data['_msg'].edit_text(text=text, reply_markup=reply_markup)
        return
    data['serial_number'] = serial_number
    arg = inventory_item.get('arg')
    if arg:
        mac = arg.get('mac')
        if mac:
            data['mac_address'] = mac
    text = utils.make_pre_mode_select_message(data)
    reply_markup = keyboards.gathering_data_keyboard(
        data['serial_number'] is not None,
        data['mac_address'] is not None)
    data['_msg'] = await data['_msg'].edit_text(text=text,
                                                reply_markup=reply_markup)
    await state.set_data(data)
    if data['mac_address'] is None:
        await state.set_state(PreMode.waiting_for_mac)


@router.message(state=PreMode.waiting_for_mac)
@flags.is_using_api_session
async def mac_address_spec(message: types.Message,
                           state: FSMContext,
                           api_session: aiohttp.ClientSession):
    data = await state.get_data()
    if data['_is_admin']:
        await message.delete()
    data['mac_address'] = None
    mac_address = message.text
    if not utils.is_mac_address(mac_address):
        text = utils.make_pre_mode_select_message(data)
        text += f'\nТекст {mac_address} не похож на MAC-адрес. ' \
                f'Попробуй ещё раз'
        reply_markup = keyboards.gathering_data_keyboard(
            data['serial_number'] is not None,
            data['mac_address'] is not None)
        await data['_msg'].edit_text(text=text, reply_markup=reply_markup)
        return
    data['mac_address'] = mac_address
    async with api_session.get(
            '/entries/',
            params={'mac_address': mac_address}) as response:
        duplicates = await response.json()
    data['_duplicate'] = bool(duplicates) or data['_duplicate']
    text = utils.make_pre_mode_select_message(data)
    reply_markup = keyboards.gathering_data_keyboard(
        data['serial_number'] is not None,
        data['mac_address'] is not None)
    data['_msg'] = await data['_msg'].edit_text(text=text,
                                                reply_markup=reply_markup)
    await state.set_data(data)


@router.message(state=PreMode.waiting_for_employee)
@flags.is_using_api_session
async def employee_spec(message: types.Message,
                        state: FSMContext,
                        api_session: aiohttp.ClientSession):
    data = await state.get_data()
    if data['_is_admin']:
        await message.delete()
    criteria = message.text
    if criteria.isdigit():
        async with api_session.get(
                '/users/',
                params={'userside_id': criteria}) as response:
            new_user = await response.json()
    else:
        async with api_session.get(
                '/users/',
                params={'name': criteria}) as response:
            new_user = await response.json()
    if len(new_user) != 1:
        return
    data['_user'] = new_user[0]
    await state.set_data(data)
    if data['serial_number'] is None:
        await state.set_state(PreMode.waiting_for_serial)
    elif data['mac_address'] is None:
        await state.set_state(PreMode.waiting_for_mac)
    text = utils.make_pre_mode_select_message(data)
    reply_markup = keyboards.gathering_data_keyboard(
        data['serial_number'] is not None,
        data['mac_address'] is not None)
    data['_msg'] = await data['_msg'].edit_text(text=text,
                                                reply_markup=reply_markup)
    await state.set_data(data)


@router.callback_query(callbacks.ChangeData.filter(), state=PreMode)
async def change_some_data(query: types.CallbackQuery,
                           callback_data: callbacks.ChangeData,
                           state: FSMContext):
    await query.answer()
    data = await state.get_data()
    field = callback_data.field
    if field == 'serial_number':
        data['serial_number'] = None
        data['mac_address'] = None
        await state.set_data(data)
        await state.set_state(PreMode.waiting_for_serial)
    elif field == 'mac_address':
        data['mac_address'] = None
        await state.set_data(data)
        await state.set_state(PreMode.waiting_for_mac)
    elif field == 'employee_id':
        data['_user'] = None
        await state.set_data(data)
        await state.set_state(PreMode.waiting_for_employee)
    text = utils.make_pre_mode_select_message(data)
    reply_markup = keyboards.gathering_data_keyboard(
        data['serial_number'] is not None,
        data['mac_address'] is not None)
    data['_msg'] = await data['_msg'].edit_text(text=text,
                                                reply_markup=reply_markup)
    await state.set_data(data)


@router.callback_query(callbacks.ModeData.filter(), state=PreMode)
async def select_mode(query: types.CallbackQuery,
                      callback_data: callbacks.ModeData,
                      state: FSMContext):
    await query.answer()
    data = await state.get_data()
    if callback_data.mode == 'change_switch':
        data['mode'] = 'change_switch'
        await state.set_state(Mode.waiting_for_ip_address)
    elif callback_data.mode == 'new_switch':
        data['mode'] = 'new_switch'
        await state.set_state(Mode.waiting_for_parent)
    elif callback_data.mode == 'new_house':
        data['mode'] = 'new_house'
        await state.set_state(Mode.waiting_for_task)
    text = utils.make_mode_select_message(data)
    data['_msg'] = await data['_msg'].edit_text(text)
    await state.set_data(data)


@router.message(state=Mode.waiting_for_ip_address)
@router.message(state=Mode.waiting_for_parent)
@flags.is_using_api_session
@flags.is_using_userside
async def ip_address_spec(message: types.Message,
                          state: FSMContext,
                          userside_api: UsersideAPI):
    data = await state.get_data()
    data['ip_address'] = None
    data['port'] = None
    data['node_id'] = None
    data['node_name'] = None
    ip_address, port = None, None
    if data['_is_admin']:
        await message.delete()
    if data['mode'] == 'change_switch':
        ip_address = message.text
    elif data['mode'] == 'new_switch':
        try:
            ip_address, port = message.text.split()
        except ValueError:
            text = utils.make_mode_select_message(data)
            text += f'Сообщение "{message.text}" не подходит под формат ' \
                    f'"[ip] [port]"'
            await data['_msg'].edit_text(text)
            return
    try:
        device_id = await userside_api.device.get_device_id(
            object_type='switch', data_typer='ip', data_value=ip_address)
    except RuntimeError:
        text = utils.make_mode_select_message(data)
        text += f'\nСвича с IP-адресом {ip_address} нет в Userside. ' \
                f'Попробуй ещё раз'
        await data['_msg'].edit_text(text)
        return
    device_data = await userside_api.device.get_data(
        object_type='switch', object_id=device_id)
    node_id = device_data[str(device_id)]['node_id']
    node_data = await userside_api.node.get(id=node_id)
    data['ip_address'] = ip_address
    data['port'] = port
    data['node_id'] = node_id
    data['node_name'] = node_data[str(node_id)]['name']
    text = utils.make_confirmation_text(data)
    data['_msg'] = await data['_msg'].edit_text(text=text)
    await state.set_data(data)

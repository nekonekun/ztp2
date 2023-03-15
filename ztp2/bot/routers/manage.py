from aiogram import Router, types, flags, F
import aiogram.exceptions
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
import aiohttp
import logging

from ..states.manage import Manage
from ..utils import manage as utils
from ..utils import common as utils_c
from ..keyboards import manage as keyboards
from ..callbacks import manage as callbacks


router = Router()
logger = logging.getLogger("aiogram.event")


@router.message(Command(commands=['manage']), state=None)
@router.message(Command(commands=['manage']), state=Manage)
@flags.is_using_api_session
@flags.authorization
async def show_switch_list(message: types.Message,
                           state: FSMContext,
                           api_session: aiohttp.ClientSession,
                           current_user: dict[str, str | int]):
    try:
        await message.delete()
        data = {'_is_admin': True}
    except aiogram.exceptions.TelegramBadRequest:
        data = {'_is_admin': False}
    data['_filter_status'] = None
    data['_filter_employee_id'] = current_user['userside_id']
    data['_filter_limit'] = 10
    switch_list = await utils.get_switch_list(
        api_session,
        employee_id=data['_filter_employee_id'],
        limit=data['_filter_limit'])
    text = utils.make_selecting_switch_message(switch_list, current_user)
    reply_markup = keyboards.selecting_keyboard()
    msg = await message.answer(text=text, reply_markup=reply_markup)
    await state.set_state(Manage.selecting_switch)
    data['_msg'] = msg
    data['_user'] = current_user
    await state.set_data(data)


@router.callback_query(callbacks.SelectData.filter())
@flags.is_using_api_session
async def edit_switch_list(query: types.CallbackQuery,
                           state: FSMContext,
                           callback_data: callbacks.SelectData,
                           api_session: aiohttp.ClientSession):
    await query.answer()
    data = await state.get_data()
    if callback_data.field == 'limit':
        if callback_data.action == 'inc':
            if data['_filter_limit'] < 40:
                data['_filter_limit'] += 10
        elif callback_data.action == 'dec':
            if data['_filter_limit'] > 10:
                data['_filter_limit'] -= 10
    elif callback_data.field == 'status':
        if callback_data.action == 'waiting':
            data['_filter_status'] = 'WAITING'
        elif callback_data.action == 'all':
            data['_filter_status'] = None
    elif callback_data.field == 'employee':
        if callback_data.action == 'nullify':
            data['_filter_employee_id'] = None
        elif callback_data.action == 'specify':
            data['_filter_employee_id'] = data['_user']['userside_id']
    switch_list = await utils.get_switch_list(
        api_session,
        employee_id=data['_filter_employee_id'],
        status=data['_filter_status'],
        limit=data['_filter_limit'])

    await state.set_data(data)

    text = utils.make_selecting_switch_message(
        switch_list,
        data['_user'],
        data['_filter_employee_id'] is not None)
    reply_markup = keyboards.selecting_keyboard(
        data['_filter_employee_id'] is not None,
        data['_filter_status'] is None)

    try:
        data['_msg'] = await data['_msg'].edit_text(text=text,
                                                    reply_markup=reply_markup)
    except aiogram.exceptions.TelegramBadRequest:
        logger.info('New switch sample is same as previous')


@router.message(state=Manage.selecting_switch)
@flags.is_using_api_session
async def choose_switch(message: types.Message,
                        state: FSMContext,
                        api_session: aiohttp.ClientSession):
    data = await state.get_data()
    if data['_is_admin']:
        await message.delete()
    if message.text.isdigit():
        async with api_session.get(f'/entries/{message.text}/') as response:
            content = await response.json()
        if not content:
            text = data['_msg'].text
            text += '\n\nСвич с таким номером не найден'
            await data['_msg'].edit_text(text=text)
            return
        entry = content
    elif utils.is_ip_address(message.text):
        async with api_session.get(f'/entries/',
                                   params={
                                       'ip_address': message.text
                                   }) as response:
            content = await response.json()
        if not content:
            text = data['_msg'].text
            text += '\n\nСвич с таким IP-адресом не найден'
            await data['_msg'].edit_text(text=text)
            return
        entry = content[0]
    else:
        text = data['_msg'].text
        text += '\n\nВведённый текст не похож ни на IP-адрес, ни на номер свича'
        await data['_msg'].edit_text(text=text)
        return
    data = await utils.make_switch_data(data['_msg'], data['_user'],
                                        data['_is_admin'], entry, api_session)
    data = utils_c.filter_data(data)
    await state.set_state(Manage.main)
    await state.set_data(data)
    text = utils.make_main_manage_message(data)
    reply_markup = keyboards.main_keyboard(data['celery_id'] is not None)
    await data['_msg'].edit_text(text=text, reply_markup=reply_markup)


@router.callback_query(callbacks.ManageData.filter(F.cat == 'ztp'))
@flags.is_using_api_session
async def ztp_control(query: types.CallbackQuery,
                      state: FSMContext,
                      callback_data: callbacks.ManageData,
                      api_session: aiohttp.ClientSession):
    await query.answer()
    data = await state.get_data()
    action = callback_data.action
    if action == 'start_ztp':
        task_id = await utils.start_ztp(api_session,
                                        data['id'],
                                        query.message.chat.id)
        data['celery_id'] = task_id
        await state.set_data(data)
    elif action == 'stop_ztp':
        await utils.stop_ztp(api_session, data['celery_id'])
        data['celery_id'] = None
        await state.set_data(data)
    reply_markup = keyboards.main_keyboard(data['celery_id'] is not None)
    await data['_msg'].edit_reply_markup(reply_markup=reply_markup)


@router.callback_query(callbacks.ScreenData.filter())
@flags.is_using_api_session
async def switch_to_screen(query: types.CallbackQuery,
                           state: FSMContext,
                           callback_data: callbacks.ScreenData,
                           api_session: aiohttp.ClientSession):
    data = await state.get_data()
    await query.answer()
    if callback_data.screen == 'parameters':
        text = utils.make_main_manage_message(data)
        reply_markup = keyboards.parameters_keyboard(
            data['_user']['userside_id'] == data['_owner']['userside_id']
        )
        data['_msg'] = await data['_msg'].edit_text(text=text,
                                                    reply_markup=reply_markup)
        await state.set_data(data)
    elif callback_data.screen == 'main':
        ztp_id = data['id']
        if callback_data.save:
            update_params = {
                key: value
                for key, value in data.items()
                if key[0] != '_'
            }
            async with api_session.patch(f'/entries/{ztp_id}/',
                                         json=update_params) as response:
                entry = await response.json()
        else:
            async with api_session.get(f'/entries/{ztp_id}/') as response:
                entry = await response.json()
        data = await utils.make_switch_data(data['_msg'], data['_user'],
                                            data['_is_admin'], entry,
                                            api_session)
        text = utils.make_main_manage_message(data)
        reply_markup = keyboards.main_keyboard(data['celery_id'] is not None)
        data['_msg'] = await data['_msg'].edit_text(text=text,
                                                    reply_markup=reply_markup)
        await state.set_data(data)
    elif callback_data.screen == 'configuration':
        text = utils.make_configuration_message(data)
        reply_markup = keyboards.configuration_keyboard()
        data['_msg'] = await data['_msg'].edit_text(text=text,
                                                    reply_markup=reply_markup)
        await state.set_state(Manage.waiting_for_movements)
        await state.set_data(data)


@router.callback_query(callbacks.ManageData.filter(F.cat == 'params'))
async def edit_parameters(query: types.CallbackQuery,
                          state: FSMContext,
                          callback_data: callbacks.ManageData):
    data = await state.get_data()
    await query.answer()
    if callback_data.action == 'transfer_self':
        data['employee_id'] = data['_user']['userside_id']
        data['_owner'] = data['_user']
        text = utils.make_main_manage_message(data)
        reply_markup = keyboards.parameters_keyboard(
            data['_user']['userside_id'] == data['_owner']['userside_id']
        )
        data['_msg'] = await data['_msg'].edit_text(text=text,
                                                    reply_markup=reply_markup)
    elif callback_data.action == 'transfer':
        await state.set_state(Manage.waiting_for_employee)
        text = utils.make_main_manage_message(data)
        text += '\nВведи имя или номер сотрудника'
        data['_msg'] = await data['_msg'].edit_text(text=text,
                                                    reply_markup=None)
    elif callback_data.action == 'edit_mac':
        await state.set_state(Manage.waiting_for_mac)
        text = utils.make_main_manage_message(data)
        text += '\nВведи новый MAC адрес'
        data['_msg'] = await data['_msg'].edit_text(text=text,
                                                    reply_markup=None)
    elif callback_data.action == 'edit_ip':
        await state.set_state(Manage.waiting_for_ip)
        text = utils.make_main_manage_message(data)
        text += '\nВведи новый IP адрес'
        data['_msg'] = await data['_msg'].edit_text(text=text,
                                                    reply_markup=None)
    elif callback_data.action == 'edit_parent':
        await state.set_state(Manage.waiting_for_parent)
        text = utils.make_main_manage_message(data)
        text += '\nВведи новый свич и порт подключения в формате "[ip] [port]"'
        data['_msg'] = await data['_msg'].edit_text(text=text,
                                                    reply_markup=None)
    await state.set_data(data)


@router.message(state=Manage.waiting_for_employee)
@flags.is_using_api_session
async def employee_edit(message: types.Message,
                        state: FSMContext,
                        api_session: aiohttp.ClientSession):
    data = await state.get_data()
    criteria = message.text
    employee = await utils_c.get_employee(criteria, api_session)
    if employee:
        if data['_is_admin']:
            await message.delete()
        data['_owner'] = employee
        data['employee_id'] = employee['userside_id']
    await state.set_state(Manage.main)
    text = utils.make_main_manage_message(data)
    reply_markup = keyboards.parameters_keyboard(
        data['_user']['userside_id'] == data['_owner']['userside_id']
    )
    data['_msg'] = await data['_msg'].edit_text(text=text,
                                                reply_markup=reply_markup)
    await state.set_data(data)


@router.message(state=Manage.waiting_for_ip)
async def ip_address_edit(message: types.Message,
                          state: FSMContext):
    data = await state.get_data()
    possible_ip = message.text
    if utils_c.is_ip_address(possible_ip):
        if data['_is_admin']:
            await message.delete()
        data['ip_address'] = possible_ip
    await state.set_state(Manage.main)
    text = utils.make_main_manage_message(data)
    reply_markup = keyboards.parameters_keyboard(
        data['_user']['userside_id'] == data['_owner']['userside_id']
    )
    data['_msg'] = await data['_msg'].edit_text(text=text,
                                                reply_markup=reply_markup)
    await state.set_data(data)


@router.message(state=Manage.waiting_for_mac)
async def mac_address_edit(message: types.Message,
                           state: FSMContext):
    data = await state.get_data()
    possible_mac = message.text
    if utils_c.is_mac_address(possible_mac):
        if data['_is_admin']:
            await message.delete()
        data['mac_address'] = possible_mac
    await state.set_state(Manage.main)
    text = utils.make_main_manage_message(data)
    reply_markup = keyboards.parameters_keyboard(
        data['_user']['userside_id'] == data['_owner']['userside_id']
    )
    data['_msg'] = await data['_msg'].edit_text(text=text,
                                                reply_markup=reply_markup)
    await state.set_data(data)


@router.message(state=Manage.waiting_for_parent)
async def parent_edit(message: types.Message,
                      state: FSMContext):
    data = await state.get_data()
    try:
        parent_switch, parent_port = message.text.split()
    except ValueError:
        logging.error('oops')
    else:
        if data['_is_admin']:
            await message.delete()
        data['parent_switch'] = parent_switch
        data['parent_port'] = parent_port
    await state.set_state(Manage.main)
    text = utils.make_main_manage_message(data)
    reply_markup = keyboards.parameters_keyboard(
        data['_user']['userside_id'] == data['_owner']['userside_id']
    )
    data['_msg'] = await data['_msg'].edit_text(text=text,
                                                reply_markup=reply_markup)
    await state.set_data(data)


@router.message(state=Manage.waiting_for_movements)
async def parent_edit(message: types.Message,
                      state: FSMContext):
    new_movements = utils.extract_movements(message.text)
    if not new_movements:
        return
    data = await state.get_data()
    if data['_is_admin']:
        await message.delete()
    movements: dict = data['port_movements'].copy()
    movements.update(new_movements)
    movements = {k: v
                 for k, v
                 in movements.items()
                 if k != v}
    new_port_settings = utils.apply_movements(data['original_port_settings'],
                                              movements)
    data['port_movements'] = movements
    data['modified_port_settings'] = new_port_settings
    await state.set_data(data)
    text = utils.make_configuration_message(data)
    reply_markup = keyboards.configuration_keyboard()
    data['_msg'] = await data['_msg'].edit_text(text=text,
                                                reply_markup=reply_markup)


@router.callback_query(callbacks.ManageData.filter(F.cat == 'config'))
async def edit_configuration(query: types.CallbackQuery,
                             state: FSMContext,
                             callback_data: callbacks.ManageData):
    await query.answer()
    if callback_data.action == 'edit_descrs':
        text = query.message.text
        text += '\n\nУкажи подписи в формате "{port} [{description}]"\n' \
                'Если указать только номер порта -- подпись будет стёрта\n' \
                'Можно указать сразу несколько, каждый с новой строки'
        await state.set_state(Manage.waiting_for_descriptions)
    elif callback_data.action == 'edit_vlans':
        text = query.message.text
        text += '\n\nУкажи вланы в формате "{vid} [{name}]"\n' \
                'Если указать только номер влана -- влан будет удалён\n' \
                'Можно указать сразу несколько, каждый с новой строки'
        await state.set_state(Manage.waiting_for_vlans)
    elif callback_data.action == 'edit_ports':
        text = query.message.text
        text += '\n\nУкажи вланы списком в dlink-формате'
        data = await state.get_data()
        data['_action'] = callback_data.params
        await state.set_data(data)
        await state.set_state(Manage.waiting_for_vlanids)
    await query.message.edit_text(text=text)  # noqa


@router.message(state=Manage.waiting_for_descriptions)
@router.message(state=Manage.waiting_for_vlans)
async def config_edit(message: types.Message,
                      state: FSMContext):
    names = utils.extract_names(message.text)
    data = await state.get_data()
    if not names:
        text = utils.make_configuration_message(data)
        reply_markup = keyboards.configuration_keyboard()
        data['_msg'] = await data['_msg'].edit_text(text=text,
                                                    reply_markup=reply_markup)
        await state.set_data(data)
        await state.set_state(Manage.waiting_for_movements)
        return
    current_state = await state.get_state()
    if current_state == Manage.waiting_for_descriptions:
        for index, description in names.items():
            data['modified_port_settings'][index]['description'] = description
    elif current_state == Manage.waiting_for_vlans:
        for vlan_id, name in names.items():
            if not name:
                if data['modified_vlan_settings'].get(vlan_id):
                    data['modified_vlan_settings'].pop(vlan_id)
            else:
                data['modified_vlan_settings'][vlan_id] = name
    else:
        return
    text = utils.make_configuration_message(data)
    reply_markup = keyboards.configuration_keyboard()
    data['_msg'] = await data['_msg'].edit_text(text=text,
                                                reply_markup=reply_markup)
    await state.set_data(data)
    await state.set_state(Manage.waiting_for_movements)


@router.message(state=Manage.waiting_for_vlanids)
async def port_vlan_edit_start(message: types.Message,
                               state: FSMContext):
    data = await state.get_data()
    vlan_text = message.text
    vlanids = utils.expand_ranges(vlan_text)
    if not vlanids:
        return
    if data['_is_admin']:
        await message.delete()
    data['_vlanids'] = vlanids
    await state.set_data(data)
    await state.set_state(Manage.waiting_for_ports)
    text = data['_msg'].text
    text += f'\n\nВыбраны вланы {vlan_text}\n' \
            f'Укажи порты списком в dlink-формате'
    await data['_msg'].edit_text(text=text)


@router.message(state=Manage.waiting_for_ports)
async def port_vlan_edit_finish(message: types.Message,
                                state: FSMContext):
    ports = utils.expand_ranges(message.text)
    if not ports:
        return
    data = await state.get_data()
    if data['_is_admin']:
        await message.delete()
    port_settings = data['modified_port_settings']
    new_port_settings = utils.update_port_vlan_settings(port_settings,
                                                        data['_action'],
                                                        data['_vlanids'],
                                                        ports)
    data['modified_port_settings'] = new_port_settings
    data.pop('_action')
    data.pop('_vlanids')
    text = utils.make_configuration_message(data)
    reply_markup = keyboards.configuration_keyboard()
    data['_msg'] = await data['_msg'].edit_text(text=text,
                                                reply_markup=reply_markup)
    await state.set_data(data)
    await state.set_state(Manage.waiting_for_movements)

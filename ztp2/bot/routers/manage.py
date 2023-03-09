from aiogram import Router, types, flags, F
import aiogram.exceptions
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
import aiohttp
import logging

from ..states.manage import Manage
from ..utils import manage as utils
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
    async with api_session.get(f'/models/{entry["model_id"]}/') as response:
        content = await response.json()
    model = content['model']
    entry['model'] = model
    async with api_session.get(
            '/users/',
            params={'userside_id': entry['employee_id']}) as response:
        content = await response.json()
    data['owner'] = content[0]
    data.update(entry)
    data = {k: v
            for k, v in data.items()
            if (k[0] != '_') or (k in ['_msg', '_user'])}
    await state.set_state(Manage.main)
    await state.set_data(data)
    text = utils.make_main_manage_message(data, data['owner'])
    reply_markup = keyboards.main_keyboard(
        data['celery_id'] is not None,
        False
    )
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
    reply_markup = keyboards.main_keyboard(
        data['celery_id'] is not None,
        False
    )
    await data['_msg'].edit_reply_markup(reply_markup=reply_markup)


@router.callback_query(callbacks.ScreenData.filter())
async def switch_to_screen(query: types.CallbackQuery,
                           state: FSMContext,
                           callback_data: callbacks.ManageData):
    pass

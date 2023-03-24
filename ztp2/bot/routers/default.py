from aiogram import Router, types, flags
import aiogram.exceptions
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
import aiohttp
import logging

from ..states.manage import Manage
from ..states.add import PreMode
from ..utils import add as utils_a
from ..utils import manage as utils_m
from ..keyboards import add as keyboards_a
from ..keyboards import manage as keyboards_m

router = Router()
logger = logging.getLogger("aiogram.event")


@router.message(Command(commands=['cancel']))
async def cancel(message: types.Message,
                 state: FSMContext):
    await state.clear()


@router.message(Command(commands=['add']))
@flags.authorization
async def start_add_process(message: types.Message,
                            state: FSMContext,
                            current_user: dict[str, str | int]):
    data = await state.get_data()
    await state.clear()
    if data.get('_msg'):
        await data['_msg'].delete_reply_markup()
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
    text = utils_a.make_pre_mode_select_message(data)
    reply_markup = keyboards_a.gathering_data_keyboard(
        data['_user'] is not None,
        data['serial_number'] is not None,
        data['mac_address'] is not None)
    msg = await message.answer(text=text, reply_markup=reply_markup)
    data['_msg'] = msg
    await state.set_data(data)
    await state.set_state(PreMode.waiting_for_serial)


# @router.message(Command(commands=['manage']), state=None)
# @router.message(Command(commands=['manage']), state=Manage)
@router.message(Command(commands=['manage']))
@flags.is_using_api_session
@flags.authorization
async def show_switch_list(message: types.Message,
                           state: FSMContext,
                           api_session: aiohttp.ClientSession,
                           current_user: dict[str, str | int]):
    data = await state.get_data()
    await state.clear()
    if data.get('_msg'):
        await data['_msg'].delete_reply_markup()
    try:
        await message.delete()
        data = {'_is_admin': True}
    except aiogram.exceptions.TelegramBadRequest:
        data = {'_is_admin': False}
    data['_filter_status'] = None
    data['_filter_employee_id'] = current_user['userside_id']
    data['_filter_limit'] = 10
    switch_list = await utils_m.get_switch_list(
        api_session,
        employee_id=data['_filter_employee_id'],
        limit=data['_filter_limit'])
    text = utils_m.make_selecting_switch_message(switch_list, current_user)
    reply_markup = keyboards_m.selecting_keyboard()
    msg = await message.answer(text=text, reply_markup=reply_markup)
    await state.set_state(Manage.selecting_switch)
    data['_msg'] = msg
    data['_user'] = current_user
    await state.set_data(data)
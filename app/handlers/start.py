import os

from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from dotenv import load_dotenv

load_dotenv(override=False)

router_start = Router()


@router_start.message(Command('start'))
async def echo_start(message: types.Message):
    web_app_url = os.getenv('WEB_APP_URL')
    button = InlineKeyboardButton(
        text='Відкрити застосунок',
        web_app=WebAppInfo(url=web_app_url),
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])
    await message.answer('Ласкаво просимо до StoryFluentGram!', reply_markup=keyboard)

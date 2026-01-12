from aiogram import types, Router
from aiogram.filters import Command
from aiogram.types import WebAppInfo, InlineKeyboardButton, InlineKeyboardMarkup
from app.settings.create_bot import dp
from dotenv import load_dotenv

import os

load_dotenv(override=False)

router_start = Router()

@router_start.message(Command('start'))
async def echo_start(message: types.Message):
    web_app_url = os.getenv("WEB_APP_URL")
    button = InlineKeyboardButton(text="Open WebApp", web_app=WebAppInfo(url=web_app_url))
    kb = InlineKeyboardMarkup(inline_keyboard=[[button]])
    await message.answer("Добро пожаловать в StoryFluentGram:", reply_markup=kb)
    
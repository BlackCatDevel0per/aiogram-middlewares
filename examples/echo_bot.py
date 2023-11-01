import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram_middlewares import RateLimiter, ThrottlingMiddleware
from dotenv import dotenv_values

logging.basicConfig(
	format='%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s',
	level=logging.INFO,
)
logging.getLogger('aiogram_middlewares').setLevel(logging.DEBUG)

# For aiogram v3.x!
TOKEN = dotenv_values(Path(Path(__file__).resolve().parent, '.env'))['BOT_TOKEN']


bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

dp.update.outer_middleware(
	ThrottlingMiddleware(
		period_sec=3, after_handle_count=2,
		# topping_up=False,
		is_cache_unity=False,  # Because will throttle twice with filters cache.
	),
)


@dp.message(RateLimiter(period_sec=15, after_handle_count=2), Command('help'))
async def help_handler(message: types.Message) -> None:
	await message.reply('Hi! This is echo bot for testing throttling =)')


@dp.message()
async def echo_handler(message: types.Message) -> None:
	await message.send_copy(chat_id=message.chat.id)


async def start_bot() -> None:
	try:
		await dp.start_polling(bot, skip_updates=True)
	finally:
		await bot.session.close()


if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	loop.run_until_complete(start_bot())

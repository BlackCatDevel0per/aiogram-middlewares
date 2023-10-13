from __future__ import annotations

import asyncio
import logging

from aiogram_middlewares import ThrottlingMiddleware

from tests.fixtures import data, empty_handler, message

logging.basicConfig(format='%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s', level=logging.INFO)
logging.getLogger('aiogram_middlewares').setLevel(logging.DEBUG)

middleware = ThrottlingMiddleware(
	period_sec=8, after_handle_count=2,
	# topping_up=False,
)


async def spam_events(times: int, period: int | float = 0.1) -> None:
	for i in range(times):
		logging.info('spam event #%i', i)
		await asyncio.sleep(period)
		await middleware(empty_handler, message, data)


async def test_middleware():
	logging.info('spam with period 1')
	await spam_events(8, 1)
	logging.info('5 sec sleep.. (should topping up or not)')
	await asyncio.sleep(5)
	await spam_events(5, 1)
	logging.info('10 sec sleep.. (should reset)')
	await asyncio.sleep(10)
	logging.info('spam with period 0.1')
	await spam_events(20, 0.1)


if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	loop.run_until_complete(test_middleware())

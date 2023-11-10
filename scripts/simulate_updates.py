from __future__ import annotations

import asyncio
import logging

from aiogram_middlewares import RateMiddleware
from aiogram_middlewares.utils import BrotliedPickleSerializer

# TODO: More fixtures (msg, query, inline and etc. formats & etc) & bug fixes..
from tests.fixtures import data, data2, empty_handler, message, message2

logging.basicConfig(
	format='%(filename)s [LINE:%(lineno)d] #%(levelname)-8s [%(asctime)s]  %(message)s',
	level=logging.INFO,
)
logging.getLogger('aiogram_middlewares').setLevel(logging.DEBUG)

# FIXME: Annotations..
middleware = RateMiddleware(
	throttling_mode=True,
	sem_period=4,
	topping_up=False,

	period_sec=8, after_handle_count=2,
	warnings_count=1,
	# topping_up=False,##
	# cooldown_message=None,
	# calmed_message=None,
	# data_serializer=BrotliedPickleSerializer,
)

# from simulate_updates_throttle import ThrottlingMiddleware

# middleware = ThrottlingMiddleware(8, 4)


async def spam_events(times: int, period: int | float = 0.1) -> None:
	for i in range(times):
		logging.info('spam event #%i', i)
		await asyncio.sleep(period)
		await middleware(empty_handler, message, data)

		# await asyncio.sleep(period * 2)
		# await middleware(empty_handler, message2, data2)


async def test_middleware():
	# logging.info('spam with period 1')
	await spam_events(8, 1)
	# logging.info('5 sec sleep.. (should topping up or not)')
	# await asyncio.sleep(5)
	# await spam_events(5, 1)
	# logging.info('10 sec sleep.. (should reset)')
	# await asyncio.sleep(10)
	# logging.info('spam with period 0.1')
	# await spam_events(20, 0.1)

	# await asyncio.sleep(10)


if __name__ == '__main__':
	loop = asyncio.get_event_loop()
	loop.run_until_complete(test_middleware())

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram_middlewares.rater.base import RaterABC
from aiogram_middlewares.rater.models import RateData

from .locks import ThrottleSemaphore

if TYPE_CHECKING:

	from typing import Any

	from aiogram import Bot
	from aiogram.types import Update, User

	from aiogram_middlewares.rater.base import HandleType
	from aiogram_middlewares.rater.types import _RD, HandleData

	from .locks import PositiveFloat, PositiveInt


logger = logging.getLogger(__name__)


# FIXME: Duplicating..
# TODO: Limiters claen by weakref..
# FIXME: Name & docs..
class RaterThrottleBase(RaterABC):

	def __init__(
		self: RaterThrottleBase,
		sem_period: PositiveInt | PositiveFloat | None,
	) -> None:
		self.sem_period: PositiveInt | PositiveFloat

		if sem_period is None:
			self.sem_period = self.period_sec - (self.period_sec / 100)  # FIXME: %%
			logger.warning('Throttle period is not set! In use: %f', self.sem_period)  # TODO: More info..
		else:
			if sem_period >= self.period_sec:
				msg = (
					f'Throttle time must be lower than ttl!'
					f' `{sem_period=}` >= `period_sec={self.period_sec}`'
				)
				raise ValueError(msg)
			self.sem_period = sem_period


	async def _trigger(
		self: RaterThrottleBase, rate_data: _RD | None,
		event_user: User, ttl: int, bot: Bot,  # noqa: ARG002
	) -> RateData | _RD:
		"""Antiflood.."""
		# Runs at first trigger to create entity, else returns data (counters)
		if not rate_data:
			logger.debug(
				'[%s] Handle user (begin): %s',
				self.__class__.__name__, event_user.username,
			)

			rate_data = RateData()
			# Add new item to cache with ttl from initializator.
			# (`Cache.add` does the same, but with checking in cache..)
			# TODO: Mb make custom variant for that..
			# TODO: Clean cache on exceptions.. (to avoid mutes..)
			self._cache.set(
				event_user.id, rate_data,
				obj=ThrottleSemaphore(
					max_rate=self.after_handle_count,
					time_period=self.sem_period,
				),
				ttl=ttl,
			)
		assert rate_data is not None  # plug for linter
		return rate_data


	async def throttle(self: RaterThrottleBase, sem: ThrottleSemaphore) -> None:
		await sem.acquire()


	async def _middleware(
		self: RaterThrottleBase,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		rate_data: RateData,
	) -> Any:
		"""Main middleware."""
		# TODO: Mb one more variant(s) for debug.. (better by decorators..)

		# proc/pass update action while not exceed rate limit (run times limit from `after_handle_count`)
		sem = self._cache.get_obj(event_user.id)
		assert sem is not None  # plug for linter

		await self.throttle(sem)
		# count up rate & proc
		return await self.proc_handle(
			handle, rate_data, event, event_user,
			data,
		)

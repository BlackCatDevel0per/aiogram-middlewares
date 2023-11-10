from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING

from aiogram_middlewares.rater.extensions.notify import RateMiddleABC

if TYPE_CHECKING:
	from typing import Any, Awaitable, Callable

	from aiogram import Bot
	from aiogram.types import Update, User

	from aiogram_middlewares.rater.base import HandleType
	from aiogram_middlewares.rater.models import RateData
	from aiogram_middlewares.rater.types import HandleData

	from .locks import ThrottleSemaphore


logger = logging.getLogger(__name__)


class RateThrottleMiddleABC(RateMiddleABC):
	throttle: Callable[[ThrottleSemaphore], Awaitable[None]]


class RateThrottleNotifyBase(RateThrottleMiddleABC):


	@abstractmethod
	async def on_exceed_rate(
		self: RateThrottleNotifyBase,
		handle: HandleType,
		rate_data: RateData, event: Update, event_user: User, data: HandleData,
		bot: Bot,
	) -> None:
		raise NotImplementedError


	async def _middleware(
		self: RateThrottleNotifyBase,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		rate_data: RateData,
	) -> Any:
		"""Main middleware."""
		# TODO: Mb one more variant(s) for debug.. (better by decorators..)

		sem = self._cache.get_obj(event_user.id)
		assert sem is not None  # plug for linter

		# proc/pass update action while not exceed rate limit (run times limit from `after_handle_count`)
		# TODO: More test `calmed` notify..

		if sem.locked():
			await self.on_exceed_rate(handle, rate_data, event, event_user, data, bot)

		# TODO: On queue/task(s) end normally send calmed message..
		await self.throttle(sem)
		return await self.proc_handle(
			handle, rate_data, event, event_user,
			data,
		)

from __future__ import annotations

import asyncio
import logging
from abc import abstractmethod
from typing import TYPE_CHECKING

from aiogram_middlewares.rater.base import RaterAttrsABC

from .notify import RateMiddleABC

if TYPE_CHECKING:

	from typing import Any

	from aiogram import Bot
	from aiogram.types import Update, User

	from aiogram_middlewares.rater.base import HandleType
	from aiogram_middlewares.rater.types import HandleData

	from .models import RateData


logger = logging.getLogger(__name__)


# FIXME: Duplicating..
class RateThrottleBase(RaterAttrsABC):

	async def throttle(self: RateThrottleBase) -> None:
		await asyncio.sleep(self.period_sec)


	async def _middleware(
		self: RateThrottleBase,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		rate_data: RateData,
	) -> Any:
		"""Main middleware."""
		##
		is_not_exceed_rate = self.after_handle_count > rate_data.rate
		# TODO: Mb one more variant(s) for debug.. (better by decorators..)

		# proc/pass update action while not exceed rate limit (run times limit from `after_handle_count`)
		print(rate_data.rate)
		if is_not_exceed_rate:
			# count up rate & proc
			return await self.proc_handle(
				handle, rate_data, event, event_user,
				data,
			)

		await self.throttle()
		return await self.proc_handle(
			handle, rate_data, event, event_user,
			data,
		)


class RateThrottleNotifyBase(RateMiddleABC):


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
		##
		is_not_exceed_rate = self.after_handle_count > rate_data.rate
		# TODO: Mb one more variant(s) for debug.. (better by decorators..)

		# proc/pass update action while not exceed rate limit (run times limit from `after_handle_count`)
		if is_not_exceed_rate:
			# count up rate & proc
			# FIXME: Remove useless counter param?
			return await self.proc_handle(####
				handle, rate_data, event, event_user,
				data,
			)

		await self.on_exceed_rate(handle, rate_data, event, event_user, data, bot)
		await RateThrottleBase.throttle(self)
		return await self.proc_handle(####
			handle, rate_data, event, event_user,
			data,
		)

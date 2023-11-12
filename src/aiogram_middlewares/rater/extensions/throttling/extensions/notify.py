from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from aiogram_middlewares.rater.base import RaterAttrsABC
from aiogram_middlewares.rater.extensions.notify import RateNotifyCooldown

if TYPE_CHECKING:
	from typing import Any, Awaitable, Callable

	from aiogram import Bot
	from aiogram.types import Update, User

	from aiogram_middlewares.rater.base import HandleType
	from aiogram_middlewares.rater.extensions.notify import PositiveInt  # FIXME: Move to types..
	from aiogram_middlewares.rater.models import RateData
	from aiogram_middlewares.rater.types import HandleData

	from .locks import ThrottleSemaphore


logger = logging.getLogger(__name__)


class RateThrottleMiddleABC(RaterAttrsABC, ABC):
	throttle: Callable[[ThrottleSemaphore], Awaitable[None]]


	@abstractmethod
	async def on_exceed_rate(
		self: RateThrottleMiddleABC,
		handle: HandleType,
		rate_data: RateData, sem: ThrottleSemaphore, event: Update, event_user: User,
		data: HandleData,
		bot: Bot,
	) -> None:
		raise NotImplementedError


	@abstractmethod
	async def _middleware(
		self: RateThrottleMiddleABC,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		rate_data: RateData,
	) -> Any | None:
		raise NotImplementedError


# FIXME: Fix calm message send rate (so visible on high load or bad connection with server).. lol..


class RateThrottleNotifyBase(RateThrottleMiddleABC):


	@abstractmethod
	async def on_exceed_rate(
		self: RateThrottleNotifyBase,
		handle: HandleType,
		rate_data: RateData, sem: ThrottleSemaphore, event: Update, event_user: User,
		data: HandleData,
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
			await self.on_exceed_rate(handle, rate_data, sem, event, event_user, data, bot)

		# TODO: On queue/task(s) end normally send calmed message..
		await self.throttle(sem)
		return await self.proc_handle(
			handle, rate_data, event, event_user,
			data,
		)


# Calmed
class RateThrottleNotifyCalmed(RateThrottleMiddleABC):

	def __init__(
		self: RateThrottleNotifyCalmed,
		calmed_message: str | None,
	) -> None:
		self.calmed_message = calmed_message


	async def on_exceed_rate(
		self: RateThrottleNotifyCalmed | RateThrottleNotifyCC,
		handle: HandleType,  # noqa: ARG002
		rate_data: RateData, sem: ThrottleSemaphore, event: Update, event_user: User,  # noqa: ARG002
		data: HandleData,  # noqa: ARG002
		bot: Bot,
	) -> None:
		"""Call: On item in cache die - send message to user or log on error."""
		# TODO: Make try/raise optionally..

		sem.stick_leak_done_callback(
			lambda: asyncio.create_task(
				bot.send_message(
					chat_id=event_user.id, text=self.calmed_message,
				),
			),
		)

		# ...


class RateThrottleNotifyCooldown(RateThrottleMiddleABC):

	def __init__(
		self: RateThrottleNotifyCooldown,  # TODO: Pass Final Assembler..
		cooldown_message: str | None,
		warnings_count: PositiveInt,
	) -> None:
		# TODO: Check to int..
		if warnings_count < 0:
			msg = f'`warnings_count` must be positive, `{warnings_count=}`'
			raise ValueError(msg)

		self.warnings_count = warnings_count
		self.cooldown_message = cooldown_message


	async def on_exceed_rate(
		self: RateThrottleNotifyCooldown | RateThrottleNotifyCC,
		handle: HandleType,
		rate_data: RateData, sem: ThrottleSemaphore | None, event: Update, event_user: User,  # noqa: ARG002
		data: HandleData,
		bot: Bot,
	) -> None:
		await RateNotifyCooldown.on_exceed_rate(
			self, handle, rate_data, event, event_user, data, bot,
		)


	async def try_user_warning(
		self: RateThrottleNotifyCooldown | RateThrottleNotifyCC, rate_data: RateData,
		event_user: User, bot: Bot,
	) -> None:
		return await RateNotifyCooldown.try_user_warning(self, rate_data, event_user, bot)


# Cooldown + Calmed
class RateThrottleNotifyCC(RateThrottleNotifyCooldown):

	def __init__(
		self: RateThrottleNotifyCC,
		calmed_message: str | None, cooldown_message: str | None,
		warnings_count: PositiveInt,
	) -> None:
		self.warnings_count = warnings_count
		self.cooldown_message = cooldown_message
		self.calmed_message = calmed_message


	async def on_exceed_rate(
		self: RateThrottleNotifyCC,
		handle: HandleType,
		rate_data: RateData, sem: ThrottleSemaphore, event: Update, event_user: User,
		data: HandleData,
		bot: Bot,
	) -> None:
		await super().on_exceed_rate(
			handle, rate_data, None, event, event_user, data, bot,
		)
		await RateThrottleNotifyCalmed.on_exceed_rate(
			self, handle, rate_data, sem, event, event_user, data, bot,
		)

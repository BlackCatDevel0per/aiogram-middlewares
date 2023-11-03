from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram.filters import Filter

from .throttling import Throttling

if TYPE_CHECKING:
	from typing import Any, Awaitable, Callable, Dict

	from aiogram import Bot
	from aiogram.types import Update, User
	from pydantic.types import PositiveInt

	from .models import ThrottlingData

	ThrottleFilterMiddleware = Callable[
		[
			None,
			None, User, Dict[str, Any], Bot, ThrottlingData,
		], Awaitable[bool],
	]
	##Update


logger = logging.getLogger(__name__)


# TODO: Rename..
# TODO: Review..
class RateLimiter(Throttling, Filter):
	middleware: ThrottleFilterMiddleware
	# Limits should be greater than in middleware.. (For handle times too!)
	def __init__(
		self: RateLimiter,
		*, period_sec: PositiveInt = 3, after_handle_count: PositiveInt = 1,
		warnings_count: PositiveInt = 2,
		calmed_message: str | None = None,
		cooldown_message: str = 'Calm down!', topping_up: bool = True,
		is_cache_unity: bool = False,
	) -> None:
		# TODO: Some optional kwargs..
		super().__init__(
			period_sec=period_sec,
			after_handle_count=after_handle_count,
			warnings_count=warnings_count,
			cooldown_message=cooldown_message,
			calmed_message=calmed_message,
			topping_up=topping_up,
			is_cache_unity=is_cache_unity,
		)


	async def proc_handle(
		self: RateLimiter,
		handler: None,  # type: ignore  # noqa: ARG002
		throttling_data: ThrottlingData, counter: str,
		event: Update, event_user: User, data: dict[str, Any],  # noqa: ARG002
	) -> bool:
		"""Process handler's update."""
		throttling_data.update_counter(counter)
		# TODO: Mb log handler's name..
		logger.debug('[%s] Handle user (proc): %s', self.__class__.__name__, event_user.username)
		return True


	# FIXME: Review..
	async def middleware(
		self: RateLimiter,
		handler: None,  # type: ignore
		event: Update,
		event_user: User,
		data: dict[str, Any],
		bot: Bot,
		throttling_data: ThrottlingData,
	) -> bool:
		# TODO: Apart this stuff..

		is_not_exceed_rate = self.after_handle_count > throttling_data.rate


		if is_not_exceed_rate:
			return await self.proc_handle(
				handler, throttling_data, 'rate', event, event_user,
				data,
			)

		return True


	async def __call__(
		self: RateLimiter, update: Update, bot: Bot,
	) -> bool:
		event_user: User = update.from_user

		event_user_throttling_data: ThrottlingData | None = await self._cache.get(event_user.id)
		throttling_data: ThrottlingData = await self.throttle(
			event_user_throttling_data, event_user, self.period_sec, bot,
		)
		del event_user_throttling_data

		return await self.middleware(None, None, event_user, update, bot, throttling_data)

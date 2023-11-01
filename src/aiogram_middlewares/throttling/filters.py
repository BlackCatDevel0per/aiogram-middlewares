from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram.filters import Filter

from .throttling import Throttling

if TYPE_CHECKING:
	from typing import Any

	from aiogram import Bot
	from aiogram.types import Update, User
	from pydantic.types import PositiveInt

	from .models import ThrottlingData
	##Update


logger = logging.getLogger(__name__)


# TODO: Rename..
class RateLimiter(Throttling, Filter):
	# Limits should be greater than in middleware.. (For handle times too!)
	def __init__(
		self: RateLimiter,
		*, period_sec: PositiveInt = 3, after_handle_count: PositiveInt = 1,
		warnings_count: PositiveInt = 2,
		cooldown_message: str = 'Calm down!', topping_up: bool = True,
		is_cache_unity: bool = False,
	) -> None:
		# TODO: Some optional kwargs..
		super().__init__(
			period_sec=period_sec,
			after_handle_count=after_handle_count,
			warnings_count=warnings_count,
			cooldown_message=cooldown_message,
			topping_up=topping_up,
			is_cache_unity=is_cache_unity,
		)


	async def proc_handler(
		self: Throttling,
		handler: None,
		throttling_data: ThrottlingData, counter: str,
		event: Update, event_user: User, data: dict[str, Any],
	) -> Any:
		"""Process handler's update."""
		throttling_data.update_counter(counter)
		# TODO: Mb log handler's name..
		logger.debug('[%s] Handle user: %s', self.__class__.__name__, event_user.username)
		return True


	async def middleware_(
		self: Throttling,
		handler: None,
		event: Update,
		event_user: User,
		bot: Bot,
		data: dict[str, Any],
		throttling_data: ThrottlingData,
	) -> Any:
		# TODO: Apart this stuff..

		is_not_exceed_rate = self.after_handle_count > throttling_data.rate
		is_not_exceed_warnings = self.warnings_count >= throttling_data.sent_warning_count


		if is_not_exceed_rate:
			return await self.proc_handler(
				handler, throttling_data, 'rate', event, event_user,
				data,
			)

		# try send warning
		if is_not_exceed_warnings:
			await self.on_warning(handler, throttling_data, event, event_user, bot, data)
		return True


	async def __call__(
		self: RateLimiter, update: Update, bot: Bot,
	) -> bool:
		event_user: User = update.from_user
		# logging.debug('throttling middleware got new event: type(%s) from %s', type(event), event_user.username)

		event_user_throttling_data: ThrottlingData | None = await self._cache.get(event_user.id)
		throttling_data: ThrottlingData = await self.throttle(
			event_user_throttling_data, event_user, self.period_sec,
		)
		del event_user_throttling_data

		return await self.middleware(None, None, event_user, update, bot, throttling_data)

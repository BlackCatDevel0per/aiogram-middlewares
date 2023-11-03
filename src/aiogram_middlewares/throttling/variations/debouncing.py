from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram_middlewares.throttling.base import ThrottlingAttrsABC

if TYPE_CHECKING:

	from aiogram import Bot
	from aiogram.types import User
	from base import ThrottlingBase

	from .models import ThrottlingData


logger = logging.getLogger(__name__)


class ThrottlingDebouncable(ThrottlingAttrsABC):

	# TODO: Flag too..
	async def throttle(
		self: ThrottlingBase | ThrottlingDebouncable, throttling_data: ThrottlingData | None,
		event_user: User, ttl: int, bot: Bot,
	) -> ThrottlingData:
		"""Antiflood+Debouncing."""
		throttling_data = await self._throttle(throttling_data, event_user, ttl, bot)
		# Reset ttl for item (topping/debouncing)
		await self._cache.expire(event_user.id, ttl)
		return throttling_data

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram_middlewares.rater.base import RaterAttrsABC

if TYPE_CHECKING:

	from aiogram import Bot
	from aiogram.types import User
	from base import RaterBase

	from .models import RateData


logger = logging.getLogger(__name__)


class RateDebouncable(RaterAttrsABC):

	# TODO: Flag too..
	async def trigger(
		self: RaterBase | RateDebouncable, throttling_data: RateData | None,
		event_user: User, ttl: int, bot: Bot,
	) -> RateData:
		"""Debouncing."""
		throttling_data = await self._trigger(throttling_data, event_user, ttl, bot)
		# Reset ttl for item (topping/debouncing)
		await self._cache.expire(event_user.id, ttl)
		return throttling_data

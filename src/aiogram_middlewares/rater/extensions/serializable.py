from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram_middlewares.rater.base import RaterAttrsABC

if TYPE_CHECKING:

	from typing import Any

	from aiogram import Bot
	from aiogram.types import Update, User

	from aiogram_middlewares.rater.types import HandleData, HandleType, RateData


logger = logging.getLogger(__name__)


# TODO: Rearch & make it by decorator on base rater lvls..
class RateSerializable(RaterAttrsABC):


	async def middleware(
		self: RateSerializable,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		rate_data: RateData,
	) -> Any | None:
		"""Handle if custom serializer is available."""
		result = await self._middleware(
			handle, event, event_user, data, bot,
			rate_data,
		)
		# Just update value without changing ttl (if item was removed from cache - catch & do nothing)
		self._cache.uppress(event_user.id, rate_data)
		return result

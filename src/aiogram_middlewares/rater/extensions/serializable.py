from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram_middlewares.rater.base import RaterAttrsABC

if TYPE_CHECKING:

	from typing import Any

	from aiocache.serializers import BaseSerializer
	from aiogram import Bot
	from aiogram.types import Update, User

	from aiogram_middlewares.rater.types import HandleData, HandleType

	from .models import RateData


logger = logging.getLogger(__name__)

# TODO: Conditional inhetirating..


class RaterSerializable(RaterAttrsABC):

	def __init__(
		self: RaterSerializable,
		cache_serializer: BaseSerializer,
	) -> None:
		del self._cache  ##
		self._cache = self._make_cache(self.period_sec, cache_serializer)
		self.choose_cache(RaterSerializable)

	async def middleware(
		self: RaterSerializable,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		rater_data: RateData,
	) -> Any:
		"""Handle if custom serializer is available."""
		##
		result = await self._middleware(
			handle, event, event_user, data, bot, rater_data,
		)
		# Just update value without changing ttl
		# P.S. Why aiocache's api doesn't has separate func for it?
		# But `SENTINEL` well solution (but value stores without ttl aka FOREVER!) =)
		await self._cache.update(event_user.id, rater_data)
		return result

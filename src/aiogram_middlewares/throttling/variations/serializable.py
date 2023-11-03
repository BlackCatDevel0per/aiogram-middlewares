from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiocache.serializers import PickleSerializer

from aiogram_middlewares.throttling.base import ThrottlingAttrsABC

if TYPE_CHECKING:

	from typing import Any

	from aiocache.serializers import BaseSerializer
	from aiogram import Bot
	from aiogram.types import Update, User

	from aiogram_middlewares.throttling.types import HandleData, HandleType

	from .models import ThrottlingData


logger = logging.getLogger(__name__)

# TODO: Conditional inhetirating..


class ThrottlingSerializable(ThrottlingAttrsABC):

	def __init__(
		self: ThrottlingSerializable,
		cache_serializer: BaseSerializer = PickleSerializer,
	) -> None:
		del self._cache  ##
		self._cache = self._make_cache(self.period_sec, cache_serializer)
		self.choose_cache(ThrottlingSerializable)

	async def middleware(
		self: ThrottlingSerializable,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		throttling_data: ThrottlingData,
	) -> Any:
		"""Handle if custom serializer is available."""
		##
		result = await self._middleware(
			handle, event, event_user, data, bot, throttling_data,
		)
		# Just update value without changing ttl
		# P.S. Why aiocache's api doesn't has separate func for it?
		# But `SENTINEL` well solution (but value stores without ttl aka FOREVER!) =)
		await self._cache.update(event_user.id, throttling_data)
		return result

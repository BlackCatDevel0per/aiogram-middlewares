from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import BaseMiddleware

from .base import RaterAttrsABC
from .rater import assemble_rater

if TYPE_CHECKING:
	from typing import Any

	from aiogram import Bot
	from aiogram.types import Update, User

	from aiogram_middlewares.types import HandleData, HandleType

	from .models import RateData


logger = logging.getLogger(__name__)


@assemble_rater
class RateMiddleware(RaterAttrsABC, BaseMiddleware):
	"""Rater middleware (usually for outer usage)."""

	async def __call__(
		self: RateMiddleware,
		handle: HandleType,
		event: Update,
		data: HandleData,
	) -> Any:
		"""Callable for routers/dispatchers."""
		event_user: User = data['event_from_user']
		bot: Bot = data['bot']

		event_user_throttling_data: RateData | None = self._cache.get(event_user.id)
		throttling_data: RateData = await self.trigger(
			event_user_throttling_data, event_user, self.period_sec, bot,
		)
		del event_user_throttling_data

		return await self.middleware(handle, event, event_user, data, bot, throttling_data)

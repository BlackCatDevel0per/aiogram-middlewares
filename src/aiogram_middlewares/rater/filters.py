from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram.filters import Filter

from .base import RaterAttrsABC
from .rater import assemble_rater

if TYPE_CHECKING:
	from typing import Any, Awaitable, Callable, Dict

	from aiogram import Bot
	from aiogram.types import Update, User

	from .models import RateData
	from .types import RateDataCounterAttrType

	ThrottleFilterMiddleware = Callable[
		[
			None,
			None, User, Dict[str, Any], Bot, RateData,
		], Awaitable[bool],
	]
	##Update


logger = logging.getLogger(__name__)


# TODO: Rename..
# TODO: Review..
@assemble_rater
class RateLimiter(RaterAttrsABC, Filter):
	middleware: ThrottleFilterMiddleware
	_middleware: ThrottleFilterMiddleware
	# Limits should be greater than in middleware.. (For handle times too!)


	async def proc_handle(
		self: RateLimiter,
		handle: None,  # type: ignore  # noqa: ARG002
		throttling_data: RateData,
		event: Update, event_user: User, data: dict[str, Any],  # noqa: ARG002
	) -> bool:
		#
		"""Process handle's update."""
		throttling_data.rate += 1
		# TODO: Mb log handle's name..
		logger.debug(
			'[%s] Handle user (proc): %s',
			self.__class__.__name__, event_user.username,
		)
		return True


	async def __call__(
		self: RateLimiter,
		update: Update,
		bot: Bot,
	) -> bool:
		event_user: User = update.from_user

		event_user_throttling_data: RateData | None = await self._cache.get(event_user.id)
		throttling_data: RateData = await self.trigger(
			event_user_throttling_data, event_user, self.period_sec, bot,  # FIXME: Args..
		)
		del event_user_throttling_data

		return await self.middleware(None, None, event_user, update, bot, throttling_data)

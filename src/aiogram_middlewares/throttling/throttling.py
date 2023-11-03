from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiocache.serializers import NullSerializer
from aiogram import BaseMiddleware

from .base import ThrottlingBase
from .variations import (
	ThrottlingDebouncable,
	ThrottlingNotifyCalmed,
	ThrottlingNotifyCC,
	ThrottlingNotifyCooldown,
	ThrottlingSerializable,
)

if TYPE_CHECKING:
	from typing import Any

	from aiocache.serializers import BaseSerializer
	from aiogram import Bot
	from aiogram.types import Update, User
	from pydantic.types import PositiveInt

	from aiogram_middlewares.types import HandleData, HandleType

	from .models import ThrottlingData


logger = logging.getLogger(__name__)

# TODO: Check per-second spam & message spam..
# TODO: Update README.. & mb aiogram2 support..

# TODO: Add throttling
# TODO: Add options to choose between antiflood & throttling
# TODO: Test & optimize =)

# TODO: Mb add debouncing) (topping? XD)
# TODO: Mb role filtering middleare.. (In aiogram2 is useless..)

# TODO: Mb add action on calmdown & after calm


class SelfAssemble:

	# TODO: Move to __new__ in other class..
	def __init__(
		self, *,
		period_sec: PositiveInt = 3, after_handle_count: PositiveInt = 1,
		warnings_count: PositiveInt = 2,
		cache_serializer: BaseSerializer = NullSerializer,

		cooldown_message: str | None = 'Calm down!',
		calmed_message: str | None = 'You can chat now',

		topping_up: bool = True,  # noqa: ARG002
		is_cache_unity: bool = False,  # Because will throttle twice with filters cache.
	):
		mro = self.__class__.__mro__
		ThrottlingBase.__init__(
			self,
			period_sec=period_sec, after_handle_count=after_handle_count,
			is_cache_unity=is_cache_unity,
		)
		if ThrottlingSerializable in mro:
			ThrottlingSerializable.__init__(
				self,
				cache_serializer=cache_serializer,
			)

		if ThrottlingDebouncable in mro:
			ThrottlingDebouncable.__init__(self)

		if ThrottlingNotifyCC in mro:
			ThrottlingNotifyCC.__init__(
				self,
				cooldown_message=cooldown_message,
				calmed_message=calmed_message,
				warnings_count=warnings_count,
			)
		##
		elif ThrottlingNotifyCooldown in mro:
			ThrottlingNotifyCooldown.__init__(
				self,
				cooldown_message=cooldown_message,
				warnings_count=warnings_count,
			)
		elif ThrottlingNotifyCalmed in mro:
			ThrottlingNotifyCalmed.__init__(
				self,
				calmed_message=calmed_message,
				warnings_count=warnings_count,
			)


# Assemble throttling
class Throttling:

	def __new__(
		cls: type, **kwargs: Any,  #~
	):
		_NO_SET = object()
		# TODO: More docstrings!!!
		# TODO: Cache autocleaner schedule (if during work had network glitch or etc.)
		# TODO: Mb rename topping to debouncing..
		bases: list[type] = [SelfAssemble]
		# FIXME: Recheck! & queuing..
		# FIXME: warnings_count
		if kwargs.get('cooldown_message', _NO_SET) is not None and \
			kwargs.get('calmed_message', _NO_SET) is not None:
			bases.append(ThrottlingNotifyCC)
		##
		elif kwargs.get('cooldown_message', _NO_SET) is not None:
			bases.append(ThrottlingNotifyCooldown)
		elif kwargs.get('calmed_message', _NO_SET) is not None:
			bases.append(ThrottlingNotifyCalmed)

		if kwargs.pop('topping_up', _NO_SET):
			bases.append(ThrottlingDebouncable)

		if not isinstance(kwargs.get('cache_serializer'), (NullSerializer, type(None))):
			bases.append(ThrottlingSerializable)
		bases.append(ThrottlingBase)

		print(bases)
		bases.append(ThrottlingMiddleware)  # FIXME: Don't crutch plz..
		obj = type('Throttling', tuple(bases), {})
		return obj(**kwargs)


class ThrottlingMiddleware(BaseMiddleware):
	"""Throttling middleware (usually for outer usage)."""

	async def __call__(
		self: ThrottlingMiddleware,
		handle: HandleType,
		event: Update,
		data: HandleData,
	) -> Any:
		"""Callable for routers/dispatchers."""
		event_user: User = data['event_from_user']
		bot: Bot = data['bot']

		event_user_throttling_data: ThrottlingData | None = await self._cache.get(event_user.id)
		throttling_data: ThrottlingData = await self.throttle(
			event_user_throttling_data, event_user, self.period_sec, bot,
		)
		del event_user_throttling_data

		return await self.middleware(handle, event, event_user, data, bot, throttling_data)

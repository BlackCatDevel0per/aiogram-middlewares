from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING

from aiocache.serializers import NullSerializer
from aiogram import BaseMiddleware

from .base import RaterAttrsABC, RaterBase
from .extensions import (
	RateDebouncable,
	RateNotifyCalmed,
	RateNotifyCC,
	RateNotifyCooldown,
	RaterSerializable,
)

if TYPE_CHECKING:
	from typing import Any

	from aiocache.serializers import BaseSerializer
	from aiogram import Bot
	from aiogram.types import Update, User
	from pydantic.types import PositiveInt

	from aiogram_middlewares.types import HandleData, HandleType

	from .models import RateData


logger = logging.getLogger(__name__)

# TODO: Check per-second spam & message spam..
# TODO: Update README.. & mb aiogram2 support..

# TODO: Add throttling
# TODO: Add options to choose between antiflood & throttling
# TODO: Test & optimize =)

# TODO: Mb add debouncing) (topping? XD)
# TODO: Mb role filtering middleare.. (In aiogram2 is useless..)

# TODO: Mb add action on calmdown & after calm


class AssembleInit:

	# TODO: Move to __new__ in other classes..
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
		RaterBase.__init__(
			self,
			period_sec=period_sec, after_handle_count=after_handle_count,
			is_cache_unity=is_cache_unity,
		)
		if RaterSerializable in mro:
			RaterSerializable.__init__(
				self,
				cache_serializer=cache_serializer,
			)

		if RateDebouncable in mro:
			RateDebouncable.__init__(self)

		if RateNotifyCC in mro:
			RateNotifyCC.__init__(
				self,
				cooldown_message=cooldown_message,
				calmed_message=calmed_message,
				warnings_count=warnings_count,
			)
		##
		elif RateNotifyCooldown in mro:
			logger.debug(
				'Calmed notify disabled for `%s` at `%s`',
				self.__class__.__name__, hex(id(self.__class__.__name__)),
			)

			RateNotifyCooldown.__init__(
				self,
				cooldown_message=cooldown_message,
				warnings_count=warnings_count,
			)
		elif RateNotifyCalmed in mro:
			logger.debug(
				'Cooldown notify disabled for `%s` at `%s`',
				self.__class__.__name__, hex(id(self.__class__.__name__)),
			)

			RateNotifyCalmed.__init__(
				self,
				calmed_message=calmed_message,
			)


# Assemble throttling
class RaterAssembler:

	def __new__(
		cls: type, **kwargs: Any,  #~
	):
		_NO_SET = object()
		# TODO: More docstrings!!!
		# TODO: Cache autocleaner schedule (if during work had network glitch or etc.)
		# TODO: Mb rename topping to debouncing..
		bound = kwargs.pop('bound')
		if not bound:
			msg = "Expected class, got '%s'"
			raise ValueError(msg % type(bound).__name__)
		logger.debug('Assembling <%s> Args: %s', bound.__name__, str(kwargs))
		bases: list[type] = [bound, AssembleInit]

		if not isinstance(kwargs.get('cache_serializer'), (NullSerializer, type(None))):
			bases.append(RaterSerializable)

		# FIXME: Recheck! & queuing..
		# FIXME: warnings_count
		if kwargs.get('cooldown_message', _NO_SET) is not None and \
			kwargs.get('calmed_message', _NO_SET) is not None:
			bases.append(RateNotifyCC)
		##
		elif kwargs.get('cooldown_message', _NO_SET) is not None:
			bases.append(RateNotifyCooldown)
		elif kwargs.get('calmed_message', _NO_SET) is not None:
			bases.append(RateNotifyCalmed)

		if kwargs.pop('topping_up', _NO_SET):
			bases.append(RateDebouncable)
		bases.append(RaterBase)

		_bases: tuple[type, ...] = tuple(bases)
		del bases

		# Check duplicates
		if len(_bases) != len(set(_bases)) and not kwargs.pop('skip_dupes'):
			msg = 'MRO has duplicates!'
			raise TypeError(msg)

		logger.debug(
			'MRO <%s>: %s',
			bound.__name__,
			f"[{', '.join(c.__name__ for c in _bases)}]",
		)
		obj = type(bound.__name__, _bases, {})
		return obj(**kwargs)


# Pass class
def assemble_rater(bound: object, **kwargs):
	return partial(RaterAssembler, bound=bound, **kwargs)


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

		event_user_throttling_data: RateData | None = await self._cache.get(event_user.id)
		throttling_data: RateData = await self.trigger(
			event_user_throttling_data, event_user, self.period_sec, bot,
		)
		del event_user_throttling_data

		return await self.middleware(handle, event, event_user, data, bot, throttling_data)

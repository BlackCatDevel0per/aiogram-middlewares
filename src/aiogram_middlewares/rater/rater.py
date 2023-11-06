from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING

from aiogram import BaseMiddleware

from .base import RaterAttrsABC, RaterBase
from .extensions import (
	RateDebouncable,
	RateNotifyBase,
	RateNotifyCalmed,
	RateNotifyCC,
	RateNotifyCooldown,
	RateSerializable,
	RateThrottleBase,
	RateThrottleNotifyBase,
)

if TYPE_CHECKING:
	from asyncio import AbstractEventLoop
	from typing import Any

	from aiogram import Bot
	from aiogram.types import Update, User
	from pydantic.types import PositiveInt

	from aiogram_middlewares.types import HandleData, HandleType
	from aiogram_middlewares.utils import BaseSerializer

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
		data_serializer: BaseSerializer | None = None,

		cooldown_message: str | None = 'Calm down!',
		calmed_message: str | None = 'You can chat now',

		topping_up: bool = True,  # noqa: ARG002
		is_cache_unity: bool = False,  # Because will throttle twice with filters cache.
		loop: AbstractEventLoop | None = None,
	) -> None:
		mro = self.__class__.__mro__
		RaterBase.__init__(
			self,
			period_sec=period_sec, after_handle_count=after_handle_count,
			data_serializer=data_serializer,
			is_cache_unity=is_cache_unity,
			loop=loop,
		)

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


def make_class_on(
	name: str | None = None, bases: tuple[type, ...] = (), dt: dict[str, Any] = {}
) -> type:
	"""Wrap type func for dynamically making class with inheritance."""
	if not name:
		name = bases[0].__name__
	return type(name, bases, dt)


# Assemble throttling
class RaterAssembler:

	# TODO: Mb cache & move this stuff..
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

		throttling_mode: bool = kwargs.pop('throttling_mode', False)
		rnb = RateNotifyBase if not throttling_mode else RateThrottleNotifyBase
		log__is_throttle_notify = lambda: logger.debug(  # noqa: E731
			'Throttling mode enabled, notifications will based on `%s`',
			RateThrottleNotifyBase.__name__,
		)

		if kwargs.get('data_serializer', _NO_SET) is not None:
			bases.append(RateSerializable)

		# FIXME: Recheck! & queuing..
		# FIXME: warnings_count
		if kwargs.get('cooldown_message', _NO_SET) is not None and \
			kwargs.get('calmed_message', _NO_SET) is not None:
			# TODO: Make func/meta for this stuff..
			rncc = make_class_on(bases=(RateNotifyCC, rnb))
			log__is_throttle_notify()
			bases.append(rncc)
		##
		elif kwargs.get('cooldown_message', _NO_SET) is not None:
			rnc = make_class_on(bases=(RateNotifyCooldown, rnb))
			log__is_throttle_notify()
			bases.append(rnc)
		elif kwargs.get('calmed_message', _NO_SET) is not None:
			rncd = make_class_on(bases=(RateNotifyCalmed, rnb))
			log__is_throttle_notify()
			bases.append(rncd)

		elif throttling_mode:
			logger.debug(
				'Throttling mode enabled, middleware will based on %s',
				RateThrottleBase.__name__,
			)
			bases.append(RateThrottleBase)

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
		obj = make_class_on(bases=_bases)
		return obj(**kwargs)


# Pass class
# TODO: Hints..
def assemble_rater(bound: object, **kwargs: Any) -> partial[RaterAssembler]:
	return partial(RaterAssembler, bound=bound, **kwargs)

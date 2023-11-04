from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from inspect import signature as inspect_signature
from typing import TYPE_CHECKING

from aiocache import Cache
from aiocache.serializers import NullSerializer

from aiogram_middlewares.caches import AdvancedSimpleMemoryCache

from .models import ThrottlingData

if TYPE_CHECKING:
	from typing import Any, Callable, TypeVar

	from aiocache.serializers import BaseSerializer
	from aiogram import Bot
	from aiogram.types import Update, User
	from pydantic.types import PositiveInt

	from .types import (
		_TD,
		HandleType,
		_BaseThrottleMethod,
		_ProcHandleMethod,
		_ThrottleMiddlewareMethod,
	)

	##
	_TI = TypeVar('_TI', bound=type)


logger = logging.getLogger(__name__)


class ThrottlingAttrsABC(ABC):
	_cache: AdvancedSimpleMemoryCache
	period_sec: PositiveInt
	after_handle_count: PositiveInt

	is_cache_unity: bool


	##
	_throttle: _BaseThrottleMethod
	proc_handle: _ProcHandleMethod

	# For serializer
	_middleware: _ThrottleMiddlewareMethod
	choose_cache: Callable[[_TI], ThrottlingBase]
	_make_cache: Callable[[int, BaseSerializer], AdvancedSimpleMemoryCache]


# FIXME: Hints.. Annotations clses..
class ThrottlingABC(ThrottlingAttrsABC):

	@abstractmethod
	async def throttle(
		self: ThrottlingABC, throttling_data: _TD | None,
		event_user: User, ttl: int, bot: Bot,
	) -> ThrottlingData | _TD:
		raise NotImplementedError
		return throttling_data or ThrottlingData(rate=0, sent_warning_count=0)


	@abstractmethod
	async def middleware(
		self: ThrottlingABC,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: dict[str, Any],
		bot: Bot,
		throttling_data: ThrottlingData,
	) -> Any:
		raise NotImplementedError


class ThrottlingBase(ThrottlingABC):

	_cache: AdvancedSimpleMemoryCache = None  # type: ignore

	def __init__(
		self: ThrottlingBase,
		period_sec: PositiveInt, after_handle_count: PositiveInt, *,

		is_cache_unity: bool,  # Because will throttle twice with filters cache.
	) -> None:
		# TODO: More docstrings!!!
		# TODO: Cache autocleaner schedule (if during work had network glitch or etc.)
		# TODO: Mb rename topping to debouncing..
		assert period_sec >= 1, '`period` must be positive!'
		assert after_handle_count >= 1, '`after_handle_count` must be positive!'

		if period_sec < 3:  # noqa: PLR2004
			# recommended to set above 3 for period..
			logger.warning('Recommended to set above 3 for `period_sec` param..')

		self.period_sec = period_sec
		self.after_handle_count = after_handle_count - 1

		# FIXME: Mb move to cache choose part.. 
		self._cache: AdvancedSimpleMemoryCache = self._make_cache(period_sec)  # FIXME: Correct type hint??

		# For unity cache for all instances
		#
		self.__is_cache_unity = is_cache_unity
		self.choose_cache(ThrottlingBase)


	def __str__(self: ThrottlingBase) -> str:
		return repr(self)


	@property
	def _signature(self: ThrottlingBase) -> str:
		sign: tuple[str, ...] = tuple(inspect_signature(self.__init__).parameters)
		attrs: list[str] = [attr for attr in sign if getattr(self, attr, None)]
		del sign
		self_attrs: dict[str, Any] = {attr: getattr(self, attr) for attr in attrs}
		MAX_LEN = 16
		for name, attr in self_attrs.items():
			if isinstance(attr, (str, list)):
				if len(attr) > MAX_LEN:
					attr = attr[:MAX_LEN]
					if isinstance(attr, str):
						attr = f'{attr}...'

				#
				if isinstance(attr, str):
					attr = f"'{attr}'" if "'" not in attr else f'"{attr}"'

				self_attrs[name] = attr

		args: str = ', '.join(f'{name}={attr}' for name, attr in self_attrs.items())
		del self_attrs
		s = (
			f'{self.__class__.__name__}'
			'('
			f'{args}'
			')'
		)
		del args
		return s

	def __repr__(self: ThrottlingBase) -> str:
		return self._signature


	##
	def _make_cache(
		self: ThrottlingBase, period_sec: int, cache_serializer: BaseSerializer = NullSerializer,
	) -> AdvancedSimpleMemoryCache:
		return Cache(  # FIXME: Correct type hint??
			cache_class=AdvancedSimpleMemoryCache,
			ttl=period_sec,  # FIXME: Arg name..
			# WARNING: If you use disk storage and program will fail,
			# some items could be still store in memory!
			serializer=cache_serializer(),  # TODO: ...
		)


	##
	# Bound to class obj.
	def choose_cache(self: ThrottlingBase, class_: _TI) -> ThrottlingBase:
		# TODO: Better logging..
		if self.__is_cache_unity:
			if class_._cache is None:  # noqa: SLF001
				class_._cache = self._cache  # noqa: SLF001
			del self._cache
			self._cache = class_._cache  # noqa: SLF001
			logger.debug(
				'Using unity cache on address `%s`',
				hex(id(class_._cache)),  # noqa: SLF001
			)
		else:
			logger.debug(
				'Using self cache on address `%s`',
				hex(id(self._cache)),
			)
		return self


	async def throttle(
		self: ThrottlingBase, throttling_data: _TD | None,
		event_user: User, ttl: int, bot: Bot,
	) -> ThrottlingData | _TD:
		return await self._throttle(throttling_data, event_user, ttl, bot)


	async def _throttle(
		self: ThrottlingBase, throttling_data: _TD | None,
		event_user: User, ttl: int, bot: Bot,  # noqa: ARG002
	) -> ThrottlingData | _TD:
		"""Antiflood.."""
		# Runs if first throttled, else returns data (counters)
		if not throttling_data:
			logger.debug(
				'[%s] Handle user (begin): %s',
				self.__class__.__name__, event_user.username,
			)
			throttling_data = ThrottlingData(rate=0, sent_warning_count=0)##def
			# Add new item to cache with ttl from initializator.
			# (`Cache.add` does the same, but with checking in cache..)
			# TODO: Mb make custom variant for that..
			# TODO: Clean cache on exceptions.. (to avoid mutes..)
			await self._cache.set(
				event_user.id, throttling_data,
				ttl,
			)
		return throttling_data


	async def proc_handle(
		self: ThrottlingBase,
		handle: HandleType,
		throttling_data: ThrottlingData, counter: str,
		event: Update, event_user: User, data: dict[str, Any],
	) -> Any:
		"""Process handle's update."""
		throttling_data.update_counter(counter)
		# TODO: Mb log handle's name..
		logger.debug(
			'[%s] Handle user (proc): %s',
			self.__class__.__name__, event_user.username,
		)
		return await handle(event, data)


	async def middleware(
		self: ThrottlingBase,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: dict[str, Any],
		bot: Bot,
		throttling_data: ThrottlingData,
	) -> Any | None:
		return await self._middleware(handle, event, event_user, data, bot, throttling_data)


	async def _middleware(
		self: ThrottlingBase,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: dict[str, Any],
		bot: Bot,
		throttling_data: ThrottlingData,
	) -> Any | None:
		"""Main middleware."""
		# TODO: Mb one more variant(s) for debug..

		# TODO: Data types variants..
		is_not_exceed_rate = self.after_handle_count > throttling_data.rate

		# proc/pass update action (run times from `after_handle_amount`)
		if is_not_exceed_rate:
			return await self.proc_handle(
				handle, throttling_data, 'rate', event, event_user,
				data,
			)

		return None

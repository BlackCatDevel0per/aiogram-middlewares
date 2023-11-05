from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from inspect import signature as inspect_signature
from typing import TYPE_CHECKING

from .caches import LazyMemoryCache, LazyMemoryCacheSerializable
from .models import RateData

if TYPE_CHECKING:
	from typing import Any, Callable, TypeVar

	from aiogram import Bot
	from aiogram.types import Update, User
	from pydantic.types import PositiveInt

	from utils import BaseSerializer

	from .types import (
		_TD,
		HandleType,
		RateDataCounterAttrType,
		_BaseThrottleMethod,
		_ProcHandleMethod,
		_ThrottleMiddlewareMethod,
	)

	##
	_TI = TypeVar('_TI', bound=type)


logger = logging.getLogger(__name__)


class RaterAttrsABC(ABC):
	_cache: LazyMemoryCache
	period_sec: PositiveInt
	after_handle_count: PositiveInt

	is_cache_unity: bool


	##
	_trigger: _BaseThrottleMethod
	proc_handle: _ProcHandleMethod

	# For serializer
	_middleware: _ThrottleMiddlewareMethod
	choose_cache: Callable[[_TI], RaterBase]
	_make_cache: Callable[[int, BaseSerializer], LazyMemoryCache]


# FIXME: Hints.. Annotations clses..
class RaterABC(RaterAttrsABC):

	@abstractmethod
	async def trigger(
		self: RaterABC, rater_data: _TD | None,
		event_user: User, ttl: int, bot: Bot,
	) -> RateData | _TD:
		raise NotImplementedError
		return rater_data or RateData(rate=0, sent_warning_count=0)


	@abstractmethod
	async def middleware(
		self: RaterABC,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: dict[str, Any],
		bot: Bot,
		rater_data: RateData,
	) -> Any:
		raise NotImplementedError


class RaterBase(RaterABC):

	_cache: LazyMemoryCache = None  # type: ignore

	def __init__(
		self: RaterBase,
		period_sec: PositiveInt, after_handle_count: PositiveInt, *,

		is_cache_unity: bool,  # Because will trigger twice with filters cache.
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
		self.after_handle_count = after_handle_count

		# FIXME: Mb move to cache choose part.. 
		self._cache: LazyMemoryCache = self._make_cache(period_sec)

		# For unity cache for all instances
		#
		self.__is_cache_unity = is_cache_unity
		self.choose_cache(RaterBase)


	def __str__(self: RaterBase) -> str:
		return repr(self)


	@property
	def _signature(self: RaterBase) -> str:
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

	def __repr__(self: RaterBase) -> str:
		return self._signature


	##
	def _make_cache(
		self: RaterBase, period_sec: int, data_serializer: BaseSerializer | None = None,
	) -> LazyMemoryCache:
		if data_serializer:
			return LazyMemoryCacheSerializable(
				ttl=period_sec,  # FIXME: Arg name..
				# WARNING: If you use disk storage and program will fail,
				# some items could be still store in memory!
				data_serializer=data_serializer(),  # TODO: ... & move serializers to different place..
			)
		return LazyMemoryCache(
			ttl=period_sec,
		)


	##
	# Bound to class obj.
	def choose_cache(self: RaterBase, class_: _TI) -> RaterBase:
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


	async def trigger(
		self: RaterBase, rater_data: _TD | None,
		event_user: User, ttl: int, bot: Bot,
	) -> RateData | _TD:
		return await self._trigger(rater_data, event_user, ttl, bot)


	async def _trigger(
		self: RaterBase, rater_data: _TD | None,
		event_user: User, ttl: int, bot: Bot,  # noqa: ARG002
	) -> RateData | _TD:
		"""Antiflood.."""
		# Runs at first trigger to create entity, else returns data (counters)
		if not rater_data:
			logger.debug(
				'[%s] Handle user (begin): %s',
				self.__class__.__name__, event_user.username,
			)
			rater_data = RateData(rate=0, sent_warning_count=0)##def
			# Add new item to cache with ttl from initializator.
			# (`Cache.add` does the same, but with checking in cache..)
			# TODO: Mb make custom variant for that..
			# TODO: Clean cache on exceptions.. (to avoid mutes..)
			self._cache.set(
				event_user.id, rater_data,
				ttl,
			)
		return rater_data


	async def proc_handle(
		self: RaterBase,
		handle: HandleType,
		rater_data: RateData, counter: RateDataCounterAttrType,
		event: Update, event_user: User, data: dict[str, Any],
	) -> Any:
		"""Process handle's update."""
		rater_data.update_counter(counter)
		# TODO: Mb log handle's name..
		logger.debug(
			'[%s] Handle user (proc): %s',
			self.__class__.__name__, event_user.username,
		)
		return await handle(event, data)


	# For front stuff
	async def middleware(
		self: RaterBase,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: dict[str, Any],
		bot: Bot,
		rater_data: RateData,
	) -> Any | None:
		return await self._middleware(handle, event, event_user, data, bot, rater_data)


	async def _middleware(
		self: RaterBase,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: dict[str, Any],
		bot: Bot,
		rater_data: RateData,
	) -> Any | None:
		"""Main middleware."""
		# TODO: Mb one more variant(s) for debug..

		# TODO: Data types variants..
		is_not_exceed_rate = self.after_handle_count > rater_data.rate

		# proc/pass update action (run times from `after_handle_amount`)
		if is_not_exceed_rate:
			# count up rate & proc
			# FIXME: Rename..
			return await self.proc_handle(
				handle, rater_data, 'rate', event, event_user,
				data,
			)

		return None

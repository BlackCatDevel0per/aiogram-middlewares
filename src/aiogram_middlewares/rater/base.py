from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from inspect import signature as inspect_signature
from typing import TYPE_CHECKING

from .caches import LazyMemoryCache, LazyMemoryCacheSerializable
from .models import RateData

if TYPE_CHECKING:
	from asyncio import AbstractEventLoop
	from typing import Any, Callable, TypeVar

	from aiogram import Bot
	from aiogram.types import Update, User
	from pydantic.types import PositiveInt

	from utils import BaseSerializer

	from .types import (
		_RD,
		HandleData,
		HandleType,
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

	_loop: AbstractEventLoop


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
		self: RaterABC, rate_data: _RD | None,
		event_user: User, ttl: int, bot: Bot,
	) -> RateData | _RD:
		raise NotImplementedError
		return rate_data or RateData()


	@abstractmethod
	async def middleware(
		self: RaterABC,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		rate_data: RateData,
	) -> Any:
		raise NotImplementedError


class RaterBase(RaterABC):

	_cache: LazyMemoryCache = None  # type: ignore

	def __init__(
		self: RaterBase,
		period_sec: PositiveInt, after_handle_count: PositiveInt, *,

		data_serializer: BaseSerializer | None = None,
		is_cache_unity: bool,  # Because will trigger twice with filters cache.

		loop: AbstractEventLoop | None = None,
	) -> None:
		# TODO: More docstrings!!!
		# TODO: Cache autocleaner schedule (if during work had network glitch or etc.)
		# TODO: Mb rename topping to debounc(e/ing)..
		if period_sec < 1:
			msg = f'`period` must be positive, `{period_sec=}`'
			raise ValueError(msg)

		if after_handle_count < 1:
			msg = f'`after_handle_count` must be positive, `{after_handle_count=}`'
			raise ValueError(msg)

		##
		if period_sec < 3:  # noqa: PLR2004
			# recommended to set above 3 for period..
			logger.warning('Recommended to set above 3 for `period_sec` param..')

		self.period_sec = period_sec
		self.after_handle_count = after_handle_count

		# FIXME: Mb move to cache choose part.. 
		self._cache: LazyMemoryCache = self._make_cache(period_sec, data_serializer)

		# For unity cache for all instances
		#
		self.__is_cache_unity = is_cache_unity
		self._loop = loop##
		self.choose_cache(RaterBase)


	def __str__(self: RaterBase) -> str:
		return repr(self)


	@property
	def _signature(self: RaterBase) -> str:
		sign: tuple[str, ...] = tuple(inspect_signature(self.__init__).parameters)
		attrs: list[str] = [attr for attr in sign if getattr(self, attr, None)]
		del sign
		self_attrs: HandleData = {attr: getattr(self, attr) for attr in attrs}
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
		self: RaterBase, rate_data: _RD | None,
		event_user: User, ttl: int, bot: Bot,
	) -> RateData | _RD:
		return await self._trigger(rate_data, event_user, ttl, bot)


	# TODO: Move to another object to avoid duplicating..
	async def _trigger(
		self: RaterBase, rate_data: _RD | None,
		event_user: User, ttl: int, bot: Bot,  # noqa: ARG002
	) -> RateData | _RD:
		"""Run at first trigger to create entity, else returns data (usually counters)."""
		if rate_data or self._cache.has_key(event_user.id):
			assert rate_data is not None  # plug for linter
			return rate_data

		logger.debug(
			'[%s] Trigger user (begin): %s',
			self.__class__.__name__, event_user.username,
		)

		rate_data = RateData()
		# TODO: Mb make custom variant for that..
		# TODO: Clean cache on exceptions.. (to avoid mutes..)
		# Add new item to cache with ttl from initializator.
		# (`Cache.add` does the same, but with checking in cache..)
		self._cache.set(
			event_user.id, rate_data,
			ttl=ttl,
		)

		assert rate_data is not None  # plug for linter
		return rate_data


	async def proc_handle(
		self: RaterBase,
		handle: HandleType,
		rate_data: RateData,
		event: Update, event_user: User, data: HandleData,
	) -> Any:
		"""Process handle's update."""
		rate_data.rate += 1
		# TODO: Mb log handle's name..
		logger.debug(
			'[%s] Handle user (proc): %s',
			self.__class__.__name__, event_user.username,  # FIXME: Log this stuff by hash..
		)
		return await handle(event, data)


	# For front stuff
	async def middleware(
		self: RaterBase,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		rate_data: RateData,
	) -> Any | None:
		return await self._middleware(handle, event, event_user, data, bot, rate_data)


	async def _middleware(
		self: RaterBase,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		rate_data: RateData,
	) -> Any | None:
		"""Main middleware."""
		# TODO: Mb one more variant(s) for debug..

		# TODO: Data types variants..
		is_not_exceed_rate = self.after_handle_count > rate_data.rate

		# proc/pass update action (run times from `after_handle_amount`)
		if is_not_exceed_rate:
			# count up rate & proc
			# FIXME: Rename..
			return await self.proc_handle(
				handle, rate_data, event, event_user,
				data,
			)

		return None

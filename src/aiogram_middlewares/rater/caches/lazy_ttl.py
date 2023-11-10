from __future__ import annotations

import asyncio
from contextlib import suppress as exception_suppress
from time import perf_counter
from typing import TYPE_CHECKING

from aiogram_middlewares.utils import BrotliedPickleSerializer, make_dataclass

if TYPE_CHECKING:
	from asyncio import AbstractEventLoop, Task, TimerHandle
	from dataclasses import dataclass as make_dataclass
	from typing import Any, Callable

	from aiogram_middlewares.utils import BaseSerializer

	# TODO: Move types to other place..
	from .rater.types import (
		PluggedAwaitable,
		ttl_type,
	)

	key_obj = Any


@make_dataclass
class CacheItem:
	"""Dataclass for timer with value data."""

	handle: TimerHandle  # Timer for ttl & some actions..
	value: Any = None  # Serializable data
	obj: object = None  # Not serializable field


_NO_ITEM = object()
# TODO: Make some args as objects..
# TODO: Add set/update method without ttl for things like throttle?


class LazyMemoryCache:
	"""Async wrapper around dict operations & event loop timers to use it as a ttl cache."""

	def __init__(
		self: LazyMemoryCache, ttl: ttl_type,
		loop: AbstractEventLoop | None = None,
	) -> None:
		self._cache: dict[Any, CacheItem] = {}
		self._ttl = ttl

		self._loop = loop if loop else asyncio.get_event_loop()


	def _make_handle(
		self: LazyMemoryCache, ttl: ttl_type, callback: Callable[..., Any], *args: Any,
	) -> TimerHandle:
		"""Wrap around asyncio event loop's `call_later` method."""
		return self._loop.call_later(ttl, callback, *args)


	def _make_handle_delete(self: LazyMemoryCache, key: key_obj, ttl: ttl_type) -> TimerHandle:
		return self._make_handle(ttl, self.delete, key)


	def set(
		self: LazyMemoryCache,
		key: key_obj, value: Any, obj: object = None,
		ttl: ttl_type = 10,
	) -> bool:
		# ttl must not be zero!
		# Not cancels old item handle!
		handle: TimerHandle = self._make_handle_delete(key, ttl)
		item = CacheItem(value=value, handle=handle, obj=obj)
		self._cache[key] = item
		return True


	def get_item(self: LazyMemoryCache, key: key_obj, default: Any = None) -> Any | None:
		return self._cache.get(key, CacheItem) or default


	def get(self: LazyMemoryCache, key: key_obj, default: Any = None) -> Any | None:
		return self._cache.get(key, CacheItem).value or default


	def get_obj(self: LazyMemoryCache, key: key_obj, default: Any = None) -> Any | None:
		return self._cache.get(key, CacheItem).obj or default


	# unused..
	def store(
		self: LazyMemoryCache,
		key: key_obj, value: Any,
	) -> bool:
		return self.set(key, value, self._ttl)


	# TODO: Mb add obj arg.. (don't forget to pass arg into serializable variant too..)
	def update(
		self: LazyMemoryCache, key: key_obj, value: Any,
	) -> bool:
		# Doesn't cancels handler task =)
		self._cache[key].value = value
		return True


	def uppress(
		self: LazyMemoryCache, key: key_obj, value: Any,
	) -> bool:
		"""Like update, but ignore KeyError exception."""
		with exception_suppress(KeyError):
			return self.update(key, value)
		return False


	# unused..
	def upsert(
		self: LazyMemoryCache, key: key_obj, value: Any,
		ttl: ttl_type = 10,
	) -> bool:
		if key not in self._cache:
			return self.set(key, value, ttl or self._ttl)
		return self.update(key, value)


	def delete(self: LazyMemoryCache, key: key_obj) -> bool:
		# Not cancels handle
		del self._cache[key]
		return True


	def expire(
		self: LazyMemoryCache,
		key: key_obj,
		ttl: ttl_type,
	) -> bool:
		"""Use if you sure item still in cache (recomment with cache cleanup scheduling)."""
		item = self._cache[key]
		item.handle.cancel()
		item.handle = self._make_handle_delete(key, ttl)
		return True


	async def _delete_with_subcall(
		self: LazyMemoryCache, key: key_obj, plugged_awaitable: PluggedAwaitable,
	) -> bool:
		status = self.delete(key)
		await plugged_awaitable()
		return status


	def wrap_delete_with_subcall(
		self: LazyMemoryCache, key: key_obj, plugged_awaitable: PluggedAwaitable,
	) -> Callable[[], Task[bool]]:
		return lambda: asyncio.ensure_future(self._delete_with_subcall(key, plugged_awaitable))


	@staticmethod
	def calc_remaining_of(handle: TimerHandle) -> float:
		return handle.when() - perf_counter()


	def cancel_handle(
		self: LazyMemoryCache, key: key_obj,
	) -> CacheItem:
		item = self._cache[key]
		item.handle.cancel()
		# del item.handle
		return item


	def replace_handle_with_subcallback(
		self: LazyMemoryCache, key: key_obj, plugged_awaitable: PluggedAwaitable,
		ttl: float | int,
	) -> bool:
		item = self.cancel_handle(key)

		item.handle = self._loop.call_later(
			ttl,
			self.wrap_delete_with_subcall(key, plugged_awaitable),
		)
		return True


	def set_handle_subcallback(
		self: LazyMemoryCache, key: key_obj, plugged_awaitable: PluggedAwaitable,
	) -> bool:
		item = self.cancel_handle(key)

		# NOTE: Hmm..
		handle_remaining = self.calc_remaining_of(item.handle)

		item.handle = self._make_handle(
			handle_remaining,
			self.wrap_delete_with_subcall(key, plugged_awaitable),
		)

		return True


class LazyMemoryCacheSerializable(LazyMemoryCache):
	"""Lazy cache wrapper to serialize/deserialize value data."""

	def __init__(
		self: LazyMemoryCacheSerializable, ttl: ttl_type,
		loop: AbstractEventLoop | None = None,
		data_serializer: BaseSerializer | None = None,
	) -> None:
		super().__init__(ttl=ttl, loop=loop)
		self._serializer = data_serializer if data_serializer else BrotliedPickleSerializer()


	def set(
		self: LazyMemoryCacheSerializable,
		key: key_obj, value: Any, obj: object = None,
		ttl: ttl_type = 10,
	) -> bool:
		# ttl must not be zero!
		return super().set(key, self._serializer.serialize(value), obj, ttl)


	def update(
		self: LazyMemoryCacheSerializable,
		key: key_obj, value: Any,
	) -> bool:
		# ttl must not be zero!
		return super().update(key, self._serializer.serialize(value))


	def get(self: LazyMemoryCacheSerializable, key: key_obj, default: Any = None) -> Any:
		return self._serializer.deserialize(super().get(key, default))
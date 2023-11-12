from __future__ import annotations

import asyncio
import logging
from contextlib import suppress as exception_suppress
from time import perf_counter
from typing import TYPE_CHECKING

from aiogram_middlewares.utils import BrotliedPickleSerializer, make_dataclass

if TYPE_CHECKING:
	from asyncio import AbstractEventLoop, Task, TimerHandle
	from dataclasses import dataclass as make_dataclass
	from typing import Any, Callable, Literal

	from aiogram_middlewares.utils import BaseSerializer

	# TODO: Move types to other place..
	from .rater.types import (
		PluggedAwaitable,
		ttl_type,
	)

	key_obj = Any
	true = Literal[True]


logger = logging.getLogger(__name__)


class CacheKeyError(KeyError):
	...


@make_dataclass
class CacheItem:
	"""Dataclass for timer with value data."""

	handle: TimerHandle  # Timer for ttl & some actions..
	callback: Callable  # Because TimerHandler._callback is None..
	callback_args: tuple[...] | None = None
	value: Any = None  # Serializable data
	obj: object = None  # Not serializable field


_NO_ITEM = object()
# TODO: Make some args as objects..
# TODO: Add set/update method without ttl for things like throttle?


# TODO: Make subclass & abc for some stuff..
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
		self: LazyMemoryCache, ttl: ttl_type,
		callback: Callable, *args: Any,
	) -> TimerHandle:
		"""Wrap around asyncio event loop's `call_later` method."""
		return self._loop.call_later(ttl, callback, *args)


	def _make_handle_delete(
		self: LazyMemoryCache, key: key_obj, ttl: ttl_type,
	) -> tuple[
		TimerHandle,
		tuple[Callable[[key_obj], true], tuple[key_obj]],
	]:
		return self._make_handle(ttl, self.delete, key), (self.delete, (key,))


	# TODO: Move into dataclass..?
	def _set_item_callback(
		self: LazyMemoryCache,
		item: CacheItem,
		callback: Callable, args: tuple[...] | None,
	) -> None:
		item.callback = callback
		item.callback_args = args


	def set(
		self: LazyMemoryCache,
		key: key_obj, value: Any, obj: object = None,
		ttl: ttl_type = 10,
	) -> true:
		# ttl must not be zero!
		# Not cancels old item handle!
		handle, _callback = self._make_handle_delete(key, ttl)
		# WARNNING: Sometimes `handle_calllback` is None!
		item = CacheItem(
			value=value, handle=handle,
			callback=_callback[0], callback_args=_callback[1],
			obj=obj,
		)
		self._cache[key] = item
		return True


	def has_key(self: LazyMemoryCache, key: key_obj) -> bool:
		"""Check if the cache has such a key."""
		return key in self._cache


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
	) -> true:
		"""Set with default ttl."""
		return self.set(key, value, self._ttl)


	# TODO: Mb add obj arg.. (don't forget to pass arg into serializable variant too..)
	def update(
		self: LazyMemoryCache, key: key_obj, value: Any,
	) -> true:
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


	def delete(self: LazyMemoryCache, key: key_obj) -> true:
		# Not cancels handle
		del self._cache[key]
		return True


	def expire(
		self: LazyMemoryCache,
		key: key_obj,
		ttl: ttl_type,
	) -> true:
		"""Use if you sure item still in cache (recomment with cache cleanup scheduling)."""
		item: CacheItem = self._cache[key]
		item.handle.cancel()
		# Reuse old callback
		item.handle = self._make_handle(ttl, item.callback, *item.callback_args or ())
		return True


	async def _delete_with_subcall(
		self: LazyMemoryCache, key: key_obj, plugged_awaitable: PluggedAwaitable,
	) -> true:
		status = self.delete(key)
		await plugged_awaitable()
		return status


	def _delete_with_sync_subcall(
		self: LazyMemoryCache, key: key_obj, callback: Callable[[], Any],
	) -> true:
		status = self.delete(key)
		callback()
		return status


	def wrap_delete_with_subcall(
		self: LazyMemoryCache, key: key_obj, plugged_awaitable: PluggedAwaitable,
	) -> Callable[[], Task[bool]]:
		return lambda: asyncio.ensure_future(self._delete_with_subcall(key, plugged_awaitable))


	def wrap_delete_with_sync_subcall(
		self: LazyMemoryCache, key: key_obj, callback_: Callable[[], Any],
	) -> Callable[[], Any]:
		return lambda: self._delete_with_sync_subcall(key, callback_)


	@staticmethod
	def calc_remaining_of(handle: TimerHandle) -> float:
		return handle.when() - perf_counter()


	def cancel_handle(
		self: LazyMemoryCache, key: key_obj,
	) -> CacheItem:
		try:
			item = self._cache[key]
		except KeyError as ke:
			msg = f'Key `{key}` not found or removed from cache!'
			raise CacheKeyError(msg) from ke
		item.handle.cancel()
		# del item.handle
		return item


	def replace_handle_with_subcallback(
		self: LazyMemoryCache, key: key_obj, plugged_awaitable: PluggedAwaitable,
		ttl: float | int,
	) -> true:
		item = self.cancel_handle(key)

		item.handle = self._loop.call_later(
			ttl,
			self.wrap_delete_with_subcall(key, plugged_awaitable),
		)
		return True


	def set_handle_subcallback(
		self: LazyMemoryCache, key: key_obj, plugged_awaitable: PluggedAwaitable,
	) -> true:
		item = self.cancel_handle(key)

		# NOTE: Hmm..
		# TODO: Unite to one func..
		handle_remaining = self.calc_remaining_of(item.handle)

		cb = self.wrap_delete_with_subcall(key, plugged_awaitable)

		item.handle = self._make_handle(
			handle_remaining,
			cb,
		)
		self._set_item_callback(item, cb, None)
		#

		return True


	def set_handle_sync_subcallback(
		self: LazyMemoryCache, key: key_obj, callback: Callable[[], Any],
	) -> true:
		item = self.cancel_handle(key)

		# NOTE: Hmm..
		handle_remaining = self.calc_remaining_of(item.handle)

		cb = self.wrap_delete_with_sync_subcall(key, callback)

		item.handle = self._make_handle(
			handle_remaining,
			cb,
		)
		self._set_item_callback(item, cb, None)

		return True


	# TODO: Set what it wraps.. (to avoid things like `method.<locals>.<lambda>`)
	# TODO: Docstrings & mb rename this method..?
	def replace_handle_sync_callback(
		self: LazyMemoryCache, key: key_obj, callback: Callable[[key_obj, CacheItem], Any],
	) -> true:
		item = self.cancel_handle(key)

		# NOTE: Hmm..
		handle_remaining = self.calc_remaining_of(item.handle)

		# TODO: Mb some optional args2callback..
		cb = lambda: callback(key, item)  # noqa: E731

		# TODO: Add func to make handle &
		# TODO: set/update (if the same cb+cb_args) CacheItem's callback+callback_args data
		item.handle = self._make_handle(
			handle_remaining,
			cb,
		)
		self._set_item_callback(item, cb, None)

		return True


	# TODO: Use as decorator..
	def _try_shs(
		self: LazyMemoryCache, func: Callable[[key_obj, PluggedAwaitable], bool],
		key: key_obj, callback: Callable,
	) -> bool:
		try:
			return func(key, callback)  # cls method
		except CacheKeyError:
			logger.warning("Key `%s` doesn't exists.", key)
		except Exception:
			logger.exception('Error on setting handle subcallback')
		return False


	def try_set_handle_subcallback(
		self: LazyMemoryCache, key: key_obj, plugged_awaitable: PluggedAwaitable,
	) -> bool:
		return self._try_shs(self.set_handle_subcallback, key, plugged_awaitable)


	def try_set_handle_sync_subcallback(
		self: LazyMemoryCache, key: key_obj, callback: Callable[[], Any],
	) -> bool:
		return self._try_shs(self.set_handle_sync_subcallback, key, callback)


	def try_replace_handle_sync_callback(
		self: LazyMemoryCache, key: key_obj, callback: Callable[[key_obj, CacheItem], Any],
	) -> bool:
		return self._try_shs(self.replace_handle_sync_callback, key, callback)


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
	) -> true:
		# ttl must not be zero!
		return super().set(key, self._serializer.serialize(value), obj, ttl)


	def update(
		self: LazyMemoryCacheSerializable,
		key: key_obj, value: Any,
	) -> true:
		# ttl must not be zero!
		return super().update(key, self._serializer.serialize(value))


	def get(self: LazyMemoryCacheSerializable, key: key_obj, default: Any = None) -> Any:
		return self._serializer.deserialize(super().get(key, default))

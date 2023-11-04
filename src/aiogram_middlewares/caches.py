from __future__ import annotations

import asyncio
from time import perf_counter
from typing import TYPE_CHECKING

from aiocache import SimpleMemoryCache
from aiocache.base import API, _Conn, logger

if TYPE_CHECKING:
	from typing import Any, Awaitable, Callable

	PluggedAwaitable = Callable[[], Awaitable]


# TODO: Wrappers, other api..

class _ASMCLazyBackend(SimpleMemoryCache):
	async def _update(
		self: _ASMCLazyBackend, key: Any, value: Any,
		_cas_token: object | None = None, _conn: _ASMCLazyBackend | None = None,
	) -> bool | int:
		if _cas_token is not None and _cas_token != self._cache.get(key):
			return 0

		# Doesn't cancels handler task =)

		self._cache[key] = value
		return True


	async def _delete_and_call(
		self: _ASMCLazyBackend, key: Any, plugged_awaitable: PluggedAwaitable,
	) -> int:
		# status = SimpleMemoryCache._SimpleMemoryCache__delete(key)
		status = await self._delete(key)
		await plugged_awaitable()
		return status


	async def _set_sub_handler(
		self: _ASMCLazyBackend, key: Any, plugged_awaitable: PluggedAwaitable,
		ttl: int | None = None,
		_conn: _ASMCLazyBackend | None = None,
	) -> bool | int:
		if key in self._cache:
			handle = self._handlers.pop(key, None)
			handle_remaining = None
			if handle:
				# NOTE: Hmm..
				handle_remaining = handle.when() - perf_counter()
				if handle_remaining:
					handle.cancel()
					# TODO: Get loop method.. (as property)
					loop = asyncio.get_running_loop()
					self._handlers[key] = loop.call_later(
						ttl or handle_remaining,
						lambda: asyncio.create_task(self._delete_and_call(key, plugged_awaitable)),
					)
			return True

		return False

	# Just optimized variant of _expire + _set_sub_handler.. & unused..
	async def _expire_with_sub_handler(
		self: _ASMCLazyBackend, key: Any, plugged_awaitable: PluggedAwaitable,
		ttl: int, _conn: _ASMCLazyBackend | None = None,
	) -> bool:
		if key in self._cache:
			handle = self._handlers.pop(key, None)
			if handle:
				handle.cancel()  # FIXME: Optional use old ttl.. Or add second handler to first..
			if ttl:
				loop = asyncio.get_running_loop()
				# FIXME: Duplication, move to other method..
				self._handlers[key] = loop.call_later(
					ttl,
					lambda: asyncio.create_task(self._delete_and_call(key, plugged_awaitable)),
				)
			return True

		return False


# TODO: Move it to different lib..
class AdvancedSimpleMemoryCache(_ASMCLazyBackend):
	"""Simple Memory Cache, but with some advanced methods."""

	def __init__(self: AdvancedSimpleMemoryCache, **kwargs: Any) -> None:
		"""Init "backend"."""
		super().__init__(**kwargs)

	# TODO: Add lazy expire.. (without checking key in cache & etc.)
	@API.register
	@API.aiocache_enabled(fake_return=True)
	@API.timeout
	@API.plugins
	async def update(
		self: AdvancedSimpleMemoryCache, key: Any, value: Any,
		dumps_fn: Callable[[Any], Any] | None = None,
		namespace: str | None = None,
		_cas_token: object | None = None, _conn: AdvancedSimpleMemoryCache | None = None,
	) -> bool | int:
		"""Store the value by the given key without changing ttl (doesn't cancels delete item task).

		Very useful if you use serializers =)

		:param dumps_fn: callable alternative to use as dumps function
		:param namespace: alternative namespace to use
		:param timeout: int or float in seconds specifying maximum timeout
			for the operations to last
		:returns: True if the value was set
		:raises: :class:`asyncio.TimeoutError` if it lasts more than self.timeout
		"""
		start = perf_counter()
		dumps = dumps_fn or self._serializer.dumps
		ns = namespace if namespace is not None else self.namespace
		ns_key = self.build_key(key, namespace=ns)

		res = await self._update(
			ns_key, dumps(value), _cas_token=_cas_token, _conn=_conn,
		)  # ??

		logger.debug('SET %s %d (%.4f)s', ns_key, True, perf_counter() - start)  # noqa: FBT003
		return res


	@API.register
	@API.aiocache_enabled(fake_return=False)
	@API.timeout
	@API.plugins
	async def set_sub_handler(
		self: AdvancedSimpleMemoryCache, key: Any, plugged_awaitable: PluggedAwaitable,
		ttl: int | None = None,
		namespace: str | None = None, _conn: AdvancedSimpleMemoryCache | None = None,
	) -> bool | int:
		"""Add sub-handler on item deletion from cache.

		:param plugged_awaitable: wrapped awaitable (coroutine-like object)
		:param ttl: int the expiration time in seconds. Due to memcached
			restrictions if you want compatibility use int. In case you
			need milliseconds, redis and memory support float ttls
			(if not passed will use remaining ttl)
		:param dumps_fn: callable alternative to use as dumps function
		:param namespace: alternative namespace to use
		:returns: True if the sub-handler was set
		:raises: :class:`asyncio.TimeoutError` if it lasts more than self.timeout
		"""
		start = perf_counter()
		ns = namespace if namespace is not None else self.namespace
		ns_key = self.build_key(key, namespace=ns)

		ret = await self._set_sub_handler(
			ns_key, plugged_awaitable, ttl=self._get_ttl(ttl),
			_conn=_conn,
		)

		logger.debug('SET %s %d (%.4f)s', ns_key, True, perf_counter() - start)  # noqa: FBT003
		return ret


	# Unused..
	@API.register
	@API.aiocache_enabled(fake_return=False)
	@API.timeout
	@API.plugins
	async def expire_with_sub_handler(
		self: AdvancedSimpleMemoryCache, key: Any, plugged_awaitable: PluggedAwaitable,
		ttl: int,
		namespace: str | None = None, _conn: AdvancedSimpleMemoryCache | None = None,
	) -> bool:
		"""Set the ttl to the given key. By setting it to 0, it will disable it.

		:param key: Any key to expire
		:param plugged_awaitable: wrapped awaitable (coroutine-like object)
		:param ttl: number of seconds for expiration. If 0, ttl is disabled
		:param namespace: alternative namespace to use
		:param timeout: int or float in seconds specifying maximum timeout
			for the operations to last
		:returns: True if set, False if key is not found
		:raises: :class:`asyncio.TimeoutError` if it lasts more than self.timeout
		"""
		start = perf_counter()
		ns = namespace if namespace is not None else self.namespace
		ns_key = self.build_key(key, namespace=ns)
		ret = await self._expire_with_sub_handler(ns_key, plugged_awaitable, ttl, _conn=_conn)
		logger.debug('EXPIRE %s %d (%.4f)s', ns_key, ret, perf_counter() - start)
		return ret


# Bruh
for cmd in API.CMDS:
	setattr(_Conn, cmd.__name__, _Conn._inject_conn(cmd.__name__))  # noqa: SLF001

from __future__ import annotations

import asyncio
from functools import wraps
from time import perf_counter
from typing import TYPE_CHECKING

from aiocache import SimpleMemoryCache
from aiocache.base import API, _Conn, logger

if TYPE_CHECKING:
	from asyncio import TimerHandle
	from typing import Any, Callable

	# TODO: Move types to other place..
	from .rater.types import (
		AsyncHandlable,
		PluggedAwaitable,
		WrappedHandlable,
		_conn_type,
		_status_type,
		opt_ttl,
	)


# TODO: Wrappers, other api..
# TODO: Make some args as objects..

class _ASMCLazyBackend(SimpleMemoryCache):
	async def _update(
		self: _ASMCLazyBackend, key: Any, value: Any,
		_cas_token: object | None = None, _conn: _conn_type = None,
	) -> _status_type:
		if _cas_token is not None and _cas_token != self._cache.get(key):
			return 0

		# Doesn't cancels handler task =)

		self._cache[key] = value
		return True


	async def _delete_with_call(
		self: _ASMCLazyBackend, key: Any, plugged_awaitable: PluggedAwaitable,
	) -> int:
		# status = SimpleMemoryCache._SimpleMemoryCache__delete(key)
		status = await self._delete(key)
		await plugged_awaitable()
		return status


	@staticmethod
	def calc_remaining_of(handle: TimerHandle) -> float:
		return handle.when() - perf_counter()


	# Decorator to avoid handle check duplication (for internal use only)
	def _handle_checks(async_func: AsyncHandlable) -> WrappedHandlable:  # noqa: N805
		@wraps(async_func)
		async def wrapper(
			self: _ASMCLazyBackend,
			key: Any, plugged_awaitable: PluggedAwaitable,
			ttl: opt_ttl = None,
			_conn: _conn_type = None,
		) -> _status_type:
			if key not in self._cache:
				return False

			handle = self._handlers.pop(key, None)
			if not handle:
				return True

			# NOTE: Hmm..
			handle_remaining = self.calc_remaining_of(handle)
			if not handle_remaining:
				return True

			return await async_func(
				self,
				key, plugged_awaitable,
				ttl,
				handle, handle_remaining,
				_conn,
			)
		return wrapper


	def _add_handler_callback(
		self: _ASMCLazyBackend, key: Any, plugged_awaitable: PluggedAwaitable,
		ttl: float | int,
		_conn: _conn_type = None,
	) -> None:
		# TODO: Get loop method.. (as property)
		loop = asyncio.get_running_loop()
		self._handlers[key] = loop.call_later(
			ttl,
			lambda: asyncio.create_task(self._delete_with_call(key, plugged_awaitable)),
		)


	def _set_handler_callback(
		self: _ASMCLazyBackend, key: Any, plugged_awaitable: PluggedAwaitable,
		ttl: float | int, handle: TimerHandle,
		_conn: _conn_type = None,
	) -> None:
		# TODO: Make subhandlers dict..
		# Dirty way..
		handle.cancel()
		return self._add_handler_callback(key, plugged_awaitable, ttl, _conn)


	@_handle_checks
	async def _set_sub_handler(
		self: _ASMCLazyBackend, key: Any, plugged_awaitable: PluggedAwaitable,
		ttl: opt_ttl,
		handle: TimerHandle, handle_remaining: float,
		_conn: _conn_type = None,
	) -> _status_type:
		self._set_handler_callback(key, plugged_awaitable, ttl or handle_remaining, handle, _conn)
		return True


# TODO: Move it to different lib..
class AdvancedSimpleMemoryCache(_ASMCLazyBackend):
	"""Simple Memory Cache, but with some advanced methods."""

	def __init__(self: AdvancedSimpleMemoryCache, **kwargs: Any) -> None:
		"""Init "backend"."""
		super().__init__(**kwargs)

	async def _middle_blink_k(
		self: AdvancedSimpleMemoryCache,
		key: Any,
		namespace: str | None = None,
		_conn: AdvancedSimpleMemoryCache | None = None,
	) -> tuple[float, Any]:
		start = perf_counter()
		ns = namespace if namespace is not None else self.namespace
		ns_key = self.build_key(key, namespace=ns)

		return start, ns_key

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
	) -> _status_type:
		"""Store the value by the given key without changing ttl (doesn't cancels delete item task).

		Very useful if you use serializers =)

		:param dumps_fn: callable alternative to use as dumps function
		:param namespace: alternative namespace to use
		:param timeout: int or float in seconds specifying maximum timeout
			for the operations to last
		:returns: True if the value was set
		:raises: :class:`asyncio.TimeoutError` if it lasts more than self.timeout
		"""
		start, ns_key = await self._middle_blink_k(
			key, namespace, _conn,
		)
		dumps = dumps_fn or self._serializer.dumps

		ret = await self._update(
			ns_key, dumps(value), _cas_token=_cas_token, _conn=_conn,
		)

		logger.debug('SET %s %d (%.4f)s', ns_key, True, perf_counter() - start)  # noqa: FBT003
		return ret


	@API.register
	@API.aiocache_enabled(fake_return=False)
	@API.timeout
	@API.plugins
	async def set_sub_handler(
		self: AdvancedSimpleMemoryCache, key: Any, plugged_awaitable: PluggedAwaitable,
		ttl: opt_ttl = None,
		namespace: str | None = None, _conn: AdvancedSimpleMemoryCache | None = None,
	) -> _status_type:
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
		start, ns_key = await self._middle_blink_k(
			key, namespace, _conn,
		)

		ret = await self._set_sub_handler(  # type: ignore
			ns_key, plugged_awaitable, ttl=self._get_ttl(ttl),
			_conn=_conn,
		)

		logger.debug('SET %s %d (%.4f)s', ns_key, True, perf_counter() - start)  # noqa: FBT003
		return ret


# Bruh
for cmd in API.CMDS:
	setattr(_Conn, cmd.__name__, _Conn._inject_conn(cmd.__name__))  # noqa: SLF001

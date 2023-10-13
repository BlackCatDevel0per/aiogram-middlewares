from __future__ import annotations

from time import monotonic

from aiocache import SimpleMemoryCache
from aiocache.base import API, logger


# TODO: Move it to different lib..
class AdvancedSimpleMemoryCache(SimpleMemoryCache):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)

	# What's `_cas_token` & `_conn`?? (Where they used?)
	async def _update(self: AdvancedSimpleMemoryCache, key: str, value: object, _cas_token=None, _conn=None) -> bool | int:
		if _cas_token is not None and _cas_token != self._cache.get(key):
			return 0

		# Doesn't cancels task in handler =)

		self._cache[key] = value
		return True


	# Do I need changing ttl??
	@API.register
	@API.aiocache_enabled(fake_return=True)
	@API.timeout
	@API.plugins
	async def update(
		self: AdvancedSimpleMemoryCache, key: str, value: object, dumps_fn: Callable[[Any], object] | None = None,
		namespace: str | None = None, _cas_token = None, _conn=None,
	) -> bool:
		"""Store the value in the given key without changing ttl (doesn't cancels remove task if has).

		Very useful if you use serializers =)

		:param dumps_fn: callable alternative to use as dumps function
		:param namespace: str alternative namespace to use
		:param timeout: int or float in seconds specifying maximum timeout
			for the operations to last
		:returns: True if the value was set
		:raises: :class:`asyncio.TimeoutError` if it lasts more than self.timeout
		"""
		start = monotonic()
		dumps = dumps_fn or self._serializer.dumps
		ns = namespace if namespace is not None else self.namespace
		ns_key = self.build_key(key, namespace=ns)

		res: bool = await self._update(
			ns_key, dumps(value), _cas_token=_cas_token, _conn=_conn,
		)  # ??

		logger.debug('SET %s %d (%.4f)s', ns_key, True, monotonic() - start)  # noqa: FBT003
		return res

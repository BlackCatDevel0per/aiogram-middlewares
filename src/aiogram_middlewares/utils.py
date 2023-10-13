from __future__ import annotations

import pickle

import brotli
from aiocache.serializers import BaseSerializer


# TODO: Move it to different lib..
# My brotlidded-pickle serializer UwU
class BrotliedPickleSerializer(BaseSerializer):
	"""Transform data to bytes using pickle.dumps and pickle.loads with brotli compression to retrieve it back."""

	DEFAULT_ENCODING = None

	def __init__(self: BrotliedPickleSerializer, *args, protocol=pickle.DEFAULT_PROTOCOL, **kwargs):
		super().__init__(*args, **kwargs)
		self.protocol = protocol

	def dumps(self: BrotliedPickleSerializer, value: object) -> bytes:
		"""Serialize the received value using ``pickle.dumps`` and compresses using brotli."""
		return brotli.compress(pickle.dumps(value, protocol=self.protocol))

	def loads(self: BrotliedPickleSerializer, value: bytes) -> object:
		"""Decompresses using brotli & deserialize value using ``pickle.loads``."""
		if value is None:
			return None
		return pickle.loads(brotli.decompress(value))  # noqa: S301

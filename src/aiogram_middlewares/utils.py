from __future__ import annotations

import pickle
import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import brotli
from aiocache.serializers import BaseSerializer

if TYPE_CHECKING:
	# Cheat XD
	from dataclasses import dataclass as make_dataclass
	from typing import Any

# TODO: Use from..
# Well..
def make_dataclass(*args: Any, **kwargs: Any):  # noqa: F811
	pyv = (sys.version_info.major, sys.version_info.minor)
	# TODO: More features..
	defs = {
		'slots': (True, (3, 10)),
		'kw_only': (True, (3, 10)),
	}
	for arg, vp in defs.items():
		p = vp[1]
		if arg not in kwargs and pyv[0] >= p[0] and pyv[1] >= p[1]:
			kwargs[arg] = vp[0]
	return dataclass(*args, **kwargs)


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

from __future__ import annotations

import sys
from dataclasses import dataclass
from pickle import DEFAULT_PROTOCOL
from pickle import dumps as pickle_dumps
from pickle import loads as pickle_loads
from typing import TYPE_CHECKING

from aiocache.serializers import BaseSerializer
from brotli import compress as brotli_compress
from brotli import decompress as brotli_decompress

if TYPE_CHECKING:
	# Cheat XD
	from dataclasses import dataclass as make_dataclass
	from typing import Any

# Well..
def make_dataclass(*args: Any, **kwargs: Any):  # noqa: F811,ANN201
	"""Wrap around @dataclass decorator with python version check to pick kwargs."""
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
	"""Transform data to bytes.

	Using pickle.dumps and pickle.loads with brotli compression to retrieve it back
	"""

	DEFAULT_ENCODING = None

	def __init__(
		self: BrotliedPickleSerializer, *args: Any,
		pickle_protocol: int = DEFAULT_PROTOCOL,
		**kwargs: Any
	) -> None:
		super().__init__(*args, **kwargs)
		# TODO: More options..
		self.pickle_protocol = pickle_protocol

	def dumps(self: BrotliedPickleSerializer, value: object) -> bytes:
		"""Serialize the received value using ``pickle.dumps`` and compresses using brotli."""
		return brotli_compress(pickle_dumps(value, protocol=self.pickle_protocol))

	def loads(self: BrotliedPickleSerializer, value: bytes) -> object:
		"""Decompresses using brotli & deserialize value using ``pickle.loads``."""
		if value is None:
			return None
		return pickle_loads(brotli_decompress(value))  # noqa: S301

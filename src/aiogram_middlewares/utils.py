from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pickle import DEFAULT_PROTOCOL
from pickle import dumps as pickle_dumps
from pickle import loads as pickle_loads
from typing import TYPE_CHECKING

from brotli import compress as brotli_compress
from brotli import decompress as brotli_decompress

if TYPE_CHECKING:
	# Cheat XD
	from dataclasses import dataclass as make_dataclass
	from typing import Any

# Well..
def make_dataclass(*args: Any, **kwargs: Any):  # noqa: F811,ANN201
	"""Wrap around @dataclass decorator with python version check to pick kwargs."""
	# TODO: Use `sys.version_info > (3, 10)`
	pyv = (sys.version_info.major, sys.version_info.minor)
	# TODO: More features..
	defs = {
		# 'slots': (True, (3, 10)),  # Glitches.. [ AttributeError: 'member_descriptor' object has no attribute 'locked' ]
		'kw_only': (True, (3, 10)),
	}
	for arg, vp in defs.items():
		p = vp[1]
		if arg not in kwargs and pyv[0] >= p[0] and pyv[1] >= p[1]:
			kwargs[arg] = vp[0]
	return dataclass(*args, **kwargs)


class BaseSerializer(ABC):
	@abstractmethod
	def serialize(self: BaseSerializer, value: object) -> bytes:
		raise NotImplementedError

	@abstractmethod
	def deserialize(self: BaseSerializer, value: bytes | None) -> object:
		raise NotImplementedError


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

	def serialize(self: BrotliedPickleSerializer, value: object) -> bytes:
		"""Serialize the received value using ``pickle.dumps`` and compresses using brotli."""
		return brotli_compress(pickle_dumps(value, protocol=self.pickle_protocol))

	def deserialize(self: BrotliedPickleSerializer, value: bytes | None) -> object:
		"""Decompresses using brotli & deserialize value using ``pickle.loads``."""
		if value is None:
			return None
		return pickle_loads(brotli_decompress(value))  # noqa: S301

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	# Cheat XD
	from dataclasses import dataclass as make_dataclass


# Well..
def make_dataclass(*args, **kwargs):  # noqa: F811
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


@make_dataclass
class ThrottlingData:
	rate: int
	sent_warning_count: int

	def update_counter(self: ThrottlingData, counter: str, count: int = 1) -> None:
		cnt: int = self.__getattribute__(counter)
		self.__setattr__(counter, cnt + count)

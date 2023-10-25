from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram_middlewares.utils import make_dataclass

if TYPE_CHECKING:
	...


@make_dataclass
class ThrottlingData:
	rate: int
	sent_warning_count: int

	def update_counter(self: ThrottlingData, counter: str, count: int = 1) -> None:
		cnt: int = self.__getattribute__(counter)
		self.__setattr__(counter, cnt + count)

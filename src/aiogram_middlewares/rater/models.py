from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram_middlewares.utils import make_dataclass

if TYPE_CHECKING:
	from .types import RateDataCounterAttrType


@make_dataclass
class RateData:
	rate: int
	sent_warning_count: int

	def update_counter(
		self: RateData, counter: RateDataCounterAttrType, count: int = 1,
	) -> None:
		"""Count up one of counters in this dataclass."""
		cnt: int = self.__getattribute__(counter)
		self.__setattr__(counter, cnt + count)

from __future__ import annotations

from aiogram_middlewares.utils import make_dataclass


@make_dataclass
class RateData:
	rate: int = 0
	sent_warning_count: int = 0

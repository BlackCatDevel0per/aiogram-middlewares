from __future__ import annotations

import asyncio
import logging
from asyncio import Semaphore
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from asyncio import AbstractEventLoop
	from types import TracebackType

	from annotated_types import Gt
	from typing_extensions import Annotated

	PositiveFloat = Annotated[float, Gt(0)]
	PositiveInt = Annotated[int, Gt(0)]


logger = logging.getLogger(__name__)


# TODO: ABC..
class ThrottleSemaphore(Semaphore):

	__slots__ = (
		'max_rate',
		'time_period',
	)

	_loop: AbstractEventLoop

	def __init__(
		self: ThrottleSemaphore,
		max_rate: PositiveInt, time_period: PositiveInt | PositiveFloat = 60,
		loop: AbstractEventLoop | None = None,
	):
		# TODO: Refactor..
		if isinstance(max_rate, float):
			msg = 'Rate value must be int'
			raise TypeError(msg)

		if max_rate <= 0:
			msg = 'Rate value must be positive'
			raise ValueError(msg)
		if time_period <= 0:
			msg = 'Time value must be positive'
			raise ValueError(msg)

		self._delay_time: PositiveFloat = time_period / max_rate
		self._max_rate: PositiveInt = max_rate
		super().__init__(max_rate)  # FIXME: Pass loop or not..?

		self._loop.create_task(self._leak_sem())


	async def _leak_sem(self: ThrottleSemaphore) -> None:
		"""Background task that leaks semaphore releases by rate of tasks per time_period."""
		while True:
			await asyncio.sleep(self._delay_time)
			if self._value < self._max_rate:  # noqa: SLF001
				# Increase rate value
				self.release()


	async def __aenter__(self: ThrottleSemaphore) -> None:
		await self.acquire()


	async def __aexit__(
		self: ThrottleSemaphore,
		exc_type: type[BaseException] | None,
		exc: BaseException | None,
		tb: TracebackType | None,
	) -> None:
		return None

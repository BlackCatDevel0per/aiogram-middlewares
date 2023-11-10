from __future__ import annotations

import asyncio
import logging
from asyncio import Semaphore
from collections import deque
from sys import getrefcount as obj_getrefcount
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from asyncio import AbstractEventLoop, Future, Task
	from types import TracebackType
	from typing import Any, Literal

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

	_waiters: deque[Future[Any]]

	def __init__(
		self: ThrottleSemaphore,
		max_rate: PositiveInt, time_period: PositiveInt | PositiveFloat = 60,
		loop: AbstractEventLoop | None = None,
	):
		# TODO: Refactor..

		_delay_time: PositiveFloat = time_period / max_rate
		loop = loop if loop else asyncio.get_event_loop()  # @dep
		# Checks
		self.__checks_init(max_rate, time_period)
		# Init attrs
		self.__post_init(max_rate, _delay_time, loop)

		logger.debug('Semaphore limits: %i / %.02f sec.', self._max_rate, time_period)


	def __checks_init(
		self: ThrottleSemaphore,
		max_rate: PositiveInt, time_period: PositiveInt | PositiveFloat,
	) -> None:
		if isinstance(max_rate, float):
			msg = 'Rate value must be int'
			raise TypeError(msg)

		if max_rate <= 0:
			msg = 'Rate value must be positive'
			raise ValueError(msg)
		if time_period <= 0:
			msg = 'Time value must be positive'
			raise ValueError(msg)


	def __post_init(
		self: ThrottleSemaphore,
		max_rate: PositiveInt, delay_time: PositiveFloat,
		loop: AbstractEventLoop,
	) -> None:
		self._delay_time = delay_time
		self._max_rate: PositiveInt = max_rate

		# FIXME: Pass loop or not..?
		self._value: PositiveInt = max_rate
		self._waiters = deque()

		self._loop = loop
		self._leak_task: Task | None = None
		self._leak_task_min_refs2die: int = 3

		self.acquire = self._first_acquire  # type: ignore  # Crutchy~, but ok


	async def _first_acquire(self: ThrottleSemaphore) -> Literal[True]:
		"""Just check for the first time & switch to acquire."""
		if not self._leak_task:
			# TODO: Add delete callback
			# TODO: Refactor..
			self._leak_task = self._loop.create_task(self._leak_sem())
		self.acquire = super().acquire  # type: ignore
		return await self.acquire()


	def __del__(self: ThrottleSemaphore) -> None:
		logger.debug('Semaphore object deleted at %s', hex(id(self)))


	def copy(self: ThrottleSemaphore) -> ThrottleSemaphore:
		"""Return a new instance of the semaphore based on the params of the current instance."""
		cls = self.__class__
		ins = cls.__new__(cls)
		ins.__post_init(self._max_rate, self._delay_time, self._loop)  # Hmm..
		return ins


	# TODO: Done callback (task_cancel&cleanup+4notify-user_optional)


	async def _leak_sem(self: ThrottleSemaphore) -> None:
		"""Background task that leaks semaphore releases by rate of tasks per time_period."""
		# Can be implemented using `call_later` with queue (but more calculations..)
		logger.debug('Semaphore task start at %s', hex(id(self)))  # TODO: Aliases..
		while obj_getrefcount(self) > self._leak_task_min_refs2die:  # FIXME: Crutchy~~
			await asyncio.sleep(self._delay_time)
			if self._value < self._max_rate:
				# Increase rate value
				self.release()

		logger.debug('Semaphore task done at %s', hex(id(self)))


	async def __aexit__(
		self: ThrottleSemaphore,
		exc_type: type[BaseException] | None,
		exc: BaseException | None,
		tb: TracebackType | None,
	) -> None:
		"""Do nothing.."""
		# override parent magic method (no release)

from __future__ import annotations

import asyncio
import logging
from asyncio import Semaphore
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from asyncio import AbstractEventLoop, Future, Task
	from types import TracebackType
	from typing import Any, Callable, Literal

	from annotated_types import Gt
	from typing_extensions import Annotated

	PositiveFloat = Annotated[float, Gt(0)]
	PositiveInt = Annotated[int, Gt(0)]

	true = Literal[True]

	LeakDoneCallback = Callable[[], Any]


logger = logging.getLogger(__name__)


# TODO: ABC.. & more variations), remove supcls.
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
		self.leak_task: Task | None = None
		self._is_leak = True
		self._leak_task_min_refs2die: int = 3

		self._leak_done_callback: LeakDoneCallback | None = None

		self.acquire = self._first_acquire  # type: ignore  # Crutchy~, but ok


	async def _first_acquire(self: ThrottleSemaphore) -> true:
		"""Just check for the first time & switch to acquire."""
		if not self.leak_task:
			# TODO: Add delete callback
			# TODO: Refactor..
			self.leak_task = self._loop.create_task(self._leak_sem_task())
		self.acquire = self._acquire  # type: ignore
		return await self.acquire()


	def locked(self: ThrottleSemaphore) -> bool:
		"""Return True if semaphore cannot be acquired immediately."""
		return self._value == 0 or (
			any(not w.cancelled() for w in self._waiters))


	async def _acquire(self: ThrottleSemaphore) -> true:
		"""Acquire a semaphore.

		If the internal counter is larger than zero on entry,
		decrement it by one and return True immediately.  If it is
		zero on entry, block, waiting until some other coroutine has
		called release() to make it larger than 0, and then return
		True.
		"""
		if not self.locked():
			self._value -= 1
			return True

		fut = self._loop.create_future()
		self._waiters.append(fut)

		# Finally block should be called before the CancelledError
		# handling as we don't want CancelledError to call
		# _wake_up_first() and attempt to wake up itself.
		try:
			try:
				await fut
			finally:
				self._waiters.remove(fut)
		except asyncio.CancelledError:
			if not fut.cancelled():
				self._value += 1
				self._wake_up_next()
			raise

		if self._value > 0:
			self._wake_up_next()
		return True


	def _wake_up_next(self: ThrottleSemaphore) -> None:
		"""Wake up the first waiter that isn't done."""
		if not self._waiters:
			return

		for fut in self._waiters:
			if not fut.done():
				self._value -= 1
				fut.set_result(True)  # noqa: FBT003
				return


	def on_leak_done_callback(self: ThrottleSemaphore, func: LeakDoneCallback) -> true:
		"""Set callback which run on leak task done."""
		self._leak_done_callback = func
		return True


	def stick_leak_done_callback(self: ThrottleSemaphore, func: LeakDoneCallback) -> bool:
		"""Add callback which run on leak task done - if it's no callback, otherwise do nothing."""
		if self._leak_done_callback:
			return False
		return self.on_leak_done_callback(func)


	def __del__(self: ThrottleSemaphore) -> None:
		"""Log on object delete."""
		logger.debug(
			'<Semaphore> object [bold red blink]deleted[/] at %s',
			hex(id(self)),
			extra={'markup': True},
		)


	def copy(self: ThrottleSemaphore) -> ThrottleSemaphore:
		"""Return a new instance of the semaphore based on the params of the current instance."""
		cls = self.__class__
		ins = cls.__new__(cls)
		ins.__post_init(self._max_rate, self._delay_time, self._loop)  # Hmm..
		return ins


	# TODO: Done callback (task_cancel&cleanup+4notify-user_optional) - callbacks (condition(s)) variants =)


	@property
	def is_leak_done(self: ThrottleSemaphore) -> bool:
		"""Check is leak done or not."""
		return self._is_leak


	def is_jobs_pending(self: ThrottleSemaphore) -> bool:
		# ...
		return bool(self._waiters)


	def set_leak_done(self: ThrottleSemaphore) -> None:
		"""Set done status for leak task."""
		self._is_leak = False


	async def _leak(self: ThrottleSemaphore) -> None:
		await asyncio.sleep(self._delay_time)
		if self._value < self._max_rate:
			# Increase rate value
			self.release()


	async def _leak_sem_task(self: ThrottleSemaphore) -> None:
		"""Background task that leaks semaphore releases by rate of tasks per time_period."""
		# Can be implemented using `call_later` with queue
		# without step-part timing (but more calculations..)
		logger.debug(
			'<Semaphore> task [bold green blink]start[/] at %s',
			hex(id(self)),
			extra={'markup': True},
		)  # TODO: Aliases.. (& colors based on it)

		while self._is_leak:
			await self._leak()

		# If on task end has undone waiters - finish them
		# TODO: Do it optional & choose another condition..
		while self._waiters:
			await self._leak()
		# ...
		if self._leak_done_callback:
			self._leak_done_callback()

		logger.debug(
			'<Semaphore> task [bold yellow blink]done[/] at %s',
			hex(id(self)),
			extra={'markup': True},
		)


	async def __aexit__(
		self: ThrottleSemaphore,
		exc_type: type[BaseException] | None,
		exc: BaseException | None,
		tb: TracebackType | None,
	) -> None:
		"""Cancel leak task on exit."""
		# override parent magic method (no release)
		self.set_leak_done()  # TODO: Make it optional & tests..

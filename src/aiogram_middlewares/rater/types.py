from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from asyncio import TimerHandle
	from typing import Any, Awaitable, Callable, Dict, Literal, Optional, TypeVar, Union

	from aiogram import Bot
	from aiogram.types import Update, User

	from .caches import _ASMCLazyBackend
	from .models import RateData, ThrottleData

	# Outer (on handlers): TelegramEventObserver.trigger
	# Inner (per handler): HandlerObject.call
	HandleData = Dict[str, Any]
	HandleType = Callable[[Update, HandleData], Awaitable[Any]]

	ThrottleMiddleCall = Callable[
		[
			HandleType,
			RateData,
			Update, User, Bot, HandleData,
		], Any,
	]

	_ThrottleMiddlewareMethod = Callable[
		[
			HandleType,
			Update, User, HandleData, Bot, RateData,
		], Any,
	]

	_RD = TypeVar('_RD', bound=RateData)

	_BaseThrottleMethod = Callable[
		[Union[_RD, None], User, int, Bot], Awaitable[Union[RateData, _RD]],
	]

	_ProcHandleMethod = Callable[
		[
			HandleType, RateData,
			Update, User, HandleData,
		], Any,
	]


	PluggedAwaitable = Callable[[], Awaitable]
	_ASMCLazyBackend_ins = _ASMCLazyBackend
	_conn_type = Union[_ASMCLazyBackend, None]
	ttl_type = Union[int, float]
	opt_ttl_type = Optional[Union[int, float]]

	_status_type = Union[bool, int]

	AsyncHandlable = Callable[
		[
			_ASMCLazyBackend_ins, Any, PluggedAwaitable, opt_ttl_type,
			TimerHandle, _conn_type,
		],
		Awaitable[_status_type],
	]
	WrappedHandlable = Callable[
		[
			_ASMCLazyBackend_ins, Any, PluggedAwaitable, opt_ttl_type, _conn_type,
		],
		Awaitable[Union[bool, int]],
	]

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from asyncio import TimerHandle
	from typing import Any, Awaitable, Callable, Dict, Literal, Optional, TypeVar, Union

	from aiogram import Bot
	from aiogram.types import Update, User

	from aiogram_middlewares.caches import _ASMCLazyBackend

	from .models import RateData

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

	_TD = TypeVar('_TD', bound=RateData)

	_BaseThrottleMethod = Callable[
		[Union[_TD, None], User, int, Bot], Awaitable[Union[RateData, _TD]],
	]

	RateDataCounterAttrType = Literal['rate', 'sent_warning_count']
	_ProcHandleMethod = Callable[
		[
			HandleType, RateData, RateDataCounterAttrType,
			Update, User, HandleData,
		], Any,
	]


	PluggedAwaitable = Callable[[], Awaitable]
	_ASMCLazyBackend_ins = _ASMCLazyBackend
	_conn_type = Union[_ASMCLazyBackend, None]
	opt_ttl = Optional[int]

	_status_type = Union[bool, int]

	AsyncHandlable = Callable[
		[
			_ASMCLazyBackend_ins, Any, PluggedAwaitable, opt_ttl,
			TimerHandle, float, _conn_type,
		],
		Awaitable[_status_type],
	]
	WrappedHandlable = Callable[
		[
			_ASMCLazyBackend_ins, Any, PluggedAwaitable, opt_ttl, _conn_type,
		],
		Awaitable[Union[bool, int]],
	]

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from typing import Any, Awaitable, Callable, Dict, Literal, TypeVar, Union

	from aiogram import Bot
	from aiogram.types import Update, User

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

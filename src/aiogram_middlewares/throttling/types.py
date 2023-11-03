from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from typing import Any, Awaitable, Callable, Dict, Literal, TypeVar, Union

	from aiogram import Bot
	from aiogram.types import Update, User

	from .models import ThrottlingData

	# Outer (on handlers): TelegramEventObserver.trigger
	# Inner (per handler): HandlerObject.call
	HandleData = Dict[str, Any]
	HandleType = Callable[[Update, HandleData], Awaitable[Any]]

	ThrottleMiddleCall = Callable[
		[
			HandleType,
			ThrottlingData,
			Update, User, Bot, HandleData,
		], Any,
	]

	_ThrottleMiddlewareMethod = Callable[
		[
			HandleType,
			Update, User, HandleData, Bot, ThrottlingData,
		], Any,
	]

	_TD = TypeVar('_TD', bound=ThrottlingData)

	_BaseThrottleMethod = Callable[
		[Union[_TD, None], User, int, Bot], Awaitable[Union[ThrottlingData, _TD]],
	]

	_ProcHandleMethod = Callable[
		[
			HandleType, ThrottlingData, Literal['rate', 'sent_warning_count'],
			Update, User, HandleData,
		], Any,
	]

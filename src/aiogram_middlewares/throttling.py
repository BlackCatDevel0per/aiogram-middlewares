from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiocache import Cache
from aiocache.serializers import NullSerializer
from aiogram import BaseMiddleware

from .caches import AdvancedSimpleMemoryCache
from .models import ThrottlingData

if TYPE_CHECKING:
	from typing import Any, Awaitable, Callable

	from aiocache.serializers import BaseSerializer
	from aiogram import Bot
	from aiogram.dispatcher.event.handler import HandlerObject
	from aiogram.types import TelegramObject, User
	from pydantic.types import PositiveFloat, PositiveInt


logger = logging.getLogger(__name__)

# TODO: Update README.. & mb aiogram2 support..


class ThrottlingMiddleware(BaseMiddleware):
	def __init__(
		self: ThrottlingMiddleware,
		period_sec: PositiveFloat | PositiveInt = 1, after_handle_count: PositiveInt = 1, warnings_count: PositiveInt = 2,
		cache_serializer: BaseSerializer = NullSerializer,
		*, cooldown_message: str = 'Calm down!', topping_up: bool = True,
	) -> None:
		# TODO: Docstrings!!!
		assert period_sec >= 1, '`period` must be positive!'
		assert warnings_count >= 1, '`after_msg_count` must be positive!'
		assert after_handle_count >= 1, '`after_msg_count` must be positive!'

		logger.debug('Limits: max. %s messages in %s sec., user warning %s times', after_handle_count, period_sec, warnings_count)

		self.period_sec = period_sec
		self.warnings_count = warnings_count
		self.after_handle_count = after_handle_count - 1

		self.cooldown_message = cooldown_message

		self.throttle: self.throttle_topping | self.throttle_ = self.throttle_

		self.middleware: self.middleware__ser | self.middleware_ = self.middleware_

		if topping_up:
			self.throttle = self.throttle_topping

		# Serialize if have serializer
		# TODO: Mb add check if not None & if cache class is subclass of `AdvancedSimpleMemoryCache`
		if not isinstance(cache_serializer, NullSerializer):
			self.middleware = self.middleware__ser


		self._cache: Cache[int, ThrottlingData] = Cache(  # Correct type hint??
			cache_class=AdvancedSimpleMemoryCache,
			ttl=period_sec,
			# WARNING: If you use spece storage and program will fail, some items could be still store in memory!
			serializer=cache_serializer(),  # TODO: ...
		)


	async def throttle_(self: ThrottlingMiddleware, throttling_data: ThrottlingData | None, event_user: User) -> ThrottlingData:
		if not throttling_data:
			logger.debug('Handle user: %s', event_user.username)  # noqa: PLE1205
			throttling_data = ThrottlingData(rate=0, sent_warning_count=0)
			# Add new item to cache with ttl from initializator.
			await self._cache.set(event_user.id, throttling_data)
		return throttling_data

	async def throttle_topping(self: ThrottlingMiddleware, throttling_data: ThrottlingData | None, event_user: User) -> ThrottlingData:
		throttling_data = await self.throttle_(throttling_data, event_user)
		# Reset ttl for item (topping) (kv)
		await self._cache.expire(event_user.id, self.period_sec)
		return throttling_data


	async def try_user_warning(
		self: ThrottlingMiddleware,
		handler: HandlerObject,
		throttling_data: ThrottlingData, event: TelegramObject, event_user: User, data: dict[str, Any],
	) -> None:
		bot: Bot = data['bot']

		# TODO: Add optional 'You can write now' message)
		# For example implement cache method with additional call (on_end -> send_msg)
		try:
			await bot.send_message(
				chat_id=event_user.id,
				text=self.cooldown_message,
			)
		except Exception:
			logger.warning('Warning message for user %s not sent', event_user.username, exc_info=True)


	async def on_warning(
		self: ThrottlingMiddleware,
		handler: HandlerObject,
		throttling_data: ThrottlingData, event: TelegramObject, event_user: User, data: dict[str, Any],
	) -> None:
		# if is first time#
		if throttling_data.sent_warning_count == 0:
			return await self.proc_handler(handler, throttling_data, 'sent_warning_count', event, event_user, data)

		await self.try_user_warning(handler, throttling_data, event, event_user, data)

		throttling_data.sent_warning_count += 1
		return


	async def proc_handler(
		self: ThrottlingMiddleware,
		handler: HandlerObject,
		throttling_data: ThrottlingData, counter: str, event: TelegramObject, event_user: User, data: dict[str, Any],
	) -> HandlerObject:
		throttling_data.update_counter(counter)
		# TODO: Mb log handler's name..
		logger.debug('proc handler for: %s', event_user.username)
		return await handler(event, data)


	async def middleware_(
		self: ThrottlingMiddleware,
		handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
		event: TelegramObject,
		event_user: User,
		data: dict[str, Any],
		throttling_data: ThrottlingData,
	) -> Any:

		is_not_exceed_rate = self.after_handle_count > throttling_data.rate
		is_not_exceed_warnings = self.warnings_count >= throttling_data.sent_warning_count

		# TODO: Mb one more variant for debug..
		#
		# if is_not_exceed_rate or is_not_exceed_warnings:
		# 	logger.debug('is_exceed_rate=%s, is_exceed_warnings=%s', not is_not_exceed_rate, not is_not_exceed_warnings)
		#

		if is_not_exceed_rate:
			return await self.proc_handler(handler, throttling_data, 'rate', event, event_user, data)

		# try send warning
		if is_not_exceed_warnings:
			await self.on_warning(handler, throttling_data, event, event_user, data)
		return

	async def middleware__ser(
		self: ThrottlingMiddleware,
		handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
		event: TelegramObject,
		event_user: User,
		data: dict[str, Any],
		throttling_data: ThrottlingData,
	) -> Any:
		result = await self.middleware_(handler, event, event_user, data, throttling_data)
		# Just update value without changing ttl
		# Why aiocache's api doesn't has separate func for it? But `SENTINEL` well solution (but value stores without ttl aka FOREVER!) =)
		await self._cache.update(event_user.id, throttling_data)
		return result


	async def __call__(
		self: ThrottlingMiddleware,
		handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
		event: TelegramObject,
		data: dict[str, Any],
	) -> Any:
		event_user: User = data['event_from_user']
		# logging.debug('throttling middleware got new event: type(%s) from %s', type(event), event_user.username)

		event_user_throttling_data: ThrottlingData | None = await self._cache.get(event_user.id)
		throttling_data: ThrottlingData = await self.throttle(event_user_throttling_data, event_user)
		del event_user_throttling_data

		return await self.middleware(handler, event, event_user, data, throttling_data)

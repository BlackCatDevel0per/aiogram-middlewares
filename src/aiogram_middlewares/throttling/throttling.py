from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiocache import Cache
from aiocache.serializers import NullSerializer
from aiogram import BaseMiddleware

from aiogram_middlewares.caches import AdvancedSimpleMemoryCache

from .models import ThrottlingData

if TYPE_CHECKING:
	from typing import Any, Awaitable, Callable, Dict

	from aiocache.serializers import BaseSerializer
	from aiogram import Bot
	from aiogram.dispatcher.event.handler import HandlerObject
	from aiogram.types import Update, User
	from pydantic.types import PositiveInt

	TelegramEventObserver_trigger = Callable[[Update, Dict[str, Any]], Awaitable[Any]]
	HandleType = TelegramEventObserver_trigger | HandlerObject


logger = logging.getLogger(__name__)

# TODO: Check per-second spam & message spam..
# TODO: Update README.. & mb aiogram2 support..

# TODO: Add throttling
# TODO: Add options to choose between antiflood & throttling
# TODO: Test & optimize =)

# TODO: Mb add debouncing) (topping? XD)
# TODO: Mb role filtering middleare.. (In aiogram2 is useless..)

# TODO: Mb add action on calmdown & after calm


class Throttling:

	_cache: Cache[int, ThrottlingData] = None

	def __init__(
		self: Throttling,
		period_sec: PositiveInt = 3, after_handle_count: PositiveInt = 1, *,
		warnings_count: PositiveInt = 2,
		cache_serializer: BaseSerializer = NullSerializer,
		cooldown_message: str = 'Calm down!', topping_up: bool = True,
		is_cache_unity: bool = False,
	) -> None:
		# TODO: Docstrings!!!
		# TODO: Mb rename topping to debouncing..
		assert period_sec >= 1, '`period` must be positive!'
		assert warnings_count >= 1, '`after_msg_count` must be positive!'
		assert after_handle_count >= 1, '`after_msg_count` must be positive!'

		if period_sec < 3:  # noqa: PLR2004
			# recommended to set above 3 for period..
			logger.warning('Recommended to set above 3 for `period_sec` param..')
		logger.debug(
			'Limits: max. %s messages in %s sec., user warning %s times',
			after_handle_count, period_sec, warnings_count
		)

		self.period_sec = period_sec
		self.warnings_count = warnings_count
		self.after_handle_count = after_handle_count - 1

		self.cooldown_message = cooldown_message

		self.throttle: Callable[
			[ThrottlingData | None, User, int], Awaitable[ThrottlingData],
		] = self.throttle_

		self.middleware: Callable[
			[
				HandleType,
				Update, User, dict[str, Any], Bot, ThrottlingData,
			], Any,
		] = self.middleware_

		if topping_up:
			self.throttle = self.throttle_topping

			# for repr
			self._topping_up = topping_up

		# Serialize if have serializer
		# TODO: Mb add check if not None & if cache class is subclass of `AdvancedSimpleMemoryCache`
		if not isinstance(cache_serializer, NullSerializer):
			self.middleware = self.middleware__ser


		self._cache = Cache(  # Correct type hint??
			cache_class=AdvancedSimpleMemoryCache,
			ttl=period_sec,
			# WARNING: If you use disk storage and program will fail, some items could be still store in memory!
			serializer=cache_serializer(),  # TODO: ...
		)

		# For unity cache for all instances
		#
		self.__is_cache_unity = is_cache_unity
		self.choose_cache(Throttling)

	def choose_cache(self: Throttling, class_: type) -> None:
		if self.__is_cache_unity:
			if class_._cache is None:
				class_._cache = self._cache
			del self._cache
			self._cache = class_._cache
			logger.debug(
				'Using unity cache instance on address `%s`, obj: `%s`',
				hex(id(class_._cache)), repr(self),
			)
		else:
			logger.debug(
				'Using self cache instance on address `%s`, obj: `%s`',
				hex(id(self._cache)), repr(self),
			)


	def __str__(self: Throttling) -> str:
		return repr(self)

	def __repr__(self: Throttling) -> str:
		# FIXME: Bruh
		return (
			f"{self.__class__.__name__}"
			f"(period_sec={self.period_sec}, "
			f"after_handle_count={self.after_handle_count}, "
			f"cooldown_message={self.cooldown_message}, "
			f"topping_up={self._topping_up}, "
			f"warnings_count={self.warnings_count})"
		)



	async def throttle_(
		self: Throttling, throttling_data: ThrottlingData | None,
		event_user: User, ttl: int,
	) -> ThrottlingData:
		"""Antiflood.."""
		if not throttling_data:
			logger.debug('[%s] Handle user: %s', self.__class__.__name__, event_user.username)
			throttling_data = ThrottlingData(rate=0, sent_warning_count=0)
			# Add new item to cache with ttl from initializator.
			# (`Cache.add` does the same, but with checking in cache..)
			await self._cache.set(event_user.id, throttling_data, ttl)
		return throttling_data

	# TODO: Flag too..
	async def throttle_topping(
		self: Throttling, throttling_data: ThrottlingData | None,
		event_user: User, ttl: int,
	) -> ThrottlingData:
		"""Antiflood+Debouncing."""
		throttling_data = await self.throttle_(throttling_data, event_user, ttl)
		# Reset ttl for item (topping) (kv)
		await self._cache.expire(event_user.id, ttl)
		return throttling_data


	async def try_user_warning(  # noqa: PLR0913
		self: Throttling,
		handler: HandleType,  # noqa: ARG002
		throttling_data: ThrottlingData, event: Update, event_user: User, bot: Bot | None,
		data: dict[str, Any],  # noqa: ARG002
	) -> None:
		"""Send user warnings."""

		# FIXME: Crutchy..
		if not bot:
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
		self: Throttling,
		handler: HandleType,
		throttling_data: ThrottlingData, event: Update, event_user: User, bot: Bot,
		data: dict[str, Any],
	) -> None:
		"""On warning handler."""
		# if it's first time#
		if throttling_data.sent_warning_count == 0:
			return await self.proc_handler(
				handler, throttling_data, 'sent_warning_count', event, event_user, data,
			)

		await self.try_user_warning(handler, throttling_data, event, event_user, bot, data)

		throttling_data.sent_warning_count += 1
		return


	async def proc_handler(
		self: Throttling,
		handler: HandleType,
		throttling_data: ThrottlingData, counter: str,
		event: Update, event_user: User, data: dict[str, Any],
	) -> Any:
		"""Process handler's update."""
		throttling_data.update_counter(counter)
		# TODO: Mb log handler's name..
		logger.debug('[%s] Handle user: %s', self.__class__.__name__, event_user.username)
		return await handler(event, data)


	async def middleware_(
		self: Throttling,
		handler: HandleType,
		event: Update,
		event_user: User,
		bot: Bot,
		data: dict[str, Any],
		throttling_data: ThrottlingData,
	) -> Any:
		"""Main middleware."""

		is_not_exceed_rate = self.after_handle_count > throttling_data.rate
		is_not_exceed_warnings = self.warnings_count >= throttling_data.sent_warning_count

		# TODO: Mb one more variant for debug..
		#
		# if is_not_exceed_rate or is_not_exceed_warnings:
		# 	logger.debug('is_exceed_rate=%s, is_exceed_warnings=%s', not is_not_exceed_rate, not is_not_exceed_warnings)
		#

		if is_not_exceed_rate:
			return await self.proc_handler(
				handler, throttling_data, 'rate', event, event_user,
				data,
			)

		# try send warning
		if is_not_exceed_warnings:
			await self.on_warning(handler, throttling_data, event, event_user, bot, data)
		return

	async def middleware__ser(
		self: Throttling,
		handler: HandleType,
		event: Update,
		event_user: User,
		bot: Bot,
		data: dict[str, Any],
		throttling_data: ThrottlingData,
	) -> Any:
		"""Handle if custom serializer is available."""
		result = await self.middleware_(handler, event, event_user, data, bot, throttling_data)
		# Just update value without changing ttl
		# Why aiocache's api doesn't has separate func for it? But `SENTINEL` well solution (but value stores without ttl aka FOREVER!) =)
		await self._cache.update(event_user.id, throttling_data)
		return result


class ThrottlingMiddleware(Throttling, BaseMiddleware):
	async def __call__(
		self: ThrottlingMiddleware,
		handler: HandleType,
		event: Update,
		data: dict[str, Any],
	) -> Any:
		"""Callable for routers/dispatchers."""
		event_user: User = data['event_from_user']
		# logging.debug('throttling middleware got new event: type(%s) from %s', type(event), event_user.username)

		event_user_throttling_data: ThrottlingData | None = await self._cache.get(event_user.id)
		throttling_data: ThrottlingData = await self.throttle(
			event_user_throttling_data, event_user, self.period_sec,
		)
		del event_user_throttling_data

		return await self.middleware(handler, event, event_user, data, None, throttling_data)

from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING

from aiogram_middlewares.throttling.base import ThrottlingAttrsABC

if TYPE_CHECKING:

	from typing import Any

	from aiogram import Bot
	from aiogram.types import Update, User
	from pydantic.types import PositiveInt

	from aiogram_middlewares.throttling.base import HandleType
	from aiogram_middlewares.throttling.types import HandleData

	from .models import ThrottlingData


logger = logging.getLogger(__name__)


class ThrottlingNotifyBase(ThrottlingAttrsABC):

	def __init__(
		self: ThrottlingNotifyBase,
		warnings_count: PositiveInt,
	) -> None:
		assert warnings_count >= 1, '`warnings_count` must be positive!'

		self.warnings_count = warnings_count


	@abstractmethod
	async def try_user_warning(
		self: ThrottlingNotifyBase, throttling_data: ThrottlingData, event_user: User, bot: Bot,
	) -> None:
		raise NotADirectoryError


	async def _middleware(
		self: ThrottlingNotifyBase,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		throttling_data: ThrottlingData,
	) -> Any:
		"""Main middleware."""
		is_not_exceed_rate = self.after_handle_count > throttling_data.rate

		# TODO: Mb one more variant(s) for debug..

		# proc/pass update action (run times from `after_handle_amount`)
		if is_not_exceed_rate:
			return await self.proc_handle(
				handle, throttling_data, 'rate', event, event_user,
				data,
			)

		is_not_exceed_warnings = self.warnings_count >= throttling_data.sent_warning_count

		# try send warning (run times from `warning_time`)
		if is_not_exceed_warnings:
			await self.on_warning(handle, throttling_data, event, event_user, data, bot)
		return


	async def on_warning(
		self: ThrottlingNotifyBase,
		handle: HandleType,
		throttling_data: ThrottlingData, event: Update, event_user: User, data: HandleData,
		bot: Bot,
	) -> None:
		"""On warning handle."""
		# if it's first time#
		# Crutchy~
		if throttling_data.sent_warning_count == 0:
			return await self.proc_handle(
				handle, throttling_data, 'sent_warning_count', event, event_user, data,
			)

		# [Optional] Will call: just warning or calmed notify (on end)
		await self.try_user_warning(throttling_data, event_user, bot)

		throttling_data.sent_warning_count += 1
		return


# Cooldown
class ThrottlingNotifyCooldown(ThrottlingNotifyBase):

	def __init__(
		self: ThrottlingNotifyCooldown,
		cooldown_message: str | None,
		warnings_count: PositiveInt,
	) -> None:
		super().__init__(warnings_count=warnings_count)
		self.cooldown_message = cooldown_message

		# logger.debug(
		# 	'Cooldown notify disabled for `%s` at `%s`',
		# 	self.__class__.__name__, hex(id(self.__class__.__name__)),
		# )


	async def try_user_warning(
		self: ThrottlingNotifyCooldown | ThrottlingNotifyCC, throttling_data: ThrottlingData, event_user: User, bot: Bot,  # noqa: ARG002
	) -> None:
		"""Send user warnings."""
		# FIXME: Crutchy..
		# For example implement cache method with additional call (on_end -> send_msg)
		try:
			await bot.send_message(
				chat_id=event_user.id,
				text=self.cooldown_message,
			)
		except Exception:
			logger.warning(
				'Warning message for user %s not sent',
				event_user.username, exc_info=True,
			)


# Calmed
class ThrottlingNotifyCalmed(ThrottlingNotifyBase):

	def __init__(
		self: ThrottlingNotifyCalmed,
		calmed_message: str | None,
		warnings_count: PositiveInt,
	) -> None:
		super().__init__(warnings_count=warnings_count)
		self.calmed_message = calmed_message

		# logger.debug(
		# 	'Calmed notify disabled for `%s` at `%s`',
		# 	self.__class__.__name__, hex(id(self.__class__.__name__)),
		# )


	# TODO: Flag too..
	async def throttle(
		self: ThrottlingNotifyCalmed, throttling_data: ThrottlingData | None,
		event_user: User, ttl: int, bot: Bot,
	) -> ThrottlingData:
		"""..."""
		throttling_data = await self._throttle(throttling_data, event_user, ttl, bot)
		# Reset ttl for item (topping/debouncing)
		await self._cache.expire_with_sub_handler(
			event_user.id,
			# plug awaitable
			lambda: bot.send_message(chat_id=event_user.id, text=self.calmed_message),
			ttl,
		)
		return throttling_data


	async def try_user_warning(
		self: ThrottlingNotifyCalmed,
		throttling_data: ThrottlingData, event_user: User, bot: Bot,
	) -> None:
		"""Send warnings to user and on cache item die - send notify unmuted."""
		await self._later_calmed_notify(throttling_data, event_user, bot)


	async def _later_calmed_notify(
		self: ThrottlingNotifyCalmed | ThrottlingNotifyCC,
		throttling_data: ThrottlingData, event_user: User, bot: Bot,
	) -> None:
		"""Call: On item in cache die - send message to user."""
		if throttling_data.sent_warning_count == 1:
			await self._cache.set_sub_handler(
				event_user.id,
				# plug awaitable
				# FIXME: Duplication, move to other method..
				lambda: bot.send_message(chat_id=event_user.id, text=self.calmed_message),
				self.period_sec,
			)


# Cooldown + Calmed
class ThrottlingNotifyCC(ThrottlingNotifyCalmed):

	def __init__(
		self: ThrottlingNotifyCC,
		calmed_message: str | None, cooldown_message: str | None,
		warnings_count: PositiveInt,
	) -> None:
		ThrottlingNotifyBase.__init__(self, warnings_count=warnings_count)
		self.cooldown_message = cooldown_message
		self.calmed_message = calmed_message

		# logger.debug(
		# 	'Cooldown notify disabled for `%s` at `%s`',
		# 	self.__class__.__name__, hex(id(self.__class__.__name__)),
		# )

		# logger.debug(
		# 	'Calmed notify disabled for `%s` at `%s`',
		# 	self.__class__.__name__, hex(id(self.__class__.__name__)),
		# )


	async def try_user_warning(
		self: ThrottlingNotifyCC,
		throttling_data: ThrottlingData, event_user: User, bot: Bot,
	) -> None:
		"""Send warnings to user and on cache item die - send notify unmuted."""
		await ThrottlingNotifyCooldown.try_user_warning(self, throttling_data, event_user, bot)
		await self._later_calmed_notify(throttling_data, event_user, bot)  # noqa: SLF001

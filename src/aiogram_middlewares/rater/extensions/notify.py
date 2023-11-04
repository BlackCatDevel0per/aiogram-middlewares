from __future__ import annotations

import logging
from abc import abstractmethod
from typing import TYPE_CHECKING

from aiogram_middlewares.rater.base import RaterAttrsABC

if TYPE_CHECKING:

	from typing import Any

	from aiogram import Bot
	from aiogram.types import Update, User
	from pydantic.types import PositiveInt

	from aiogram_middlewares.rater.base import HandleType
	from aiogram_middlewares.rater.types import HandleData

	from .models import RateData


logger = logging.getLogger(__name__)


class RaterNotifyBase(RaterAttrsABC):


	@abstractmethod
	async def on_exceed_rate(
		self: RaterNotifyBase,
		handle: HandleType,
		rate_data: RateData, event: Update, event_user: User, data: HandleData,
		bot: Bot,
	) -> None:
		raise NotImplementedError


	async def _middleware(
		self: RaterNotifyBase,
		handle: HandleType,
		event: Update,
		event_user: User,
		data: HandleData,
		bot: Bot,
		rate_data: RateData,
	) -> Any | None:
		"""Main middleware."""
		##
		is_not_exceed_rate = self.after_handle_count > rate_data.rate
		# TODO: Mb one more variant(s) for debug..

		# proc/pass update action while not exceed rate limit (run times limit from `after_handle_count`)
		if is_not_exceed_rate:
			# count up rate & proc
			# FIXME: Remove useless counter param?
			return await self.proc_handle(####
				handle, rate_data, 'rate', event, event_user,
				data,
			)

		await self.on_exceed_rate(handle, rate_data, event, event_user, data, bot)
		return None


# Cooldown
class RateNotifyCooldown(RaterNotifyBase):

	def __init__(
		self: RateNotifyCooldown,
		cooldown_message: str | None,
		warnings_count: PositiveInt,
	) -> None:
		assert warnings_count >= 1, '`warnings_count` must be positive!'

		self.warnings_count = warnings_count
		self.cooldown_message = cooldown_message


	async def on_exceed_rate(
		self: RateNotifyCooldown,
		handle: HandleType,  # noqa: ARG002
		rate_data: RateData, event: Update, event_user: User, data: HandleData,  # noqa: ARG002
		bot: Bot,
	) -> None:
		"""Send cooldowns."""
		is_not_exceed_warnings = self.warnings_count > rate_data.sent_warning_count
		# try send warning (run times from `warning_count`)
		if is_not_exceed_warnings:
			# [Optional] Will call: just warning and optional calmed notify (on end)
			await self.try_user_warning(rate_data, event_user, bot)

			rate_data.sent_warning_count += 1


	async def try_user_warning(
		self: RateNotifyCooldown | RateNotifyCC, rate_data: RateData,  # noqa: ARG002
		event_user: User, bot: Bot,
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
class RateNotifyCalmed(RaterNotifyBase):

	def __init__(
		self: RateNotifyCalmed,
		calmed_message: str | None,
	) -> None:
		self.calmed_message = calmed_message

	async def on_exceed_rate(
		self: RateNotifyCalmed,
		handle: HandleType,  # noqa: ARG002
		rate_data: RateData, event: Update, event_user: User, data: HandleData,  # noqa: ARG002
		bot: Bot,
	) -> None:
		"""Call: On item in cache die - send message to user."""
		await self._cache.set_sub_handler(
			event_user.id,
			# plug awaitable
			lambda: bot.send_message(chat_id=event_user.id, text=self.calmed_message),
		)
		# ...


# TODO: call_later this way for throttling..
# Cooldown + Calmed
class RateNotifyCC(RateNotifyCooldown):

	def __init__(
		self: RateNotifyCC,
		calmed_message: str | None, cooldown_message: str | None,
		warnings_count: PositiveInt,
	) -> None:
		self.warnings_count = warnings_count
		self.cooldown_message = cooldown_message
		self.calmed_message = calmed_message


	async def on_exceed_rate(
		self: RateNotifyCC,
		handle: HandleType,
		rate_data: RateData, event: Update, event_user: User, data: HandleData,
		bot: Bot,
	) -> None:
		await RateNotifyCooldown.on_exceed_rate(
			self, handle, rate_data, event, event_user, data, bot,
		)
		await RateNotifyCalmed.on_exceed_rate(
			self, handle, rate_data, event, event_user, data, bot,
		)

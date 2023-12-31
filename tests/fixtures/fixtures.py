from __future__ import annotations

import datetime
import logging

from random import randint

from aiogram import types

# from aiogram.enums import ChatType
from aiogram.filters.command import CommandObject

logger = logging.getLogger(__name__)


class FakeBot:
	async def send_message(self: FakeBot, chat_id: int, text: str, *args, **kwargs) -> None:
		# print('%s -> %i' % (text, chat_id))
		logger.info('%s -> %i', text, chat_id)


Bot = FakeBot()


async def empty_handler(*args, **kwargs) -> None:
	...


def make_fake_user_update(user_id: int, username: str):
	message = types.Message(
							message_id=randint(100000000, 999999999),
							date=datetime.datetime(2023, 10, 11, 20, 58, 36, tzinfo=datetime.timezone.utc),

							chat=types.Chat(
								id=user_id,
								type='private',
								title=None,
								username=username,
								first_name='Some',
								last_name='User',
								is_forum=None,
								photo=None,
								active_usernames=None,
								emoji_status_custom_emoji_id=None,
								emoji_status_expiration_date=None,
								bio=None,
								has_private_forwards=None,
								has_restricted_voice_and_video_messages=None,
								join_to_send_messages=None,
								join_by_request=None,
								description=None,
								invite_link=None,
								pinned_message=None,
								permissions=None,
								slow_mode_delay=None,
								message_auto_delete_time=None,
								has_aggressive_anti_spam_enabled=None,
								has_hidden_members=None,
								has_protected_content=None,
								sticker_set_name=None,
								can_set_sticker_set=None,
								linked_chat_id=None,
								location=None
							),

							message_thread_id=None,
							from_user=types.User(id=user_id,
													is_bot=False,
													first_name='Some',
													last_name='User',
													username=username,
													language_code='ru',
													is_premium=None,
													added_to_attachment_menu=None,
													can_join_groups=None,
													can_read_all_group_messages=None,
													supports_inline_queries=None),
							sender_chat=None,
							forward_from=None,
							forward_from_chat=None,
							forward_from_message_id=None,
							forward_signature=None,
							forward_sender_name=None,
							forward_date=None,
							is_topic_message=None,
							is_automatic_forward=None,
							reply_to_message=None,
							via_bot=None,
							edit_date=None,
							has_protected_content=None,
							media_group_id=None,
							author_signature=None,
							# text='/start',
							# text='/say',
							text='/say ' + 'yoohoo!'*10,

							entities=[
								types.MessageEntity(
									type='bot_command',
									offset=0,
									length=6,
									url=None,
									user=None,
									language=None,
									custom_emoji_id=None,
								),
							],

							animation=None,
							audio=None,
							document=None,
							photo=None,
							sticker=None,
							story=None,
							video=None,
							video_note=None,
							voice=None,
							caption=None,
							caption_entities=None,
							has_media_spoiler=None,
							contact=None,
							dice=None,
							game=None,
							poll=None,
							venue=None,
							location=None,
							new_chat_members=None,
							left_chat_member=None,
							new_chat_title=None,
							new_chat_photo=None,
							delete_chat_photo=None,
							group_chat_created=None,
							supergroup_chat_created=None,
							channel_chat_created=None,
							message_auto_delete_timer_changed=None,
							migrate_to_chat_id=None,
							migrate_from_chat_id=None,
							pinned_message=None,
							invoice=None,
							successful_payment=None,
							user_shared=None,
							chat_shared=None,
							connected_website=None,
							write_access_allowed=None,
							passport_data=None,
							proximity_alert_triggered=None,
							forum_topic_created=None,
							forum_topic_edited=None,
							forum_topic_closed=None,
							forum_topic_reopened=None,
							general_forum_topic_hidden=None,
							general_forum_topic_unhidden=None,
							video_chat_scheduled=None,
							video_chat_started=None,
							video_chat_ended=None,
							video_chat_participants_invited=None,
							web_app_data=None,
							reply_markup=None,
	)


	data = {
		'bot': Bot,
		'bots': (Bot,),
		'command': CommandObject(prefix='/', command='start', mention=None),
		'dispatcher': 'aiogram.Dispatcher',  ##
		'event_chat': types.Chat(
			id=user_id,
			type='private',
			title=None,
			username=username,
			first_name='Some',
			last_name='User',
			is_forum=None,
			photo=None,
			active_usernames=None,
			emoji_status_custom_emoji_id=None,
			emoji_status_expiration_date=None,
			bio=None,
			has_private_forwards=None,
			has_restricted_voice_and_video_messages=None,
			join_to_send_messages=None,
			join_by_request=None,
			description=None,
			invite_link=None,
			pinned_message=None,
			permissions=None,
			slow_mode_delay=None,
			message_auto_delete_time=None,
			has_aggressive_anti_spam_enabled=None,
			has_hidden_members=None,
			has_protected_content=None,
			sticker_set_name=None,
			can_set_sticker_set=None,
			linked_chat_id=None,
			location=None,
		),
		'event_from_user': types.User(
			id=user_id,
			is_bot=False,
			first_name='Some',
			last_name='User',
			username=username,
			language_code='ru',
			is_premium=None,
			added_to_attachment_menu=None,
			can_join_groups=None,
			can_read_all_group_messages=None,
			supports_inline_queries=None,
		),
		'event_router': 'aiogram.Dispatcher',
		'event_update': types.Update(
									update_id=123654789,
									message=message,
									edited_message=None,
									channel_post=None,
									edited_channel_post=None,
									inline_query=None,
									chosen_inline_result=None,
									callback_query=None,
									shipping_query=None,
									pre_checkout_query=None,
									poll=None,
									poll_answer=None,
									my_chat_member=None,
									chat_member=None, chat_join_request=None,
		),
		'fsm_storage': 'aiogram.fsm.storage.memory.MemoryStorage',
		'handler': empty_handler,
		'raw_state': None,
		'skip_updates': True,
		'state': None,
	}

	return message, data

message, data = make_fake_user_update(123456789, 'someuser')
message2, data2 = make_fake_user_update(987654231, 'someuser2')

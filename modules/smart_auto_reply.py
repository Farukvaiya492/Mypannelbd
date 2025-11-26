import asyncio
import logging
from pyrogram import filters
from pyrogram.types import Message
from .base_module import BaseModule


class SmartAutoReplyModule(BaseModule):
    def __init__(self, client, socketio):
        super().__init__(client, socketio)
        self.pending_group_replies = {}
        self.pending_replies = {}
        self.group_reply_timeout = 120
        self.reply_timeout = 120
        
        self.auto_reply_message = (
            "𝑰 𝒎𝒂𝒚𝒃𝒆 𝒃𝒖𝒔𝒚 𝒏𝒐𝒘. 💝\n\n"
            "💬 আপনি চাইলে আমাকে কিছু জিজ্ঞাসা করতে পারেন, আমি AI দিয়ে উত্তর দেওয়ার চেষ্টা করব।\n"
            "🤖 **Auto-reply চালু / বন্ধ করতে:** /on , /off command ব্যবহার করুন\n\n"
            "💝 𝑻𝒉𝒂𝒏𝒌 𝑼 💝"
        )

    def setup(self):
        @self.client.on_message(filters.group & filters.text & filters.incoming & filters.mentioned)
        async def handle_group_mention(client, message: Message):
            try:
                user = message.from_user
                chat_id = message.chat.id
                msg_id = message.id
                group_name = message.chat.title or "Group"

                logging.info(f"👥 Mentioned in group '{group_name}' by {user.first_name}")
                self.emit_terminal(f'👥 Mentioned in {group_name} by {user.first_name}')

                group_key = f"{chat_id}_{msg_id}"

                if group_key in self.pending_group_replies:
                    return

                logging.info(f"📨 New group mention from {user.first_name} - Waiting {self.group_reply_timeout}s for reply")
                self.emit_terminal(f'⏰ Group mention: Waiting {self.group_reply_timeout}s...')

                async def send_delayed_group_reply():
                    try:
                        logging.info(f"⏰ Waiting {self.group_reply_timeout} seconds before group auto-reply...")
                        await asyncio.sleep(self.group_reply_timeout)

                        if group_key not in self.pending_group_replies:
                            logging.info("❌ Group reply was cancelled")
                            return

                        logging.info(f"📤 Sending auto-reply to group '{group_name}'...")
                        self.emit_terminal(f'📤 Auto-replying in {group_name}')

                        busy_message = "𝑰 𝒎𝒂𝒚𝒃𝒆 𝒃𝒖𝒔𝒚 𝒏𝒐𝒘. 💝\n\n 💬 কোন দরকার হলে 𝒊𝒏𝒃𝒐𝒙 𝒎𝒆. 💝 𝑻𝒉𝒂𝒏𝒌 𝑼 💝"

                        await message.reply_text(busy_message)
                        logging.info(f"✅ Sent busy message to group '{group_name}'")
                        self.emit_terminal(f'✅ Replied in group: {group_name}')

                    except asyncio.CancelledError:
                        logging.info("❌ Group auto-reply cancelled by user response")
                        self.emit_terminal(f'❌ Group auto-reply cancelled')
                    except Exception as e:
                        logging.error(f"Error sending group auto-reply: {e}", exc_info=True)
                    finally:
                        if group_key in self.pending_group_replies:
                            del self.pending_group_replies[group_key]

                task = asyncio.create_task(send_delayed_group_reply())
                self.pending_group_replies[group_key] = task

            except Exception as e:
                logging.error(f"Error handling group mention: {e}", exc_info=True)

        @self.client.on_message(filters.group & filters.outgoing)
        async def handle_group_outgoing(client, message: Message):
            try:
                chat_id = message.chat.id
                cancelled_count = 0
                keys_to_remove = []

                for key, task in self.pending_group_replies.items():
                    if key.startswith(f"{chat_id}_"):
                        task.cancel()
                        keys_to_remove.append(key)
                        cancelled_count += 1

                for key in keys_to_remove:
                    del self.pending_group_replies[key]

                if cancelled_count > 0:
                    group_name = message.chat.title or "Group"
                    logging.info(f"✅ Cancelled {cancelled_count} pending group auto-reply(s) in '{group_name}'")
                    self.emit_terminal(f'✅ Cancelled group auto-reply in {group_name}')

            except Exception as e:
                logging.error(f"Error handling group outgoing: {e}", exc_info=True)

        @self.client.on_message(filters.private & filters.text & filters.incoming)
        async def handle_incoming_private_message(client, message: Message):
            chat_id = message.chat.id
            msg_id = message.id
            user = message.from_user

            if message.text.startswith('/'):
                logging.info(f"⏭️ Skipping auto-reply for command: {message.text}")
                self.emit_terminal(f'⚙️ Command from {user.first_name}: "{message.text}"')
                return

            logging.info(f'📨 Private message from {user.first_name}: "{message.text[:50]}..."')
            self.emit_terminal(f'📨 Message from {user.first_name}: "{message.text[:50]}..."')

            logging.info(f"📨 New message from {user.first_name} - Waiting {self.reply_timeout}s for reply")
            self.emit_terminal(f'⏰ Waiting 120 sec for reply to {user.first_name}')

            self.pending_replies[chat_id] = {
                'message_id': msg_id,
                'timestamp': asyncio.get_event_loop().time()
            }

            asyncio.create_task(self._schedule_auto_reply(message, chat_id, msg_id))

        @self.client.on_message(filters.private & filters.outgoing)
        async def handle_outgoing_private_message(client, message: Message):
            chat_id = message.chat.id

            logging.info(f"👤 You replied manually to chat {chat_id}")
            self.emit_terminal(f'👤 Manual reply sent')

            if chat_id in self.pending_replies:
                logging.info(f"✅ Cancelling auto-reply (manual reply sent)")
                self.emit_terminal(f'✅ Auto-reply cancelled')
                del self.pending_replies[chat_id]

    async def _schedule_auto_reply(self, message: Message, chat_id: int, msg_id: int):
        try:
            logging.info(f"⏰ Waiting {self.reply_timeout} seconds before auto-reply...")
            await asyncio.sleep(self.reply_timeout)

            if chat_id in self.pending_replies and self.pending_replies[chat_id]['message_id'] == msg_id:
                try:
                    logging.info(f"📤 Sending auto-reply to {message.from_user.first_name}...")

                    await self.client.send_message(chat_id, self.auto_reply_message)
                    logging.info(f'✅ Auto-reply sent to {message.from_user.first_name}')
                    self.emit_terminal(f'🤖 Auto-replied to {message.from_user.first_name}')
                    del self.pending_replies[chat_id]

                except Exception as e:
                    logging.error(f"❌ Failed to send auto-reply: {e}", exc_info=True)
                    self.emit_terminal(f'❌ Auto-reply failed: {str(e)}')

        except Exception as e:
            logging.error(f"Error in auto-reply scheduling: {e}", exc_info=True)

    def cleanup(self):
        self.pending_group_replies.clear()
        self.pending_replies.clear()
        logging.info("Smart Auto-Reply module cleaned up")

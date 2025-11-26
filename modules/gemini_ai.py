import os
import asyncio
import logging
import requests
from collections import deque
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatAction
from pyrogram import ContinuePropagation
from .base_module import BaseModule


class GeminiAIModule(BaseModule):
    def __init__(self, client, socketio):
        super().__init__(client, socketio)
        self.api_key = os.getenv('GEMINI_API_KEY', 'put api key here')
        if not self.api_key:
            logging.error("❌ GEMINI_API_KEY environment variable not set! AI features will not work.")
            self.api_url = None
            self.enabled = False
        else:
            self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
            self.enabled = True

        self.conversation_history = {}
        self.max_history_length = 50
        self.auto_reply_mode = {}

        if self.api_key:
            logging.info("✅ Gemini AI: Using API key from environment variables")

    def setup(self):
        @self.client.on_message(filters.private & filters.incoming & filters.command("on"))
        async def handle_on_command(client, message: Message):
            if not self.enabled:
                await message.reply_text(
                    "⚠️ **AI Features Disabled**\n\n"
                    "Gemini AI is currently unavailable because GEMINI_API_KEY environment variable is not configured.\n\n"
                    "**To enable AI features:**\n"
                    "1. Get a Gemini API key from https://makersuite.google.com/app/apikey\n"
                    "2. Set it as GEMINI_API_KEY environment variable\n"
                    "3. Restart the bot"
                )
                logging.warning(f"⚠️ {message.from_user.first_name} tried to use /on but AI is disabled")
                self.emit_terminal(f'⚠️ AI unavailable - {message.from_user.first_name} tried /on')
                return

            chat_id = message.chat.id
            self.auto_reply_mode[chat_id] = True
            
            await message.reply_text(
                "✅ **Auto-Reply Mode ON**\n\n"
                "🤖 আমি এখন আপনার সব মেসেজে AI দিয়ে স্বয়ংক্রিয়ভাবে উত্তর দিব।\n\n"
                "💬 শুধু টেক্সট লিখলেই হবে, কোন কমান্ড লাগবে না।\n\n"
                "🛑 বন্ধ করতে: /off"
            )
            logging.info(f"✅ Auto-reply mode activated for {message.from_user.first_name}")
            self.emit_terminal(f'✅ Auto-reply ON for {message.from_user.first_name}')

        @self.client.on_message(filters.private & filters.incoming & filters.command("off"))
        async def handle_off_command(client, message: Message):
            chat_id = message.chat.id
            if chat_id in self.auto_reply_mode:
                del self.auto_reply_mode[chat_id]
                
                await message.reply_text(
                    "🛑 **Auto-Reply Mode OFF**\n\n"
                    "আমি আর স্বয়ংক্রিয়ভাবে উত্তর দিব না।\n\n"
                    "💡 এখন /gem কমান্ড ব্যবহার করে প্রশ্ন করতে পারবেন।\n"
                    "✅ আবার চালু করতে: /on"
                )
                logging.info(f"🛑 Auto-reply mode deactivated for {message.from_user.first_name}")
                self.emit_terminal(f'🛑 Auto-reply OFF for {message.from_user.first_name}')
            else:
                await message.reply_text(
                    "ℹ️ Auto-reply mode তো চালু নেই!\n\n"
                    "✅ চালু করতে: /on"
                )

        @self.client.on_message(filters.private & filters.incoming & filters.command("clear"))
        async def handle_clear_command(client, message: Message):
            chat_id = message.chat.id
            if chat_id in self.conversation_history:
                self.conversation_history[chat_id].clear()
                
                await message.reply_text("✅ **Conversation history cleared!**\n\nনতুন কথোপকথন শুরু হবে এখন থেকে। 🔄")
                logging.info(f"🗑️ Conversation history cleared for {message.from_user.first_name}")
                self.emit_terminal(f'🗑️ History cleared for {message.from_user.first_name}')
            else:
                await message.reply_text("ℹ️ কোন conversation history নেই এই chat এ।")

        @self.client.on_message(filters.private & filters.incoming & filters.regex(r"^/gem\b"))
        async def handle_gemini_command(client, message: Message):
            if not self.enabled:
                await message.reply_text(
                    "⚠️ **AI Features Disabled**\n\n"
                    "Gemini AI is currently unavailable because GEMINI_API_KEY environment variable is not configured.\n\n"
                    "**To enable AI features:**\n"
                    "1. Get a Gemini API key from https://makersuite.google.com/app/apikey\n"
                    "2. Set it as GEMINI_API_KEY environment variable\n"
                    "3. Restart the bot"
                )
                logging.warning(f"⚠️ {message.from_user.first_name} tried to use /gem but AI is disabled")
                self.emit_terminal(f'⚠️ AI unavailable - {message.from_user.first_name} tried /gem')
                return

            if message.text and message.text.startswith('/gem'):
                user_query = message.text[4:].strip()

                if not user_query:
                    await message.reply_text(
                        "❓ **ব্যবহার করার নিয়ম:**\n"
                        "/gem আপনার প্রশ্ন লিখুন\n\n"
                        "**উদাহরণ:**\n"
                        "/gem হাই, তুমি কেমন আছো?\n"
                        "/gem What is artificial intelligence?\n\n"
                        "💡 **Tip:** Auto-reply চালু করতে /on ব্যবহার করুন"
                    )
                    return

                logging.info(f"🤖 Gemini AI request from {message.from_user.first_name}: {user_query[:100]}")
                self.emit_terminal(f'🤖 Gemini AI processing: "{user_query[:50]}..."')

                await client.send_chat_action(message.chat.id, ChatAction.TYPING)

                try:
                    response_text = await self._call_gemini_api(user_query, message.chat.id)
                    await message.reply_text(response_text)
                    logging.info(f"✅ Gemini AI responded to {message.from_user.first_name}")
                    self.emit_terminal(f'✅ Gemini AI responded successfully to {message.from_user.first_name}')

                except Exception as e:
                    error_msg = f"❌ দুঃখিত, Gemini AI এ সমস্যা হয়েছে।\n\nError: {str(e)}"
                    logging.error(f"Gemini AI error: {e}", exc_info=True)
                    await message.reply_text(error_msg)
                    self.emit_terminal(f'❌ Gemini AI error: {str(e)}')

        @self.client.on_message(filters.private & filters.text & filters.incoming)
        async def handle_auto_reply(client, message: Message):
            chat_id = message.chat.id

            if message.text.startswith('/'):
                raise ContinuePropagation

            if chat_id not in self.auto_reply_mode:
                raise ContinuePropagation

            user = message.from_user
            user_query = message.text

            logging.info(f"🤖 Auto-reply mode active for {user.first_name}: {user_query[:100]}")
            self.emit_terminal(f'🤖 Auto-replying to {user.first_name}')

            await client.send_chat_action(chat_id, ChatAction.TYPING)

            try:
                response_text = await self._call_gemini_api(user_query, chat_id)
                await message.reply_text(response_text)
                logging.info(f"✅ Auto-replied to {user.first_name}")
                self.emit_terminal(f'✅ Auto-replied to {user.first_name}')

            except Exception as e:
                logging.error(f"Auto-reply error: {e}", exc_info=True)
                await message.reply_text("❌ দুঃখিত, AI উত্তর দিতে পারেনি। আবার চেষ্টা করুন।")

    async def _call_gemini_api(self, query: str, chat_id: int) -> str:
        if not self.api_url:
            logging.error("❌ Cannot call Gemini API: GEMINI_API_KEY not configured")
            raise Exception("Gemini API key not configured. Please set GEMINI_API_KEY environment variable.")

        if chat_id not in self.conversation_history:
            self.conversation_history[chat_id] = deque(maxlen=self.max_history_length)
            system_prompt = {
                "role": "user",
                "parts": [{
                    "text": "You are a helpful AI assistant. Language guidelines:\n"
                            "- If the user writes in Bengali (বাংলা) or uses English letters to write Bengali (Banglish/Roman Bengali), respond in Bengali (বাংলা script)\n"
                            "- If the user writes in English, respond in English\n"
                            "- If the user writes in any other language, respond in English\n"
                            "- Be natural, friendly, and helpful in your responses"
                }]
            }
            model_ack = {
                "role": "model",
                "parts": [{"text": "আমি বুঝেছি! আমি বাংলা বা ইংরেজিতে সাহায্য করতে পারি। কিভাবে সাহায্য করতে পারি?"}]
            }
            self.conversation_history[chat_id].append(system_prompt)
            self.conversation_history[chat_id].append(model_ack)

        user_message = {
            "role": "user",
            "parts": [{"text": query}]
        }
        self.conversation_history[chat_id].append(user_message)

        payload = {
            "contents": list(self.conversation_history[chat_id])
        }

        headers = {
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            if 'candidates' in data and len(data['candidates']) > 0:
                candidate = data['candidates'][0]
                if 'content' in candidate and 'parts' in candidate['content']:
                    parts = candidate['content']['parts']
                    if len(parts) > 0 and 'text' in parts[0]:
                        ai_response = parts[0]['text']

                        model_message = {
                            "role": "model",
                            "parts": [{"text": ai_response}]
                        }
                        self.conversation_history[chat_id].append(model_message)

                        return ai_response
            return "❌ দুঃখিত, Gemini থেকে সঠিক উত্তর পাওয়া যায়নি।"

        except requests.exceptions.Timeout:
            logging.error("Gemini API request timed out")
            return "⏱️ Request timeout হয়েছে। আবার চেষ্টা করুন।"

        except requests.exceptions.RequestException as e:
            logging.error(f"Gemini API request failed: {e}")
            return f"❌ API Error: Connection failed. Please check internet connection."

        except KeyError as e:
            logging.error(f"Gemini response parsing error: {e}")
            return "❌ Response parsing error. API response format may have changed."

        except Exception as e:
            logging.error(f"Unexpected error in Gemini API call: {e}", exc_info=True)
            return f"❌ Unexpected error: {str(e)}"

    def enable(self):
        self.enabled = True
        logging.info("Gemini AI module enabled")
        self.emit_terminal("✅ Gemini AI module enabled")

    def disable(self):
        self.enabled = False
        logging.info("Gemini AI module disabled")
        self.emit_terminal("🛑 Gemini AI module disabled")

    def cleanup(self):
        self.enabled = False
        self.conversation_history.clear()
        self.auto_reply_mode.clear()
        logging.info("Gemini AI module cleaned up")

import logging
from pyrogram import filters
from pyrogram.types import Message
from .base_module import BaseModule


class StartCommandModule(BaseModule):
    def __init__(self, client, socketio):
        super().__init__(client, socketio)
        self.welcome_message = (
            "👋 **স্বাগতম!**\n\n"
            "আমি একটি স্মার্ট Telegram Bot। আমার সাথে চ্যাট করুন!\n\n"
            "**Available Commands:**\n"
            "• `/gem [প্রশ্ন]` - Gemini AI এর সাথে কথা বলুন\n"
            "• `/start` - এই welcome message দেখুন\n\n"
            "**Features:**\n"
            "✨ Auto-reply system (normal messages এর জন্য)\n"
            "🤖 AI-powered responses\n\n"
            "এখনই ব্যবহার করুন এবং মজা করুন! 🚀"
        )
    
    def setup(self):
        start_filter = filters.private & filters.incoming & filters.regex(r"^/start\b")
        
        @self.client.on_message(start_filter)
        async def handle_start_command(client, message: Message):
            logging.info(f"▶️ /start command from {message.from_user.first_name} (ID: {message.from_user.id})")
            self.emit_terminal(f'▶️ /start command from {message.from_user.first_name}')
            
            try:
                await message.reply_text(
                    self.welcome_message,
                    disable_web_page_preview=True
                )
                
                logging.info(f"✅ Welcome message sent to {message.from_user.first_name}")
                self.emit_terminal(f'✅ Welcome message sent to {message.from_user.first_name}')
                
            except Exception as e:
                logging.error(f"Error sending welcome message: {e}", exc_info=True)
                self.emit_terminal(f'❌ Error sending welcome message: {str(e)}')
    
    def cleanup(self):
        """Cleanup resources."""
        logging.info("Start Command module cleaned up")

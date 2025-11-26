# 🤖 Telegram Bot Manager - Smart Auto-Reply & AI

একটি শক্তিশালী Telegram Userbot যা Smart Auto-Reply, AI Conversation এবং Modular Architecture সহ তৈরি।

## 🌐 Multi-User Support

**This bot supports multiple users simultaneously!** Each user can connect their own Telegram account by providing their API credentials through the web interface. See [MULTI_USER_GUIDE.md](MULTI_USER_GUIDE.md) for detailed instructions on how to use this system with multiple users.

---

## 📁 প্রজেক্ট স্ট্রাকচার

```
telegram-bot-manager/
│
├── main.py                    # Main Flask + Pyrogram server
├── requirements.txt           # Python dependencies
├── Procfile                   # Deployment configuration
├── README.md                  # এই ফাইল
├── replit.md                  # Replit project info
│
├── modules/                   # সব feature modules এখানে
│   ├── __init__.py           # Package initialization
│   ├── base_module.py        # Base class for all modules
│   ├── start.py              # /start command handler
│   ├── gemini_ai.py          # Gemini AI integration
│   └── smart_auto_reply.py   # Auto-reply + conversation mode
│
└── templates/                 # Web interface templates
    └── terminal.html          # Web terminal UI
```

---

## ⚙️ সিস্টেম Requirements

### Python Version
- Python 3.9 বা তার উপরে

### Dependencies
```txt
pyrogram==2.0.106          # Telegram MTProto API client
tgcrypto==1.2.5            # Fast cryptography for Pyrogram
flask==2.3.3               # Web framework
flask-socketio==5.3.6      # Real-time communication
eventlet==0.33.3           # Async networking library
python-dotenv==1.0.0       # Environment variables
ptyprocess==0.7.0          # Terminal process handling
gunicorn==21.2.0           # Production WSGI server
requests==2.31.0           # HTTP library for API calls
```

---

## 🚀 Installation Guide

### Step 1: Clone Repository
```bash
git clone <repository-url>
cd telegram-bot-manager
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Get Telegram API Credentials

#### 📌 API ID এবং API Hash পাওয়ার জন্য:

1. **https://my.telegram.org** এ যান
2. আপনার Phone Number দিয়ে Login করুন
3. **API Development Tools** এ ক্লিক করুন
4. নতুন Application তৈরি করুন:
   - **App title:** যেকোনো নাম (যেমন: My Userbot)
   - **Short name:** ছোট নাম (যেমন: mybot)
   - **Platform:** অন্যান্য (Other)
   - **Description:** (optional)

5. **Create Application** এ ক্লিক করুন

6. আপনি পাবেন:
   - **App api_id:** `12345678` (এরকম একটা নাম্বার)
   - **App api_hash:** `abcdef1234567890abcdef1234567890` (32 characters)

⚠️ **গুরুত্বপূর্ণ:** এই credentials কাউকে শেয়ার করবেন না!

### Step 4: Get Gemini API Key (AI এর জন্য)

1. **https://makersuite.google.com/app/apikey** এ যান
2. **Create API Key** এ ক্লিক করুন
3. API Key কপি করুন (যেমন: `AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXX`)


### Step 5: Run Bot
```bash
python main.py
```

---

## 🔧 নতুন Module যোগ করার ধাপ

নিচের **৩টি সহজ ধাপ** অনুসরণ করুন:

### ধাপ ১: Module File তৈরি করুন

`modules/` ফোল্ডারে নতুন Python file তৈরি করুন (যেমন: `my_module.py`)

**Template:**

```python
import logging
from pyrogram import filters
from pyrogram.types import Message
from .base_module import BaseModule


class MyCustomModule(BaseModule):
    """আপনার module এর বর্ণনা এখানে"""
    
    def __init__(self, client, socketio):
        super().__init__(client, socketio)
        # আপনার variables এখানে
        self.my_data = {}
    
    def setup(self):
        """Message handlers register করুন"""
        
        @self.client.on_message(filters.command("mycommand") & filters.private)
        async def handle_my_command(client, message: Message):
            # Terminal এ log দেখান
            self.emit_terminal('⚙️ Processing /mycommand')
            
            # আপনার কাজ করুন
            response = "Hello from my module!"
            
            # Reply পাঠান
            await message.reply_text(response)
            
            # Success log
            logging.info("✅ Command executed")
            self.emit_terminal('✅ Done')
    
    def cleanup(self):
        """Module বন্ধ হওয়ার সময় cleanup"""
        self.my_data.clear()
        logging.info(f"{self.name} cleaned up")
```

---

### ধাপ ২: Module Load করুন

`main.py` → `TelegramBotManager` class → `load_modules()` method এ যোগ করুন:

```python
def load_modules(self):
    """Load and setup all feature modules."""
    from modules.smart_auto_reply import SmartAutoReplyModule
    from modules.gemini_ai import GeminiAIModule
    from modules.start import StartCommandModule
    from modules.my_module import MyCustomModule  # ← নতুন import
    
    # Load Start Command module
    start_cmd = StartCommandModule(self.client, socketio)
    start_cmd.setup()
    self.modules.append(start_cmd)
    logging.info(f"✅ Loaded module: {start_cmd.name}")
    
    # Load Gemini AI module
    gemini_ai = GeminiAIModule(self.client, socketio)
    gemini_ai.setup()
    self.modules.append(gemini_ai)
    logging.info(f"✅ Loaded module: {gemini_ai.name}")
    
    # Load Smart Auto Reply module
    smart_auto_reply = SmartAutoReplyModule(self.client, socketio)
    smart_auto_reply.setup()
    self.modules.append(smart_auto_reply)
    logging.info(f"✅ Loaded module: {smart_auto_reply.name}")
    
    # Load YOUR module ← নতুন code
    my_module = MyCustomModule(self.client, socketio)
    my_module.setup()
    self.modules.append(my_module)
    logging.info(f"✅ Loaded module: {my_module.name}")
```

---

### ধাপ ৩: Test করুন

1. **Bot Restart করুন**
   ```bash
   python main.py
   ```

2. **Terminal এ চেক করুন**
   ```
   ✅ Loaded module: MyCustomModule
   ```

3. **Telegram এ Test করুন**
   - Command পাঠান (যেমন: `/mycommand`)
   - Expected output দেখুন

---

## 📚 Module Development Tips

### BaseModule থেকে পাবেন:

```python
# Terminal এ message দেখান
self.emit_terminal('✅ Success message')

# Module এর নাম পান
self.name  # Returns: "MyCustomModule"

# Client access করুন
self.client  # Pyrogram client instance

# SocketIO access করুন
self.socketio  # Flask-SocketIO instance
```

### Pyrogram Filters (Common):

```python
filters.private          # শুধু private chat
filters.group            # শুধু group chat
filters.incoming         # অন্যদের message
filters.outgoing         # আপনার message
filters.text             # শুধু text message
filters.command("start") # /start command
filters.mentioned        # আপনাকে mention করলে

# Multiple filters একসাথে
filters.private & filters.incoming & filters.text
```

---

## ⚠️ Important Notes

### ✅ DO:
- `BaseModule` থেকে inherit করুন
- `setup()` method implement করুন
- Error handling যোগ করুন
- `self.emit_terminal()` ব্যবহার করুন
- Conversation history manage করুন

### ❌ DON'T:
- Global variables ব্যবহার করবেন না
- API keys hardcode করবেন না (production এ)
- Module এর মধ্যে dependency তৈরি করবেন না
- Exception handling ছাড়া API call করবেন না

---

## 📖 API Documentation

### Telegram API
- **Pyrogram:** https://docs.pyrogram.org/

### AI API
- **Gemini AI:** https://ai.google.dev/

---

## 🎉 সমাপ্তি

এই bot সম্পূর্ণ **modular এবং extensible**। আপনি সহজেই নতুন features যোগ করতে পারবেন!

**Happy Coding! 🚀**

---

**Version:** 2.0.0  
**Last Updated:** November 2025  
**License:** MIT

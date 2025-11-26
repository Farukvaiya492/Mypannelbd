import os
import subprocess
import threading
import asyncio
import logging
import queue
import zipfile
import io
import shutil
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from flask_socketio import SocketIO, emit
from functools import wraps
from pyrogram import Client, filters
from pyrogram.types import Message


logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())

socketio = SocketIO(app, async_mode='threading')

port = int(os.environ.get("PORT", "5000"))
logging.info(f"✅ Using port: {port}")

ADMIN_PASSWORD = "sneha"

active_processes = {}
active_bots = {}

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/')
def index():
    return render_template('terminal.html')

@app.route('/tutorial')
def tutorial():
    return render_template('tutorial.html')

@app.route('/api/video/tutorial')
def stream_tutorial_video():
    video_path = os.path.join(app.root_path, 'templates', 'How to Get API Id API Hash Of a Telegram Account.mp4')
    
    if not os.path.exists(video_path):
        return jsonify({"error": "Video file not found"}), 404
    
    return send_file(
        video_path,
        mimetype='video/mp4',
        as_attachment=False,
        download_name='telegram_api_tutorial.mp4'
    )

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('output', {'data': '🚀 Web Terminal Connected! Use the forms to manage the Telegram Bot.\n'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('execute')
def handle_execute(data):
    command = data['command']
    session_id = request.sid
    
    # Handle simple internal commands
    if command.lower() == 'help':
        help_text = """
Available Terminal Commands:
----------------------------
help        - Show this help message.
ls, pwd, etc. - Executes basic shell commands (output will be shown here).
"""
        socketio.emit('output', {'data': help_text}, room=session_id)
        return

    print(f'Executing command: {command}')
    
    def send_output(data):
        socketio.emit('output', {'data': data}, room=session_id)
    def run_command(cmd, sid):
        try:
            process = subprocess.Popen(
                cmd, 
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            active_processes[sid] = process
            
            for line in iter(process.stdout.readline, ''):
                if not line:
                    break
                send_output(line)
                
            process.stdout.close()
            return_code = process.wait()
            
            if return_code == 0:
                send_output('\n✅ Command executed successfully\n')
            else:
                send_output(f'\n❌ Command failed with return code {return_code}\n')
                
        except Exception as e:
            send_output(f'\n💥 Error running command: {str(e)}\n')
            
        finally:
            if sid in active_processes:
                del active_processes[sid]

    threading.Thread(target=run_command, args=(command, session_id), daemon=True).start()


@socketio.on('interrupt')
def handle_interrupt():
    session_id = request.sid
    if session_id in active_processes:
        active_processes[session_id].terminate()
        emit('output', {'data': '\n🛑 Process interrupted\n'})

_async_loop = None
_async_thread = None

def get_async_loop():
    """Get or create the persistent async event loop."""
    global _async_loop, _async_thread
    if _async_loop is None or not _async_loop.is_running():
        _async_loop = asyncio.new_event_loop()
        _async_thread = threading.Thread(target=_async_loop.run_forever, daemon=True)
        _async_thread.start()
        logging.info("Created persistent event loop for async operations")
    return _async_loop

class TelegramBotManager:
    """Manages a Pyrogram Client instance and feature modules."""
    def __init__(self, api_id, api_hash, phone_number):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.session_name = f"session_{phone_number.replace('+', '')}"
        self.client = None
        self.is_running = False
        self.phone_code_hash = None
        self.awaiting_code = False
        self.awaiting_password = False
        self.loop = get_async_loop() 
        self.modules = []
        self.user_info = {
            "username": None,
            "first_name": None,
            "last_name": None,
            "user_id": None
        }  
        
    def update_user_info(self, me):
        """Update user info from Telegram user object."""
        self.user_info = {
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "user_id": me.id
        }
    
    async def initialize_bot(self):
        """Initializes the Pyrogram client."""
        self.client = Client(
            self.session_name,
            api_id=int(self.api_id),
            api_hash=self.api_hash,
            workdir="session"
        )
        
        return self.client
    
    def load_modules(self):
        """Load and setup all feature modules."""
        from modules.smart_auto_reply import SmartAutoReplyModule
        from modules.gemini_ai import GeminiAIModule
        from modules.start import StartCommandModule
        
        # Load Start Command module first (highest priority)
        start_cmd = StartCommandModule(self.client, socketio)
        start_cmd.setup()
        self.modules.append(start_cmd)
        logging.info(f"✅ Loaded module: {start_cmd.name}")
        
        # Load Gemini AI module (for /gem command)
        gemini_ai = GeminiAIModule(self.client, socketio)
        gemini_ai.setup()
        self.modules.append(gemini_ai)
        logging.info(f"✅ Loaded module: {gemini_ai.name}")
        
        # Load Smart Auto Reply module last (handles online/offline + conversation mode)
        smart_auto_reply = SmartAutoReplyModule(self.client, socketio)
        smart_auto_reply.setup()
        self.modules.append(smart_auto_reply)
        logging.info(f"✅ Loaded module: {smart_auto_reply.name}")
        
    
    def unload_modules(self):
        """Unload all modules and cleanup."""
        for module in self.modules:
            try:
                module.cleanup()
                logging.info(f"✅ Unloaded module: {module.name}")
            except Exception as e:
                logging.error(f"Error unloading module {module.name}: {e}")
        self.modules.clear()
    
    async def start_bot(self, verification_code=None, password=None):
        """Starts the Pyrogram client using start() method."""
        from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired
        
        try:
            if self.is_running and self.client:
                try:
                    me = await self.client.get_me()
                    self.update_user_info(me)
                    return {"status": "success", "message": f"✅ Bot is already running as {me.first_name}"}
                except:
                    self.is_running = False

            if not self.client:
                await self.initialize_bot()

            try:
                await self.client.start()
                self.is_running = True
                me = await self.client.get_me()
                self.update_user_info(me)
                
                self.load_modules()
                
                logging.info(f"✅ Bot is now actively running and listening for messages")
                return {
                    "status": "success",
                    "message": f"✅ Bot started successfully as @{me.username if me.username else me.first_name} (ID: {me.id})"
                }
            except:
                pass
            
            if not self.client.is_connected:
                try:
                    await self.client.connect()
                except ConnectionError:
                    pass

            try:
                me = await self.client.get_me()
                self.is_running = True
                self.update_user_info(me)
                
                # Load feature modules
                self.load_modules()
                
                logging.info(f"✅ Bot is now actively running and listening for messages")
                return {
                    "status": "success",
                    "message": f"✅ Bot started successfully as @{me.username if me.username else me.first_name} (ID: {me.id})"
                }
            except:
                pass
            
            if not self.phone_code_hash and not verification_code:
                logging.info(f"Sending verification code to {self.phone_number}")
                sent_code = await self.client.send_code(self.phone_number)
                self.phone_code_hash = sent_code.phone_code_hash
                self.awaiting_code = True
                return {
                    "status": "code_sent",
                    "message": f"📱 Verification code sent to {self.phone_number}. Please enter the code."
                }
            
            if verification_code and self.phone_code_hash:
                logging.info(f"Attempting sign in for {self.phone_number}")
                try:
                    await self.client.sign_in(
                        self.phone_number,
                        self.phone_code_hash,
                        verification_code
                    )
                    self.awaiting_code = False
                    self.is_running = True
                    me = await self.client.get_me()
                    self.update_user_info(me)
                    
                    self.load_modules()
                    
                    return {
                        "status": "success",
                        "message": f"✅ Bot started successfully as @{me.username if me.username else me.first_name} (ID: {me.id})"
                    }
                except SessionPasswordNeeded:
                    self.awaiting_password = True
                    return {
                        "status": "password_required",
                        "message": "🔐 2FA is enabled. Please enter your password."
                    }
                except (PhoneCodeInvalid, PhoneCodeExpired) as e:
                    self.phone_code_hash = None
                    self.awaiting_code = False
                    return {
                        "status": "error",
                        "message": f"❌ {type(e).__name__}: Invalid or expired code. Please try again."
                    }
            
            if password and self.awaiting_password:
                logging.info(f"Checking 2FA password for {self.phone_number}")
                await self.client.check_password(password)
                self.awaiting_password = False
                self.is_running = True
                me = await self.client.get_me()
                self.update_user_info(me)
                
                self.load_modules()
                
                return {
                    "status": "success",
                    "message": f"✅ Bot started successfully as @{me.username if me.username else me.first_name} (ID: {me.id})"
                }

            return {"status": "error", "message": "❌ Unexpected state in auth flow"}
                
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            logging.error(f"Bot start error: {error_detail}")
            return {"status": "error", "message": f"❌ Login or start failed: {type(e).__name__}: {str(e)}"}

    async def stop_bot(self):
        """Stops the Pyrogram client and unloads modules."""
        if self.is_running and self.client:
            self.unload_modules()
            
            await self.client.stop()
            self.is_running = False
            self.client = None  
            return {"status": "success", "message": "🛑 Bot stopped."}
        return {"status": "error", "message": "Bot is not running."}


def run_async_task(manager, task_name, verification_code=None, password=None):
    """Utility to run an async method using the persistent event loop."""
    logging.info(f"Starting async task: {task_name} for phone {manager.phone_number}")
    
    if task_name == 'start':
        coro = manager.start_bot(verification_code=verification_code, password=password)
    elif task_name == 'stop':
        coro = manager.stop_bot()
    else:
        msg = {"status": "error", "message": "Invalid task"}
        logging.error(f"Invalid task: {task_name}")
        socketio.emit('bot_management_result', msg)
        return

    try:
        logging.info(f"Executing {task_name} task...")
        future = asyncio.run_coroutine_threadsafe(coro, manager.loop)
        result = future.result(timeout=60)
        logging.info(f"Task {task_name} completed with result: {result}")
        socketio.emit('bot_management_result', result)
        
    except Exception as e:
        error_msg = f"Thread exception: {type(e).__name__}: {str(e)}"
        logging.error(f"Error in {task_name} task: {error_msg}", exc_info=True)
        socketio.emit('bot_management_result', {"status": "error", "message": error_msg})

@app.route('/api/bot/start', methods=['POST'])
def start_bot_route():
    data = request.json
    api_id = data.get('api_id')
    api_hash = data.get('api_hash')
    phone_number = data.get('phone_number')
    verification_code = data.get('verification_code')
    password = data.get('password')
    
    if not all([api_id, api_hash, phone_number]):
        return jsonify({"status": "error", "message": "Missing API ID, Hash, or Phone Number."}), 400
    
    bot_id = f"{phone_number}_{api_id}"
    if bot_id not in active_bots:
        active_bots[bot_id] = TelegramBotManager(api_id, api_hash, phone_number)
    
    manager = active_bots[bot_id]
    threading.Thread(target=run_async_task, args=(manager, 'start', verification_code, password), daemon=True).start()
    
    return jsonify({"status": "starting", "message": f"Bot startup initiated for {phone_number}. Check terminal for status."})


@app.route('/api/bot/stop', methods=['POST'])
def stop_bot_route():
    data = request.json
    phone_number = data.get('phone_number')
    api_id = data.get('api_id')
    bot_id = f"{phone_number}_{api_id}"
    
    if bot_id not in active_bots:
        return jsonify({"status": "error", "message": "Bot instance not found."})

    manager = active_bots[bot_id]
    
    threading.Thread(target=run_async_task, args=(manager, 'stop'), daemon=True).start()
    
    return jsonify({"status": "stopping", "message": f"Bot shutdown initiated for {phone_number}. Check terminal for status."})


@app.route('/api/bot/status', methods=['GET'])
def bot_status():
    status_list = []
    for bot_id, bot_manager in active_bots.items():
        display_name = (
            f"@{bot_manager.user_info['username']}" if bot_manager.user_info.get('username') else
            bot_manager.user_info.get('first_name') or
            bot_manager.user_info.get('last_name') or
            f"ID: {bot_manager.user_info.get('user_id')}" if bot_manager.user_info.get('user_id') else
            "Unknown User"
        )
        
        status_list.append({
            "bot_id": bot_id,
            "is_running": bot_manager.is_running,
            "display_name": display_name
        })
    
    return jsonify({"bots": status_list})


@app.route('/admin')
def admin_page():
    """Render the admin panel for session management."""
    if not session.get('admin_logged_in'):
        return render_template('admin_login.html')
    return render_template('admin.html')


@app.route('/admin/login', methods=['POST'])
def admin_login():
    """Handle admin login."""
    data = request.json
    password = data.get('password')
    
    if password == ADMIN_PASSWORD:
        session['admin_logged_in'] = True
        return jsonify({"status": "success", "message": "Login successful"})
    else:
        return jsonify({"status": "error", "message": "Invalid password"}), 401


@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    """Handle admin logout."""
    session.pop('admin_logged_in', None)
    return jsonify({"status": "success", "message": "Logged out"})


@app.route('/api/admin/sessions/list', methods=['GET'])
@admin_required
def list_sessions():
    """List all session files in the session directory."""
    try:
        session_dir = 'session'
        if not os.path.exists(session_dir):
            os.makedirs(session_dir)
            return jsonify({"sessions": []})
        
        sessions = []
        for filename in os.listdir(session_dir):
            if filename.endswith('.session') or filename.endswith('.session-journal'):
                filepath = os.path.join(session_dir, filename)
                file_size = os.path.getsize(filepath)
                size_kb = file_size / 1024
                sessions.append({
                    "name": filename,
                    "size": f"{size_kb:.2f} KB"
                })
        
        return jsonify({"sessions": sessions})
    except Exception as e:
        logging.error(f"Error listing sessions: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/sessions/download', methods=['GET'])
@admin_required
def download_sessions():
    """Download all session files as a ZIP archive."""
    try:
        session_dir = 'session'
        if not os.path.exists(session_dir):
            return jsonify({"error": "Session directory not found"}), 404
        
        memory_file = io.BytesIO()
        
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filename in os.listdir(session_dir):
                if filename.endswith('.session') or filename.endswith('.session-journal'):
                    filepath = os.path.join(session_dir, filename)
                    zipf.write(filepath, filename)
        
        memory_file.seek(0)
        
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name='sessions_backup.zip'
        )
    except Exception as e:
        logging.error(f"Error downloading sessions: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/admin/sessions/upload', methods=['POST'])
@admin_required
def upload_sessions():
    """Upload and replace all session files from a ZIP archive."""
    try:
        if 'sessions' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['sessions']
        
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        if not file.filename.endswith('.zip'):
            return jsonify({"error": "Only ZIP files are allowed"}), 400
        
        session_dir = 'session'
        
        if os.path.exists(session_dir):
            for filename in os.listdir(session_dir):
                if filename.endswith('.session') or filename.endswith('.session-journal'):
                    os.remove(os.path.join(session_dir, filename))
        else:
            os.makedirs(session_dir)
        
        with zipfile.ZipFile(file, 'r') as zip_ref:
            for member in zip_ref.namelist():
                if member.endswith('.session') or member.endswith('.session-journal'):
                    member_path = os.path.normpath(member)
                    if member_path.startswith('..') or os.path.isabs(member_path):
                        logging.warning(f"Skipping suspicious path: {member}")
                        continue
                    
                    target_path = os.path.join(session_dir, os.path.basename(member_path))
                    target_path = os.path.realpath(target_path)
                    session_dir_real = os.path.realpath(session_dir)
                    
                    if not target_path.startswith(session_dir_real + os.sep):
                        logging.warning(f"Path traversal attempt detected: {member}")
                        continue
                    
                    with zip_ref.open(member) as source, open(target_path, 'wb') as target:
                        shutil.copyfileobj(source, target)
        
        return jsonify({"message": "Sessions uploaded and replaced successfully"}), 200
    except Exception as e:
        logging.error(f"Error uploading sessions: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    logging.info(f"Flask-SocketIO server starting on http://0.0.0.0:{port}")
    try:
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=False,
            allow_unsafe_werkzeug=True,
        )
    except Exception as e:
        logging.error(f"Failed to start server: {e}")

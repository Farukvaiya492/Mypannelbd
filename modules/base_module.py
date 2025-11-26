from abc import ABC, abstractmethod
from pyrogram import Client
from flask_socketio import SocketIO


class BaseModule(ABC):
    def __init__(self, client: Client, socketio: SocketIO):
        self.client = client
        self.socketio = socketio
        self.name = self.__class__.__name__
    
    @abstractmethod
    def setup(self):
        pass
    
    def cleanup(self):
        pass
    
    def emit_terminal(self, message: str):
        self.socketio.emit('output', {'data': f'{message}\n'})

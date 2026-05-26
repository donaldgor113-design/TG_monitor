# client.py
from telethon import TelegramClient
from config import API_ID, API_HASH

userbot = TelegramClient("monitor_session", API_ID, API_HASH)
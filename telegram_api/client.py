import os
from telethon.sync import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telegram_api import config

# Absolute path — session file is always in the project root regardless of CWD
SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "telegram_session")


class TelegramClientWrapper:
    """Wraps Telethon for send/receive as a regular user account."""

    def __init__(self):
        self._client = TelegramClient(SESSION_FILE, config.API_ID, config.API_HASH)

    def connect(self, otp_callback=None, password_callback=None):
        """Connect and authenticate.
        The verification code arrives as a message in your Telegram app
        from the official 'Telegram' account — same place as when you log
        into Telegram Web."""
        self._client.connect()
        if not self._client.is_user_authorized():
            try:
                self._client.send_code_request(config.PHONE)
            except FloodWaitError as e:
                raise RuntimeError(
                    f"Too many attempts. Wait {e.seconds} seconds (~{e.seconds // 60} min) and try again."
                ) from e

            if otp_callback:
                code = otp_callback()
            else:
                code = input("Enter the 5-digit code from the Telegram app: ").strip()

            try:
                self._client.sign_in(config.PHONE, code)
            except SessionPasswordNeededError:
                if password_callback:
                    password = password_callback()
                else:
                    password = input("Two-step verification password: ").strip()
                self._client.sign_in(password=password)

    def disconnect(self):
        self._client.disconnect()

    def send_message(self, text: str, target: str = None) -> None:
        self._client.send_message(target or config.TARGET, text)

    def get_last_bot_message(self, target: str = None) -> dict:
        """Return the last message sent BY the bot (not by us)."""
        messages = self._client.get_messages(target or config.TARGET, limit=20)
        me = self._client.get_me()
        for msg in messages:
            if msg.sender_id != me.id and msg.text:
                return {
                    "sender": getattr(msg.sender, "username", "") or getattr(msg.sender, "first_name", ""),
                    "text": msg.text or "",
                    "date": msg.date.strftime("%Y-%m-%d %H:%M:%S") if msg.date else "",
                }
        return {"sender": "", "text": "", "date": ""}

    def get_bot_buttons(self, target: str = None) -> list[str]:
        """Return flat list of button labels from the last bot message."""
        messages = self._client.get_messages(target or config.TARGET, limit=5)
        for msg in messages:
            if msg.buttons:
                labels = []
                for row in msg.buttons:
                    for btn in row:
                        if btn.text:
                            labels.append(btn.text)
                return labels
        return []

    def click_button(self, label: str, target: str = None) -> None:
        """Click an inline keyboard button by its label text."""
        messages = self._client.get_messages(target or config.TARGET, limit=5)
        for msg in messages:
            if msg.buttons:
                for row in msg.buttons:
                    for btn in row:
                        if btn.text == label:
                            btn.click()
                            return
        # Fallback for ReplyKeyboard — send as plain text
        self._client.send_message(target or config.TARGET, label)

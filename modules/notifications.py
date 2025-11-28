"""
Telegram notification helpers for the bot.
"""

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Optional

from . import config

logger = logging.getLogger("OgameBot")


class TelegramNotifier:
    """Thin wrapper around Telegram Bot API."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        enabled: Optional[bool] = None,
        timeout: int = 10,
    ):
        self.bot_token = bot_token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = str(chat_id or config.TELEGRAM_CHAT_ID or "")
        self.enabled = config.TELEGRAM_ENABLED if enabled is None else bool(enabled)
        self.timeout = timeout

    def send(self, message: str, chat_id: Optional[str] = None, disable_notification: bool = False) -> bool:
        """Send a Telegram message. Returns True on success."""
        if not self.enabled:
            return False

        token = self.bot_token or config.TELEGRAM_BOT_TOKEN
        target_chat = str(chat_id or self.chat_id or config.TELEGRAM_CHAT_ID or "")

        if not token or not target_chat:
            logger.debug("Telegram send skipped (missing token/chat id).")
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": message,
            "disable_web_page_preview": True,
            "disable_notification": disable_notification,
        }

        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return 200 <= getattr(resp, "status", 500) < 300
        except urllib.error.HTTPError as exc:
            logger.warning(f"Telegram API HTTP error {exc.code}: {exc.reason}")
        except Exception as exc:
            logger.warning(f"Telegram API request failed: {exc}")

        return False

    def send_error(self, message: str, chat_id: Optional[str] = None) -> bool:
        """Send an error notification with a standard prefix."""
        prefixed = f"[OgameX Bot] {message}"
        return self.send(prefixed, chat_id=chat_id, disable_notification=False)


class TelegramLogHandler(logging.Handler):
    """Logging handler that ships ERROR logs to Telegram with a cooldown."""

    def __init__(self, notifier: Optional[TelegramNotifier] = None, cooldown_seconds: int = 120):
        super().__init__(level=logging.ERROR)
        self.notifier = notifier or TelegramNotifier()
        self.cooldown_seconds = cooldown_seconds
        self._last_sent_ts = 0.0

    def emit(self, record: logging.LogRecord):
        if record.levelno < logging.ERROR:
            return

        now = time.time()
        if now - self._last_sent_ts < self.cooldown_seconds:
            return

        try:
            msg = self.format(record)
            text = f"Alerta no bot OgameX:\n{msg}"
            if self.notifier.send_error(text):
                self._last_sent_ts = now
        except Exception:
            # Do not break logging pipeline if Telegram fails
            self.handleError(record)

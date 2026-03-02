"""
Telegram Bot Module
Provides remote control of the OgameX bot via Telegram commands.
"""

import asyncio
import logging
import threading
from typing import Optional, Callable, Dict, Any

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from . import config

logger = logging.getLogger("OgameBot")


class TelegramBotController:
    """
    Telegram Bot for remote control of OgameX bot features.
    
    Supported commands:
    /status - Show current bot status
    /start_asteroid - Start asteroid miner
    /stop_asteroid - Stop asteroid miner
    /start_expedition - Start expedition mode
    /stop_expedition - Stop expedition mode
    /start_farmer - Start farmer mode
    /stop_farmer - Stop farmer mode
    /help - Show available commands
    """

    def __init__(self):
        self.application: Optional[Application] = None
        self.thread: Optional[threading.Thread] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.running = False
        
        # Callbacks to be set by the main application
        self._get_status_cb: Optional[Callable[[], Dict[str, Any]]] = None
        self._start_asteroid_cb: Optional[Callable[[], bool]] = None
        self._stop_asteroid_cb: Optional[Callable[[], bool]] = None
        self._start_expedition_cb: Optional[Callable[[], bool]] = None
        self._stop_expedition_cb: Optional[Callable[[], bool]] = None
        self._start_farmer_cb: Optional[Callable[[], bool]] = None
        self._stop_farmer_cb: Optional[Callable[[], bool]] = None

    def set_callbacks(
        self,
        get_status: Callable[[], Dict[str, Any]],
        start_asteroid: Callable[[], bool],
        stop_asteroid: Callable[[], bool],
        start_expedition: Callable[[], bool],
        stop_expedition: Callable[[], bool],
        start_farmer: Callable[[], bool],
        stop_farmer: Callable[[], bool],
    ):
        """Set callback functions for bot control."""
        self._get_status_cb = get_status
        self._start_asteroid_cb = start_asteroid
        self._stop_asteroid_cb = stop_asteroid
        self._start_expedition_cb = start_expedition
        self._stop_expedition_cb = stop_expedition
        self._start_farmer_cb = start_farmer
        self._stop_farmer_cb = stop_farmer

    def _is_authorized(self, update: Update) -> bool:
        """Check if the user is authorized to use commands."""
        if not update.effective_chat:
            return False
        
        chat_id = str(update.effective_chat.id)
        allowed_chat_id = str(config.TELEGRAM_CHAT_ID or "")
        
        if not allowed_chat_id:
            # If no chat ID configured, allow any user (not recommended)
            logger.warning("TELEGRAM_CHAT_ID not configured - allowing all users")
            return True
        
        return chat_id == allowed_chat_id

    async def _unauthorized_response(self, update: Update):
        """Send unauthorized message."""
        if update.message:
            await update.message.reply_text(
                "⛔ Acesso negado. Seu chat ID não está autorizado."
            )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self._is_authorized(update):
            await self._unauthorized_response(update)
            return

        if update.message:
            await update.message.reply_text(
                "🤖 *OgameX Bot Controller*\n\n"
                "Use /help para ver os comandos disponíveis.",
                parse_mode="Markdown"
            )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        if not self._is_authorized(update):
            await self._unauthorized_response(update)
            return

        help_text = """🤖 *Comandos Disponíveis*

📊 *Status*
/status - Ver status atual do bot

⛏️ *Asteroid Miner*
/start\\_asteroid - Iniciar mineração
/stop\\_asteroid - Parar mineração

🚀 *Expedition*
/start\\_expedition - Iniciar expedições
/stop\\_expedition - Parar expedições

🌾 *Farmer*
/start\\_farmer - Iniciar farmer
/stop\\_farmer - Parar farmer

ℹ️ /help - Mostrar esta ajuda"""

        if update.message:
            await update.message.reply_text(help_text, parse_mode="Markdown")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        if not self._is_authorized(update):
            await self._unauthorized_response(update)
            return

        if not self._get_status_cb:
            if update.message:
                await update.message.reply_text("❌ Status callback não configurado")
            return

        try:
            status = self._get_status_cb()
            
            bot_running = "🟢 Rodando" if status.get("bot_running", False) else "🔴 Parado"
            asteroid = "🟢 Ativo" if status.get("asteroid_enabled", False) else "⚫ Inativo"
            expedition = "🟢 Ativo" if status.get("expedition_enabled", False) else "⚫ Inativo"
            farmer = "🟢 Ativo" if status.get("farmer_enabled", False) else "⚫ Inativo"
            
            cooldowns = status.get("active_cooldowns", 0)
            
            status_text = f"""📊 *Status do Bot*

🤖 Bot: {bot_running}

⛏️ Asteroid Miner: {asteroid}
🚀 Expedition: {expedition}
🌾 Farmer: {farmer}

⏱️ Cooldowns ativos: {cooldowns}"""

            if update.message:
                await update.message.reply_text(status_text, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            if update.message:
                await update.message.reply_text(f"❌ Erro ao obter status: {e}")

    async def cmd_start_asteroid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start_asteroid command."""
        if not self._is_authorized(update):
            await self._unauthorized_response(update)
            return

        if not self._start_asteroid_cb:
            if update.message:
                await update.message.reply_text("❌ Callback não configurado")
            return

        try:
            success = self._start_asteroid_cb()
            if success:
                if update.message:
                    await update.message.reply_text("✅ Asteroid Miner iniciado!")
            else:
                if update.message:
                    await update.message.reply_text("⚠️ Não foi possível iniciar o Asteroid Miner")
        except Exception as e:
            logger.error(f"Error starting asteroid miner: {e}")
            if update.message:
                await update.message.reply_text(f"❌ Erro: {e}")

    async def cmd_stop_asteroid(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop_asteroid command."""
        if not self._is_authorized(update):
            await self._unauthorized_response(update)
            return

        if not self._stop_asteroid_cb:
            if update.message:
                await update.message.reply_text("❌ Callback não configurado")
            return

        try:
            success = self._stop_asteroid_cb()
            if success:
                if update.message:
                    await update.message.reply_text("✅ Asteroid Miner parado!")
            else:
                if update.message:
                    await update.message.reply_text("⚠️ Não foi possível parar o Asteroid Miner")
        except Exception as e:
            logger.error(f"Error stopping asteroid miner: {e}")
            if update.message:
                await update.message.reply_text(f"❌ Erro: {e}")

    async def cmd_start_expedition(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start_expedition command."""
        if not self._is_authorized(update):
            await self._unauthorized_response(update)
            return

        if not self._start_expedition_cb:
            if update.message:
                await update.message.reply_text("❌ Callback não configurado")
            return

        try:
            success = self._start_expedition_cb()
            if success:
                if update.message:
                    await update.message.reply_text("✅ Expedition mode iniciado!")
            else:
                if update.message:
                    await update.message.reply_text("⚠️ Não foi possível iniciar o Expedition mode")
        except Exception as e:
            logger.error(f"Error starting expedition mode: {e}")
            if update.message:
                await update.message.reply_text(f"❌ Erro: {e}")

    async def cmd_stop_expedition(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop_expedition command."""
        if not self._is_authorized(update):
            await self._unauthorized_response(update)
            return

        if not self._stop_expedition_cb:
            if update.message:
                await update.message.reply_text("❌ Callback não configurado")
            return

        try:
            success = self._stop_expedition_cb()
            if success:
                if update.message:
                    await update.message.reply_text("✅ Expedition mode parado!")
            else:
                if update.message:
                    await update.message.reply_text("⚠️ Não foi possível parar o Expedition mode")
        except Exception as e:
            logger.error(f"Error stopping expedition mode: {e}")
            if update.message:
                await update.message.reply_text(f"❌ Erro: {e}")

    async def cmd_start_farmer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start_farmer command."""
        if not self._is_authorized(update):
            await self._unauthorized_response(update)
            return

        if not self._start_farmer_cb:
            if update.message:
                await update.message.reply_text("❌ Callback não configurado")
            return

        try:
            success = self._start_farmer_cb()
            if success:
                if update.message:
                    await update.message.reply_text("✅ Farmer mode iniciado!")
            else:
                if update.message:
                    await update.message.reply_text("⚠️ Não foi possível iniciar o Farmer mode")
        except Exception as e:
            logger.error(f"Error starting farmer mode: {e}")
            if update.message:
                await update.message.reply_text(f"❌ Erro: {e}")

    async def cmd_stop_farmer(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop_farmer command."""
        if not self._is_authorized(update):
            await self._unauthorized_response(update)
            return

        if not self._stop_farmer_cb:
            if update.message:
                await update.message.reply_text("❌ Callback não configurado")
            return

        try:
            success = self._stop_farmer_cb()
            if success:
                if update.message:
                    await update.message.reply_text("✅ Farmer mode parado!")
            else:
                if update.message:
                    await update.message.reply_text("⚠️ Não foi possível parar o Farmer mode")
        except Exception as e:
            logger.error(f"Error stopping farmer mode: {e}")
            if update.message:
                await update.message.reply_text(f"❌ Erro: {e}")

    async def _run_polling(self):
        """Run the Telegram bot polling loop."""
        token = config.TELEGRAM_BOT_TOKEN
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN not configured - Telegram bot disabled")
            return

        try:
            self.application = Application.builder().token(token).build()

            # Register command handlers
            self.application.add_handler(CommandHandler("start", self.cmd_start))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            self.application.add_handler(CommandHandler("status", self.cmd_status))
            self.application.add_handler(CommandHandler("start_asteroid", self.cmd_start_asteroid))
            self.application.add_handler(CommandHandler("stop_asteroid", self.cmd_stop_asteroid))
            self.application.add_handler(CommandHandler("start_expedition", self.cmd_start_expedition))
            self.application.add_handler(CommandHandler("stop_expedition", self.cmd_stop_expedition))
            self.application.add_handler(CommandHandler("start_farmer", self.cmd_start_farmer))
            self.application.add_handler(CommandHandler("stop_farmer", self.cmd_stop_farmer))

            logger.info("Telegram bot started - listening for commands")
            self.running = True

            # Initialize and start polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling(drop_pending_updates=True)

            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

            # Cleanup
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

        except Exception as e:
            logger.error(f"Telegram bot error: {e}")
            self.running = False

    def _thread_target(self):
        """Thread target for running the async polling loop."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._run_polling())
        except Exception as e:
            logger.error(f"Telegram bot thread error: {e}")
        finally:
            self.loop.close()
            self.running = False

    def start(self):
        """Start the Telegram bot in a separate thread."""
        if self.running:
            logger.warning("Telegram bot already running")
            return

        if not config.TELEGRAM_BOT_TOKEN:
            logger.warning("TELEGRAM_BOT_TOKEN not configured - skipping Telegram bot")
            return

        if not config.TELEGRAM_ENABLED:
            logger.info("Telegram notifications disabled - skipping Telegram bot")
            return

        self.thread = threading.Thread(target=self._thread_target, daemon=True)
        self.thread.start()
        logger.info("Telegram bot controller started")

    def stop(self):
        """Stop the Telegram bot."""
        if not self.running:
            return

        logger.info("Stopping Telegram bot...")
        self.running = False

        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

        logger.info("Telegram bot stopped")


# Global instance
telegram_controller = TelegramBotController()

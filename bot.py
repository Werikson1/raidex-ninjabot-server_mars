"""
Ogamex Bot - Main Entry Point
Automated asteroid mining bot for Ogamex game
"""

import asyncio
import random
import logging
import threading
import time
import json
from datetime import datetime
from collections import deque
from playwright.async_api import async_playwright

from modules.config import *
import modules.config as config_module
from modules.cooldown_manager import CooldownManager
from modules.fleet_dispatcher import FleetDispatcher
from modules.asteroid_finder import AsteroidFinder
from modules.expedition_runner import ExpeditionRunner
from modules.farmer_runner import FarmerRunner
from modules.asteroid_miner_runner import AsteroidMinerRunner
from modules.stealth import apply_stealth, get_stealth_args, get_stealth_user_agent
from modules.empire_manager import EmpireManager
from modules.notifications import TelegramLogHandler

# Setup logging
log_queue = deque(maxlen=100)  # Store last 100 logs

class QueueHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        # Format: [HH:MM:SS] Message
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_queue.append(f"[{timestamp}] {log_entry}")
        print(f"[{timestamp}] {log_entry}")

logger = logging.getLogger("OgameBot")
logger.setLevel(logging.INFO)
handler = QueueHandler()
console_formatter = logging.Formatter("%(message)s")
handler.setFormatter(console_formatter)
logger.addHandler(handler)

# Telegram error notifications
telegram_handler = TelegramLogHandler()
telegram_formatter = logging.Formatter("%(levelname)s - %(message)s")
telegram_handler.setFormatter(telegram_formatter)
logger.addHandler(telegram_handler)

class OgameBot:
    def __init__(self):
        self.running = False
        self.stop_flag = False
        self.thread = None
        self.loop = None
        self.cooldown_mgr = None
        self.empire_mgr = EmpireManager()
        self.browser_context = None
        self.asteroid_miner_enabled = False
        self.expedition_enabled = False
        self.farmer_enabled = False
        self.asteroid_task = None
        self.expedition_task = None
        self.farmer_task = None
        self.asteroid_runner = None
        
    def enable_asteroid_miner(self):
        """Enable the asteroid miner feature"""
        self.asteroid_miner_enabled = True
        # Reset miner-specific state if available
        try:
            if self.asteroid_runner and hasattr(self.asteroid_runner, "asteroid_finder"):
                af = getattr(self.asteroid_runner, "asteroid_finder")
                if hasattr(af, "range_skip_cooldowns"):
                    af.range_skip_cooldowns = {}
        except Exception:
            pass
        logger.info("Asteroid Miner enabled")

    def disable_asteroid_miner(self):
        """Disable the asteroid miner feature"""
        self.asteroid_miner_enabled = False
        logger.info("Asteroid Miner disabled")
    
    def is_asteroid_miner_enabled(self):
        """Check if asteroid miner is enabled"""
        return self.asteroid_miner_enabled

    def enable_expedition_mode(self):
        """Enable expedition automation"""
        self.expedition_enabled = True
        logger.info("Expedition mode enabled")

    def disable_expedition_mode(self):
        """Disable expedition automation"""
        self.expedition_enabled = False
        logger.info("Expedition mode disabled")

    def is_expedition_enabled(self):
        """Check if expedition automation is enabled"""
        return self.expedition_enabled

    def enable_farmer_mode(self):
        """Enable farmer automation"""
        self.farmer_enabled = True
        logger.info("Farmer mode enabled")

    def disable_farmer_mode(self):
        """Disable farmer automation"""
        self.farmer_enabled = False
        logger.info("Farmer mode disabled")

    def is_farmer_enabled(self):
        """Check if farmer automation is enabled"""
        return self.farmer_enabled
        
    def start(self):
        if self.running:
            logger.warning("Bot is already running")
            return
        
        self.running = True
        self.stop_flag = False

        # Sync runtime feature toggles with config on each start
        try:
            config_module._config = config_module.load_config()
            asteroid_cfg = config_module._config.get("ASTEROID_ENABLED", True)
            self.asteroid_miner_enabled = bool(asteroid_cfg)
            exp_cfg = config_module.get_expedition_config(config_module._config)
            self.expedition_enabled = exp_cfg.get("enabled", False)
            farmer_cfg = config_module.get_farmer_config(config_module._config)
            self.farmer_enabled = farmer_cfg.get("enabled", False)
        except Exception as e:
            logger.error(f"Failed to sync config on start: {e}")
        
        # Run in a separate thread to not block the web server
        self.thread = threading.Thread(target=self._run_async_loop)
        self.thread.start()
        logger.info("Bot started")

    def stop(self):
        if not self.running:
            return
        
        logger.info("Stopping bot...")
        self.stop_flag = True
        # Wait for thread to finish (optional, or just let it finish)
        self.running = False
    
    def get_cooldowns(self):
        """Get current cooldowns safely"""
        if self.cooldown_mgr:
            return self.cooldown_mgr.cooldowns
        # If bot not running, try to load from file directly for display
        try:
            with open(COOLDOWN_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}

    def get_empire_data(self):
        return self.empire_mgr.get_data()

    def trigger_empire_crawl(self):
        """Triggers the empire crawl in the running loop"""
        logger.info("Triggering empire crawl requested...")
        if not self.running or not self.loop:
            logger.error("Bot not running or loop not ready")
            return False, "Bot is not running"
        
        # Schedule the crawl coroutine in the running loop
        future = asyncio.run_coroutine_threadsafe(self._crawl_empire_task(), self.loop)
        try:
            # Optional: wait for result or just let it run
            # future.result(timeout=1) # Don't block here
            pass
        except Exception as e:
            logger.error(f"Error scheduling crawl: {e}")
            
        return True, "Crawl scheduled"

    async def _crawl_empire_task(self):
        """Task wrapper for empire crawl"""
        logger.info("Empire crawl task started")
        try:
            if not self.browser_context:
                logger.error("Cannot crawl: Browser context not available")
                return
                
            logger.info("Initiating manual Empire Crawl...")
            await self.empire_mgr.fetch_data(self.browser_context)
        except Exception as e:
            logger.error(f"Error in empire crawl task: {e}")

    async def _sleep_with_stop(self, seconds: int):
        """Sleep helper that checks for stop flag each second."""
        remaining = max(0, int(seconds))
        for _ in range(remaining):
            if self.stop_flag:
                break
            await asyncio.sleep(1)

    def _run_async_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._main_logic())
        except Exception as e:
            logger.error(f"Bot crashed: {e}")
        finally:
            self.loop.close()
            self.running = False
            logger.info("Bot stopped")

    async def _main_logic(self):
        # Reload config at start
        config_module._config = config_module.load_config()
        self.asteroid_miner_enabled = bool(config_module._config.get("ASTEROID_ENABLED", True))
        expedition_cfg = config_module.get_expedition_config(config_module._config)
        self.expedition_enabled = expedition_cfg.get("enabled", False)
        farmer_cfg = config_module.get_farmer_config(config_module._config)
        self.farmer_enabled = farmer_cfg.get("enabled", False)

        # Initialize modules
        self.cooldown_mgr = CooldownManager(COOLDOWN_FILE, COOLDOWN_HOURS)
        fleet_dispatcher = FleetDispatcher(FLEET_GROUP_NAME, FLEET_GROUP_VALUE, config_module.ASTEROID_MINER_AMOUNT)
        asteroid_finder = AsteroidFinder(
            SEARCH_DELAY_MIN,
            SEARCH_DELAY_MAX,
            NETWORK_IDLE_TIMEOUT,
            MODAL_TIMEOUT,
            BASE_SYSTEM,
            TRAVEL_TIME_RANGES
        )
        self.asteroid_runner = AsteroidMinerRunner(fleet_dispatcher, asteroid_finder, self.cooldown_mgr)
        expedition_runner = ExpeditionRunner(expedition_cfg)
        farmer_runner = FarmerRunner(farmer_cfg)

        async with async_playwright() as p:
            logger.info(f"Launching browser with persistent profile: {USER_DATA_DIR}")

            # Use persistent context to save login session with stealth mode
            stealth_args = get_stealth_args()
            stealth_args.append("--start-maximized")
            user_agent = get_stealth_user_agent()
            viewport_choice = {
                "width": random.randint(1330, 1380),
                "height": random.randint(750, 820),
            }

            headless_choice = HEADLESS_MODE or expedition_cfg.get("headless", False)

            context = await p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=headless_choice,
                args=stealth_args,
                viewport=viewport_choice,
                locale="en-US",
                color_scheme="light",
                user_agent=user_agent,
                ignore_default_args=["--enable-automation"],
            )

            self.browser_context = context

            # Apply stealth JavaScript evasions
            await apply_stealth(context, user_agent=user_agent)
            logger.info("Stealth mode activated - bot detection evasions applied")
            
            # Get or create page
            if len(context.pages) > 0:
                page = context.pages[0]
            else:
                page = await context.new_page()

            # Navigate to home (do not force galaxy here)
            if USE_LOCAL_FILE:
                logger.info(f"Loading local file: {LOCAL_FILE_PATH}")
                await page.goto(f"file:///{LOCAL_FILE_PATH}")
            else:
                logger.info("Navigating to: https://mars.ogamex.net/home")
                await page.goto("https://mars.ogamex.net/home")
                logger.info("Waiting for page load/login check...")
                await asyncio.sleep(5)

            # Cleanup expired cooldowns
            self.cooldown_mgr.cleanup_expired()
            active_cooldowns = self.cooldown_mgr.get_active_count()
            logger.info(f"Active cooldowns: {active_cooldowns}")

            # Feature tasks
            self.asteroid_task = asyncio.create_task(
                self.asteroid_runner.run(page, lambda: self.stop_flag, lambda: self.asteroid_miner_enabled)
            )
            self.expedition_task = asyncio.create_task(
                self._expedition_loop(context, expedition_runner)
            )
            self.farmer_task = asyncio.create_task(
                self._farmer_loop(context, farmer_runner)
            )
            tasks = [self.asteroid_task, self.expedition_task, self.farmer_task]

            try:
                while not self.stop_flag:
                    await asyncio.sleep(1)
            finally:
                for task in tasks:
                    if task:
                        task.cancel()
                await asyncio.gather(*[t for t in tasks if t], return_exceptions=True)
                self.asteroid_task = None
                self.expedition_task = None
                self.farmer_task = None
                self.asteroid_runner = None
                self.browser_context = None
                await context.close()
                logger.info("Browser context closed.")

    async def _expedition_loop(self, context, runner: ExpeditionRunner):
        """Expedition automation loop (runs as a background task)."""
        try:
            while not self.stop_flag:
                if not self.expedition_enabled:
                    await asyncio.sleep(1)
                    continue

                latest_cfg = config_module.get_expedition_config()
                runner.update_config(latest_cfg)

                if not latest_cfg.get("enabled", False):
                    await asyncio.sleep(1)
                    continue

                if runner.error_count > 5:
                    logger.error("Expedition retries exhausted. Toggle the feature or update config to reset.")
                    await self._sleep_with_stop(300)
                    continue

                stop_cb = lambda: self.stop_flag or not self.expedition_enabled
                await runner.run(context, stop_cb)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"Expedition loop error: {e}")
            await asyncio.sleep(5)

    async def _farmer_loop(self, context, runner: FarmerRunner):
        """Farmer automation loop (runs as a background task)."""
        try:
            while not self.stop_flag:
                if not self.farmer_enabled:
                    await asyncio.sleep(1)
                    continue

                latest_cfg = config_module.get_farmer_config()
                runner.update_config(latest_cfg)

                if not latest_cfg.get("enabled", False):
                    await asyncio.sleep(1)
                    continue

                if runner.error_count > 5:
                    logger.error("Farmer retries exhausted. Toggle the feature or update config to reset.")
                    await self._sleep_with_stop(300)
                    continue

                stop_cb = lambda: self.stop_flag or not self.farmer_enabled
                await runner.run(context, stop_cb)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"Farmer loop error: {e}")
            await asyncio.sleep(5)

    def run_brain_action(self, action):
        """
        Run a one-off brain action in the bot loop.
        """
        if not self.running or not self.loop:
            return False, "Bot not running"
            
        if action == "fetch_planets":
            # We need to import brain_manager here or pass it?
            # Better to import at top or use the one passed.
            from modules.brain import brain_manager
            future = asyncio.run_coroutine_threadsafe(brain_manager.fetch_planets(self.browser_context), self.loop)
            try:
                result = future.result(timeout=30)
                return True, result
            except Exception as e:
                return False, str(e)
        return False, "Unknown action"

    def start_brain_task(self, brain_mgr):
        """
        Start the brain background task.
        """
        if not self.running or not self.loop:
            return False, "Bot not running"
            
        # Stop existing if any
        if brain_mgr.running:
            brain_mgr.running = False
            
        # Schedule new task
        asyncio.run_coroutine_threadsafe(brain_mgr.run_brain_task(self.browser_context), self.loop)
        return True, "Brain task started"

    def stop_brain_task(self):
        from modules.brain import brain_manager
        brain_manager.running = False
        logger.info("Brain task stop requested")

# Global bot instance
bot_instance = OgameBot()

if __name__ == "__main__":
    # For backward compatibility/testing
    try:
        bot_instance.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bot_instance.stop()
        print("\n\n👋 Goodbye!")

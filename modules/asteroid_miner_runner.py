import asyncio
import logging
import random
from datetime import datetime, timedelta

import modules.config as config

logger = logging.getLogger("OgameBot")


class AsteroidMinerRunner:
    """Encapsulates the asteroid miner loop logic."""

    def __init__(self, fleet_dispatcher, asteroid_finder, cooldown_mgr, galaxy_url=None):
        self.fleet_dispatcher = fleet_dispatcher
        self.asteroid_finder = asteroid_finder
        self.cooldown_mgr = cooldown_mgr
        self.galaxy_url = galaxy_url or getattr(config, "ASTEROID_GALAXY_URL", config.LIVE_URL)
        self.reset_requested = False
        self.reset_reason = None
        try:
            self.asteroid_finder.set_galaxy_url(self.galaxy_url)
        except Exception:
            pass

    def update_galaxy_url(self, galaxy_url: str):
        """Update target galaxy URL for navigation and finder reuse."""
        if not galaxy_url:
            return
        self.galaxy_url = galaxy_url
        try:
            self.asteroid_finder.set_galaxy_url(galaxy_url)
        except Exception:
            pass

    def _reload_config(self):
        """Reload configuration from disk and update relevant settings."""
        try:
            cfg = config.load_config()
            
            # Update galaxy URL based on selected planet
            new_galaxy_url = config.get_asteroid_galaxy_url(cfg)
            if new_galaxy_url and new_galaxy_url != self.galaxy_url:
                logger.info(f"Asteroid config changed - updating galaxy URL")
                self.update_galaxy_url(new_galaxy_url)
            
            # Update fleet dispatcher settings
            asteroid_mode = cfg.get("asteroid_mode", {})
            fleet_group_name = asteroid_mode.get("fleet_group_name") or cfg.get("FLEET_GROUP_NAME", config.FLEET_GROUP_NAME)
            fleet_group_value = asteroid_mode.get("fleet_group_value") or cfg.get("FLEET_GROUP_VALUE", config.FLEET_GROUP_VALUE)
            
            if hasattr(self.fleet_dispatcher, "fleet_group_name"):
                self.fleet_dispatcher.fleet_group_name = fleet_group_name
            if hasattr(self.fleet_dispatcher, "fleet_group_value"):
                self.fleet_dispatcher.fleet_group_value = fleet_group_value
            
            # Update cooldown hours for asteroids
            cooldown_hours = cfg.get("COOLDOWN_HOURS", config.COOLDOWN_HOURS)
            if hasattr(self.cooldown_mgr, "cooldown_hours"):
                self.cooldown_mgr.cooldown_hours = cooldown_hours
            
            # Update range cooldown hours (also uses COOLDOWN_HOURS config)
            if hasattr(self.asteroid_finder, "range_cooldown_mgr"):
                self.asteroid_finder.range_cooldown_mgr.cooldown_hours = cooldown_hours
            
            return cfg
        except Exception as e:
            logger.warning(f"Failed to reload asteroid config: {e}")
            return None

    def _sleep_window_remaining(self) -> int:
        """Return seconds remaining in the sleep window (0 if outside sleep window)."""
        cfg = config.load_config()
        asteroid_cfg = cfg.get("asteroid_mode", {})
        
        # Support both new format (asteroid_mode.sleep_mode) and legacy root-level format
        sleep_mode = asteroid_cfg.get("sleep_mode") or cfg.get("asteroidSleepMode", False)
        
        if not sleep_mode:
            return 0

        now = datetime.now()
        
        # Try new format first, then fallback to legacy root-level format
        sleep_start = asteroid_cfg.get("sleep_start", {}) or {}
        wake_up = asteroid_cfg.get("wake_up", {}) or {}
        
        # Fallback to legacy root-level fields if new format is empty
        start_hour = int(sleep_start.get("hour") or cfg.get("sleepStartHour") or 0)
        start_minute = int(sleep_start.get("minute") or cfg.get("sleepStartMinute") or 0)
        wake_hour = int(wake_up.get("hour") or cfg.get("wakeHour") or 0)
        wake_minute = int(wake_up.get("minute") or cfg.get("wakeMinute") or 0)

        start_dt = now.replace(
            hour=start_hour,
            minute=start_minute,
            second=0,
            microsecond=0,
        )
        wake_dt = now.replace(
            hour=wake_hour,
            minute=wake_minute,
            second=0,
            microsecond=0,
        )

        # Handle overnight sleep (e.g., 23:00 -> 07:00)
        if start_dt >= wake_dt:
            if now < wake_dt:
                start_dt -= timedelta(days=1)
            else:
                wake_dt += timedelta(days=1)

        logger.debug(f"Sleep check: now={now.strftime('%H:%M')}, start={start_dt.strftime('%H:%M')}, wake={wake_dt.strftime('%H:%M')}")

        if start_dt <= now < wake_dt:
            remaining = (wake_dt - now).total_seconds()
            random_sleep = asteroid_cfg.get("random_sleep_mode") or cfg.get("asteroidRandomSleepMode", False)
            if random_sleep:
                jitter = random.randint(-5, 5) * 60
                remaining = max(0, remaining + jitter)
                logger.info(f"🎲 Random sleep jitter applied: {int(jitter/60)} minute(s)")
            return int(remaining)

        return 0

    def reset(self, galaxy_url: str = None, reason: str = None):
        """Reset the asteroid miner loop to start fresh."""
        if galaxy_url:
            self.update_galaxy_url(galaxy_url)
        self.reset_requested = True
        if reason:
            self.reset_reason = reason
        # Cleanup expired range cooldowns (persisted in JSON)
        try:
            if hasattr(self.asteroid_finder, "range_cooldown_mgr"):
                self.asteroid_finder.range_cooldown_mgr.cleanup_expired()
        except Exception:
            pass
        # Cleanup expired asteroid cooldowns
        try:
            self.cooldown_mgr.cleanup_expired()
        except Exception:
            pass
        logger.info("Asteroid miner cycle reset requested")

    async def _perform_reset(self):
        """Actually reset runtime state (close galaxy tab, clear cached page)."""
        try:
            galaxy_page = getattr(self.asteroid_finder, "galaxy_page", None)
            if galaxy_page and not galaxy_page.is_closed():
                await galaxy_page.close()
        except Exception:
            pass
        try:
            if hasattr(self.asteroid_finder, "galaxy_page"):
                self.asteroid_finder.galaxy_page = None
        except Exception:
            pass

    async def _sleep_with_stop(self, seconds: int, stop_cb):
        remaining = max(0, int(seconds))
        for _ in range(remaining):
            if stop_cb() or self.reset_requested:
                return False
            await asyncio.sleep(1)
        return True

    async def run(self, page, stop_cb, enabled_cb):
        """Background loop for asteroid mining."""
        try:
            while not stop_cb():
                if self.reset_requested:
                    reset_reason = self.reset_reason
                    self.reset_requested = False
                    self.reset_reason = None
                    await self._perform_reset()
                    if reset_reason:
                        logger.info(f"Asteroid miner reset acknowledged - restarting from step 1 ({reset_reason})")
                    else:
                        logger.info("Asteroid miner reset acknowledged - restarting from step 1")

                if not enabled_cb():
                    await asyncio.sleep(1)
                    continue

                # Sleep window guard - wait until wake up time
                sleep_seconds = self._sleep_window_remaining()
                if sleep_seconds > 0:
                    wake_time = (datetime.now() + timedelta(seconds=sleep_seconds)).strftime("%H:%M")
                    logger.info(f"💤 Asteroid miner sleeping until {wake_time} ({int(sleep_seconds // 60)} minutes)")
                    await self._sleep_with_stop(sleep_seconds, stop_cb)
                    continue

                # Reload config at start of each cycle to pick up changes
                self._reload_config()

                logger.info("Searching for asteroids...")
                asteroid_coords = await self.asteroid_finder.find_asteroids(page, self.cooldown_mgr)

                if asteroid_coords:
                    range_start_sys = None
                    range_end_sys = None
                    try:
                        if len(asteroid_coords) == 3:
                            galaxy, system, position = asteroid_coords
                        else:
                            galaxy, system, position, range_start_sys, range_end_sys = asteroid_coords
                    except Exception:
                        galaxy, system, position = asteroid_coords[:3]
                        range_start_sys = None
                        range_end_sys = None
                    logger.info(f"Dispatching fleet to [{galaxy}:{system}:{position}]")

                    dispatch_page = page
                    try:
                        galaxy_page = getattr(self.asteroid_finder, "galaxy_page", None)
                        if galaxy_page and not galaxy_page.is_closed():
                            dispatch_page = galaxy_page
                    except Exception:
                        pass

                    success = await self.fleet_dispatcher.dispatch_to_asteroid(
                        dispatch_page, self.galaxy_url, target_coords=(galaxy, system, position)
                    )

                    if success:
                        self.cooldown_mgr.add_to_cooldown(galaxy, system, position)
                        # Only persist the range cooldown after successful dispatch
                        try:
                            if (
                                range_start_sys is not None
                                and range_end_sys is not None
                                and hasattr(self.asteroid_finder, "range_cooldown_mgr")
                            ):
                                self.asteroid_finder.range_cooldown_mgr.add_to_cooldown(
                                    galaxy, range_start_sys, range_end_sys, position
                                )
                        except Exception as e:
                            logger.debug(f"Failed to persist range cooldown: {e}")
                        logger.info("Asteroid mission complete. Continuing search...")
                    else:
                        logger.warning("Fleet dispatch failed (possibly no fleet available)")
                        # Reload config to get latest wait time
                        cfg = config.load_config()
                        wait_minutes = cfg.get("FLEET_FAIL_WAIT_MINUTES", config.FLEET_FAIL_WAIT_MINUTES)
                        logger.info(f"Waiting {wait_minutes} minutes before retrying...")
                        completed = await self._sleep_with_stop(wait_minutes * 60, stop_cb)
                        if completed and enabled_cb() and not stop_cb():
                            self.reset(reason="Fleet Fail Wait finished")
                else:
                    # Reload config to get latest wait times
                    cfg = config.load_config()
                    wait_min = cfg.get("NO_ASTEROID_WAIT_MIN", config.NO_ASTEROID_WAIT_MIN)
                    wait_max = cfg.get("NO_ASTEROID_WAIT_MAX", config.NO_ASTEROID_WAIT_MAX)
                    wait_minutes = random.randint(wait_min, wait_max)
                    logger.info("No asteroids available")
                    logger.info(f"Waiting {wait_minutes} minutes before next search...")
                    completed = await self._sleep_with_stop(wait_minutes * 60, stop_cb)
                    if completed and enabled_cb() and not stop_cb():
                        self.reset(reason="No-asteroid standby finished")
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"Asteroid loop error: {e}")
            await asyncio.sleep(5)

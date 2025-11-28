import asyncio
import logging
import random

import modules.config as config

logger = logging.getLogger("OgameBot")


class AsteroidMinerRunner:
    """Encapsulates the asteroid miner loop logic."""

    def __init__(self, fleet_dispatcher, asteroid_finder, cooldown_mgr):
        self.fleet_dispatcher = fleet_dispatcher
        self.asteroid_finder = asteroid_finder
        self.cooldown_mgr = cooldown_mgr

    async def _sleep_with_stop(self, seconds: int, stop_cb):
        remaining = max(0, int(seconds))
        for _ in range(remaining):
            if stop_cb():
                break
            await asyncio.sleep(1)

    async def run(self, page, stop_cb, enabled_cb):
        """Background loop for asteroid mining."""
        try:
            while not stop_cb():
                if not enabled_cb():
                    await asyncio.sleep(1)
                    continue

                logger.info("Searching for asteroids...")
                asteroid_coords = await self.asteroid_finder.find_asteroids(page, self.cooldown_mgr)

                if asteroid_coords:
                    galaxy, system, position = asteroid_coords
                    logger.info(f"Dispatching fleet to [{galaxy}:{system}:{position}]")

                    success = await self.fleet_dispatcher.dispatch_to_asteroid(page, config.LIVE_URL)

                    if success:
                        self.cooldown_mgr.add_to_cooldown(galaxy, system, position)
                        logger.info("Asteroid mission complete. Continuing search...")
                    else:
                        logger.warning("Fleet dispatch failed (possibly no fleet available)")
                        logger.info(f"Waiting {config.FLEET_FAIL_WAIT_MINUTES} minutes before retrying...")
                        await self._sleep_with_stop(config.FLEET_FAIL_WAIT_MINUTES * 60, stop_cb)
                else:
                    wait_minutes = random.randint(config.NO_ASTEROID_WAIT_MIN, config.NO_ASTEROID_WAIT_MAX)
                    logger.info("No asteroids available")
                    logger.info(f"Waiting {wait_minutes} minutes before next search...")
                    await self._sleep_with_stop(wait_minutes * 60, stop_cb)
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.error(f"Asteroid loop error: {e}")
            await asyncio.sleep(5)

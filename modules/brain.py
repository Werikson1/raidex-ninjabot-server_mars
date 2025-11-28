import asyncio
import json
import logging
import os
import random
import re
import sqlite3
import time
from datetime import datetime

logger = logging.getLogger("OgameBot")


class BrainManager:
    def __init__(self):
        self.running = False
        self.task = None
        self.planet_targets = {}  # {planet_id: {building_id: max_level}}
        self.targets_file = os.path.abspath(os.path.join("data", "brain_targets.json"))
        self.state_db_path = os.path.abspath(os.path.join("data", "brain_state.db"))
        self._db_conn = None
        self.page = None  # reused page to avoid tab churn

        # Building IDs mapping (based on OGame standard or observed)
        self.BUILDINGS = {
            "METAL_MINE": "Metal Mine",
            "CRYSTAL_MINE": "Crystal Mine",
            "DEUTERIUM_REFINERY": "Deuterium Synthesizer",
            "SOLAR_POWER_PLANT": "Solar Plant",
            "FUSION_REACTOR": "Fusion Reactor",
            "ROBOT_FACTORY": "Robotics Factory",
            "NANITE_FACTORY": "Nanite Factory",
            "SHIPYARD": "Shipyard",
            "METAL_STORAGE": "Metal Storage",
            "CRYSTAL_STORAGE": "Crystal Storage",
            "DEUTERIUM_TANK": "Deuterium Tank",
            "RESEARCH_LAB": "Research Lab",
            "TERRAFORMER": "Terraformer",
            "ALLIANCE_DEPOT": "Alliance Depot",
            "MISSILE_SILO": "Missile Silo",
        }
        # Map building to page type to avoid extra navigation
        self.BUILDING_PAGE = {
            "METAL_MINE": "resource",
            "CRYSTAL_MINE": "resource",
            "DEUTERIUM_REFINERY": "resource",
            "SOLAR_POWER_PLANT": "resource",
            "FUSION_REACTOR": "resource",
            "METAL_STORAGE": "resource",
            "CRYSTAL_STORAGE": "resource",
            "DEUTERIUM_TANK": "resource",
            "SHIPYARD": "facility",
            "ROBOT_FACTORY": "facility",
            "NANITE_FACTORY": "facility",
            "RESEARCH_LAB": "facility",
            "TERRAFORMER": "facility",
            "ALLIANCE_DEPOT": "facility",
            "MISSILE_SILO": "facility",
        }

    def _sanitize_targets(self, targets):
        """
        Normalize/validate targets structure to {planet_id: {building_id: positive_int}}.
        Zero/negative or non-numeric values are discarded.
        """
        if not isinstance(targets, dict):
            return {}

        cleaned = {}
        for planet_id, buildings in targets.items():
            if not isinstance(buildings, dict):
                continue

            planet_key = str(planet_id)
            valid_buildings = {}

            for building_id, level in buildings.items():
                try:
                    level_int = int(level)
                except (TypeError, ValueError):
                    continue

                if level_int > 0:
                    valid_buildings[building_id] = level_int

            if valid_buildings:
                cleaned[planet_key] = valid_buildings

        return cleaned

    def read_saved_targets(self):
        """
        Load saved targets from disk without mutating active targets.
        """
        try:
            with open(self.targets_file, "r") as f:
                data = json.load(f)
            return self._sanitize_targets(data)
        except FileNotFoundError:
            return {}
        except Exception as e:
            logger.error(f"Failed to load brain targets: {e}")
            return {}

    def save_targets_to_disk(self, targets):
        """
        Persist targets to disk. Returns cleaned targets on success, None on failure.
        """
        cleaned = self._sanitize_targets(targets)
        try:
            dir_name = os.path.dirname(self.targets_file)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)

            with open(self.targets_file, "w") as f:
                json.dump(cleaned, f, indent=4)

            logger.info(f"Brain targets saved to {self.targets_file}")
            return cleaned
        except Exception as e:
            logger.error(f"Failed to save brain targets: {e}")
            return None

    def set_targets(self, planet_id, targets):
        """
        Set or update the building targets for a specific planet.
        targets: dict of {building_id: max_level}
        """
        sanitized = self._sanitize_targets({planet_id: targets})
        planet_key = str(planet_id)

        if planet_key in sanitized:
            self.planet_targets[planet_key] = sanitized[planet_key]
            logger.info(f"Brain targets updated for planet {planet_id}: {sanitized[planet_key]}")
        elif planet_key in self.planet_targets:
            # Remove if no valid targets remain
            self.planet_targets.pop(planet_key, None)
            logger.info(f"Brain targets cleared for planet {planet_id}")

    # --- Persistence helpers for build cooldowns ---
    def _init_db(self):
        if self._db_conn:
            return
        self._db_conn = sqlite3.connect(self.state_db_path, check_same_thread=False)
        self._db_conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planet_cooldowns (
                planet_id TEXT PRIMARY KEY,
                building_id TEXT,
                ready_at REAL
            )
            """
        )
        self._db_conn.commit()

    def _set_cooldown(self, planet_id, building_id, ready_at):
        self._init_db()
        self._db_conn.execute(
            "REPLACE INTO planet_cooldowns (planet_id, building_id, ready_at) VALUES (?, ?, ?)",
            (str(planet_id), building_id, float(ready_at)),
        )
        self._db_conn.commit()

    def _get_cooldown(self, planet_id):
        self._init_db()
        cur = self._db_conn.execute(
            "SELECT building_id, ready_at FROM planet_cooldowns WHERE planet_id = ?",
            (str(planet_id),),
        )
        row = cur.fetchone()
        if not row:
            return None, None
        building_id, ready_at = row
        return building_id, float(ready_at)

    def _clear_expired_cooldowns(self):
        self._init_db()
        now_ts = time.time()
        self._db_conn.execute("DELETE FROM planet_cooldowns WHERE ready_at <= ?", (now_ts,))
        self._db_conn.commit()

    async def run_brain_task(self, context):
        """
        Main loop for the brain task. Iterates through all configured planets.
        """
        self.running = True
        logger.info("Brain started! Processing all configured planets...")
        self._init_db()
        self._clear_expired_cooldowns()

        try:
            while self.running:
                if not self.planet_targets:
                    logger.warning("Brain running but no targets set for any planet.")
                    await asyncio.sleep(random.uniform(8, 14))
                    continue

                # Create a list of planets to process to avoid runtime modification issues during iteration
                planets_to_process = list(self.planet_targets.items())

                for planet_id, targets in planets_to_process:
                    if not self.running:
                        break

                    # Skip planet if a build is already underway
                    current_building, ready_at = self._get_cooldown(planet_id)
                    now_ts = time.time()
                    if ready_at and ready_at > now_ts:
                        wait_min = int((ready_at - now_ts) // 60)
                        logger.info(
                            f"Skipping planet {planet_id} (building {current_building} busy for ~{wait_min} min)"
                        )
                        continue

                    logger.info(f"Processing planet {planet_id}...")

                    page = await self._get_work_page(context)
                    try:
                        # Resolve ID if it's a coordinate
                        target_id = planet_id
                        if target_id and target_id.startswith('['):
                            # Load empire data to find ID
                            try:
                                with open(os.path.join("data", "empire_data.json"), "r") as f:
                                    data = json.load(f)
                                    for p in data.get("planets", []):
                                        if p.get("coords") == target_id and p.get("id"):
                                            target_id = p.get("id")
                                            logger.info(f"Resolved {planet_id} -> {target_id}")
                                            break
                            except Exception as e:
                                logger.error(f"Failed to resolve coordinate to ID: {e}")

                        # Group targets by page type to avoid extra navigation
                        grouped = {"resource": {}, "facility": {}}
                        for b_id, max_level in targets.items():
                            page_type = self.BUILDING_PAGE.get(b_id, "resource")
                            grouped.setdefault(page_type, {})[b_id] = max_level

                        action_taken = False

                        for page_type, page_targets in grouped.items():
                            if not page_targets or action_taken:
                                continue

                            url = f"https://cypher.ogamex.net/building/{page_type}?planet={target_id}"
                            logger.info(f"Navigating to {url}")
                            await page.goto(url)
                            await page.wait_for_load_state("networkidle")

                            for building_id, max_level in page_targets.items():
                                if not self.running or action_taken:
                                    break

                                max_level = int(max_level)
                                if max_level <= 0:
                                    continue

                                selector = f"a.upgrade-btn-small[data-building-type='{building_id}']"
                                button = await page.query_selector(selector)

                                if button:
                                    to_level = await button.get_attribute("data-tolevel")
                                    to_level = int(to_level) if to_level else 0

                                    logger.info(f"Checking {building_id}: Upgrade to {to_level} (Target: {max_level})")

                                    if to_level <= max_level:
                                        class_attr = await button.get_attribute("class")
                                        if class_attr and ("disabled" in class_attr or "gray" in class_attr):
                                            logger.info(f"Cannot build {building_id} yet (resources or requirements).")
                                            continue

                                        # Capture duration before click
                                        duration_sec = await self._parse_build_duration(page)

                                        logger.info(f"Attempting to upgrade {building_id} to level {to_level}")
                                        await button.click()
                                        action_taken = True

                                        await page.wait_for_load_state("networkidle")
                                        await asyncio.sleep(2)  # Safety wait

                                        if duration_sec:
                                            ready_at = time.time() + duration_sec + 5  # small buffer
                                            self._set_cooldown(planet_id, building_id, ready_at)
                                            mins = int(duration_sec // 60)
                                            logger.info(
                                                f"Queued {building_id} on {planet_id}; will revisit after ~{mins} min"
                                            )

                                        # One build per planet at a time
                                        break
                                    else:
                                        logger.info(f"{building_id} already at or above target level.")
                                else:
                                    logger.debug(
                                        f"Upgrade button for {building_id} not found (maybe maxed or already building)."
                                    )

                        if action_taken:
                            logger.info(f"Action taken on {planet_id}. Moving to next planet.")
                        else:
                            logger.info(f"No actions possible on {planet_id}.")

                    except Exception as e:
                        logger.error(f"Error processing planet {planet_id}: {e}")
                        # keep page open to avoid tab churn

                    # Short pause between planets
                    await asyncio.sleep(random.uniform(1.5, 3.5))

                # Wait before next full cycle
                logger.info("Cycle complete. Waiting before next check...")
                await asyncio.sleep(random.uniform(55, 75))

        except Exception as e:
            logger.error(f"Brain crashed: {e}")
        finally:
            self.running = False
            try:
                if self.page and not self.page.is_closed():
                    await self.page.close()
            except Exception:
                pass
            try:
                if self._db_conn:
                    self._db_conn.close()
                    self._db_conn = None
            except Exception:
                pass
            logger.info("Brain stopped.")

    async def calculate_wait_time(self, page, building_id):
        """
        Calculate time needed to gather resources.
        """
        try:
            # Parse current resources
            # Selectors for resources (usually in header)
            metal = await self.get_resource(page, "metal")
            crystal = await self.get_resource(page, "crystal")
            deuterium = await self.get_resource(page, "deuterium")

            # Parse production (might need to go to resource settings or infer)
            # For now, just log that we are waiting.
            # Implementing full calculation requires knowing the cost.
            # The cost might be in the tooltip or a separate element.

            logger.info(f"Current resources: M:{metal} C:{crystal} D:{deuterium}")
            # TODO: Implement full cost parsing and time calculation

        except Exception as e:
            logger.error(f"Error calculating wait time: {e}")

    async def fetch_planets(self, context):
        """
        Fetches planets with their IDs from the game interface.
        """
        try:
            page = await context.new_page()
            # Go to overview or any page where the planet list is visible
            await page.goto("https://cypher.ogamex.net/overview")
            await page.wait_for_load_state("networkidle")

            planets = []
            # Select planet links. Usually in a list #planetList or similar
            # OGame standard: #planetList .smallplanet
            # OgameX might differ.
            # Let's try a generic selector for links containing 'planet='

            elements = await page.query_selector_all("a[href*='planet=']")

            seen_ids = set()

            for el in elements:
                href = await el.get_attribute("href")
                # Extract ID
                match = re.search(r'planet=([a-zA-Z0-9-]+)', href)
                if match:
                    planet_id = match.group(1)
                    if planet_id in seen_ids:
                        continue
                    seen_ids.add(planet_id)

                    # Try to get name
                    name = await el.inner_text()
                    name = name.strip() or "Unknown"

                    # Sometimes the name is in a child span or title attribute
                    if name == "Unknown":
                        title = await el.get_attribute("title")
                        if title:
                            name = title

                    # Clean up name (remove coords if present, or keep them)
                    planets.append({"id": planet_id, "name": name})

            await page.close()
            logger.info(f"Brain fetched {len(planets)} planets: {planets}")
            return planets
        except Exception as e:
            logger.error(f"Error fetching planets: {e}")
            return []

    async def get_resource(self, page, resource_name):
        try:
            # Common OGame selectors, might need adjustment for OgameX
            el = await page.query_selector(f"#resources_{resource_name}")
            if el:
                text = await el.inner_text()
                return int(text.replace('.', '').strip())
        except Exception:
            return 0
        return 0

    async def _get_work_page(self, context):
        """
        Reuse a single page to avoid opening/closing tabs on every planet.
        """
        try:
            if self.page and not self.page.is_closed():
                return self.page
        except Exception:
            pass

        pages = context.pages
        if pages:
            self.page = pages[0]
        else:
            self.page = await context.new_page()
        return self.page

    async def _parse_build_duration(self, page):
        """
        Parse build duration from the current page. Returns seconds or None.
        Expects content like: 'Construction duration : 34:04' or '1:02:03'.
        """
        try:
            items = await page.query_selector_all("div.production-info .info-item")
            for item in items:
                text = await item.inner_text()
                if "Construction duration" in text:
                    # Extract time pattern
                    match = re.search(r"(\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})", text)
                    if match:
                        parts = match.group(1).split(":")
                        if len(parts) == 3:
                            h, m, s = [int(p) for p in parts]
                        else:
                            h = 0
                            m, s = [int(p) for p in parts]
                        return h * 3600 + m * 60 + s
        except Exception as e:
            logger.debug(f"Failed to parse build duration: {e}")
        return None


brain_manager = BrainManager()

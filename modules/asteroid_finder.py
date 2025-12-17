"""Asteroid Finder Module
Handles asteroid detection, modal parsing, and system searching
"""

import asyncio
import json
import os
import random
import time
from typing import List, Tuple, Optional, Dict
from playwright.async_api import Page

from .cooldown_manager import CooldownManager
from .config import LIVE_URL, USE_LOCAL_FILE

# File path for range cooldowns persistence
RANGE_COOLDOWN_FILE = os.path.abspath(os.path.join("data", "range_cooldowns.json"))


class RangeCooldownManager:
    """Manages cooldowns for asteroid ranges to avoid re-checking recently visited ranges."""
    
    def __init__(self, cooldown_file: str = RANGE_COOLDOWN_FILE, cooldown_hours: float = 1.0):
        self.cooldown_file = cooldown_file
        self.cooldown_hours = cooldown_hours
        self.cooldowns: Dict[str, float] = self._load()
    
    def _load(self) -> Dict[str, float]:
        """Load range cooldowns from file."""
        try:
            with open(self.cooldown_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    def _save(self):
        """Save range cooldowns to file."""
        try:
            os.makedirs(os.path.dirname(self.cooldown_file), exist_ok=True)
            with open(self.cooldown_file, 'w') as f:
                json.dump(self.cooldowns, f, indent=2)
        except Exception as e:
            print(f"⚠ Failed to save range cooldowns: {e}")
    
    def _make_key(self, galaxy: int, start_sys: int, end_sys: int, position: int) -> str:
        """Create a string key from range tuple."""
        return f"{galaxy}:{start_sys}-{end_sys}:{position}"
    
    def is_in_cooldown(self, galaxy: int, start_sys: int, end_sys: int, position: int) -> bool:
        """Check if a range is in cooldown."""
        key = self._make_key(galaxy, start_sys, end_sys, position)
        
        if key in self.cooldowns:
            sent_time = self.cooldowns[key]
            elapsed_hours = (time.time() - sent_time) / 3600
            
            if elapsed_hours < self.cooldown_hours:
                remaining = self.cooldown_hours - elapsed_hours
                print(f"  → Range [{galaxy}:{start_sys}-{end_sys}:{position}] in cooldown. {remaining:.1f}h remaining.")
                return True
            else:
                # Cooldown expired, remove it
                del self.cooldowns[key]
                self._save()
        
        return False
    
    def add_to_cooldown(self, galaxy: int, start_sys: int, end_sys: int, position: int):
        """Add a range to cooldown after successful dispatch or insufficient time."""
        key = self._make_key(galaxy, start_sys, end_sys, position)
        self.cooldowns[key] = time.time()
        self._save()
        print(f"✓ Range [{galaxy}:{start_sys}-{end_sys}:{position}] added to cooldown for {self.cooldown_hours}h")
    
    def cleanup_expired(self):
        """Remove all expired range cooldowns."""
        current_time = time.time()
        expired_keys = []
        
        for key, sent_time in self.cooldowns.items():
            elapsed_hours = (current_time - sent_time) / 3600
            if elapsed_hours >= self.cooldown_hours:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cooldowns[key]
        
        if expired_keys:
            self._save()
            print(f"✓ Cleaned up {len(expired_keys)} expired range cooldown(s)")
    
    def clear_all(self):
        """Clear all range cooldowns."""
        self.cooldowns = {}
        self._save()
        print("✓ All range cooldowns cleared")


class AsteroidFinder:
    def __init__(
        self,
        search_delay_min: float,
        search_delay_max: float,
        network_timeout: int,
        modal_timeout: int,
        base_system: int,
        travel_time_ranges: List[Tuple[int, int, int]],
        galaxy_url: str = None,
        range_cooldown_hours: float = 1.0,
    ):
        self.search_delay_min = search_delay_min
        self.search_delay_max = search_delay_max
        self.network_timeout = network_timeout
        self.modal_timeout = modal_timeout
        self.base_system = base_system
        self.travel_time_ranges = travel_time_ranges
        self.galaxy_page: Optional[Page] = None
        self.galaxy_url = galaxy_url or LIVE_URL
        # Persistent range cooldown manager (saves to JSON)
        self.range_cooldown_mgr = RangeCooldownManager(cooldown_hours=range_cooldown_hours)

    def set_galaxy_url(self, galaxy_url: str):
        """Update target galaxy URL for navigation."""
        if galaxy_url:
            self.galaxy_url = galaxy_url

    async def _get_galaxy_page(self, page: Page) -> Page:
        """
        Ensure we have a galaxy page tab; reuse if still open.
        """
        if USE_LOCAL_FILE:
            self.galaxy_page = page
            return page
        try:
            if self.galaxy_page and not self.galaxy_page.is_closed():
                try:
                    current_url = self.galaxy_page.url or ""
                except Exception:
                    current_url = ""
                if self.galaxy_url and self.galaxy_url not in current_url:
                    await self.galaxy_page.goto(self.galaxy_url)
                return self.galaxy_page
        except Exception:
            pass

        target_url = self.galaxy_url or LIVE_URL
        self.galaxy_page = await page.context.new_page()
        await self.galaxy_page.goto(target_url)
        await self.galaxy_page.wait_for_selector("#systemInput", state="visible", timeout=10000)
        return self.galaxy_page

    async def _human_pause(self, min_delay: float = 0.08, max_delay: float = 0.25):
        """Small random pause to break deterministic timing."""
        await asyncio.sleep(random.uniform(min_delay, max_delay))

    async def _human_mouse_move(self, page: Page, locator):
        """Move mouse through a few steps over the target area."""
        try:
            box = await locator.bounding_box()
            if not box:
                return
            target_x = box["x"] + random.uniform(3, max(4.0, box["width"] - 3))
            target_y = box["y"] + random.uniform(3, max(4.0, box["height"] - 3))
            await page.mouse.move(target_x, target_y, steps=random.randint(6, 14))
        except Exception:
            return

    async def _human_click(self, page: Page, locator):
        """Hover then click with a small delay to mimic users."""
        try:
            await self._human_mouse_move(page, locator)
        except Exception:
            pass
        try:
            await locator.click(delay=random.randint(35, 120))
        except Exception:
            await locator.click()
        await self._human_pause()

    async def _type_safely(self, page: Page, selector: str, value: str):
        """Type with per-character delay and an occasional backspace/retype."""
        try:
            field = page.locator(selector)
            await field.click()
            await field.fill("")
            for ch in value:
                await page.keyboard.type(ch, delay=random.randint(40, 110))
            if value and random.random() < 0.2:
                await page.keyboard.press("Backspace")
                await page.keyboard.type(value[-1], delay=random.randint(40, 110))
        except Exception:
            await page.fill(selector, value)

    async def find_asteroids(self, page: Page, cooldown_mgr: CooldownManager) -> Optional[Tuple[int, int, int]]:
        """
        Search for asteroids and return coordinates of first available one

        Args:
            page: Playwright page object
            cooldown_mgr: Cooldown manager instance

        Returns:
            Tuple of (galaxy, system, position) if found, None otherwise
        """
        try:
            page = await self._get_galaxy_page(page)
            
            # Check for "Find asteroids" button
            find_btn = page.locator(".btn-asteroid-find.x-find-asteroid")
            try:
                print("🔍 Waiting for 'Find asteroids' button...")
                await find_btn.wait_for(state="visible", timeout=12000)
            except Exception:
                print("ℹ No 'Find asteroids' button visible (timeout).")
                return None

            print("✓ Asteroid 'Find' button detected! Clicking...")
            await self._human_click(page, find_btn)

            # Wait for modal
            print("⌛ Waiting for asteroid modal...")
            await page.wait_for_selector("#playerAsteroidTable", timeout=self.modal_timeout)

            # Parse asteroid ranges
            ranges = await self._parse_asteroid_ranges(page)

            if not ranges:
                print("ℹ No asteroid ranges found in modal")
                await self._close_modal(page)
                return None

            print(f"📊 Found {len(ranges)} asteroid range(s) to check")

            # Close modal before searching
            await self._close_modal(page)

            # Search through ranges for available asteroid
            asteroid_coords = await self._search_ranges(page, ranges, cooldown_mgr)

            return asteroid_coords

        except Exception as e:
            print(f"❌ Error in asteroid finder: {e}")
            return None

    async def _parse_asteroid_ranges(self, page: Page) -> List[Tuple[int, int, int]]:
        """Parse asteroid coordinate ranges from the modal"""
        links = await page.locator("#playerAsteroidTable a").all_text_contents()
        print(f"  → Raw locations: {links}")

        ranges = []
        # Iterate in steps of 2 to get pairs (start, end)
        for i in range(0, len(links), 2):
            if i + 1 < len(links):
                try:
                    start_str = links[i]
                    end_str = links[i + 1]
                    # Parse [3:74:17] -> extract galaxy, start_sys, end_sys
                    galaxy = int(start_str.strip("[]").split(":")[0])
                    start_sys = int(start_str.strip("[]").split(":")[1])
                    end_sys = int(end_str.strip("[]").split(":")[1])
                    position = int(start_str.strip("[]").split(":")[2])
                    ranges.append((galaxy, start_sys, end_sys, position))
                except Exception as e:
                    print(f"  ⚠ Error parsing range {links[i]} - {links[i+1]}: {e}")

        return ranges

    async def _close_modal(self, page: Page):
        """Close the asteroid modal"""
        try:
            close_btn = page.locator("#ajax-asteroid-modal .modal__close")
            await self._human_click(page, close_btn)
            print("✓ Closed asteroid modal")
        except Exception as e:
            print(f"  ⚠ Could not close modal: {e}")

    async def _search_ranges(
        self,
        page: Page,
        ranges: List[Tuple[int, int, int, int]],
        cooldown_mgr: CooldownManager,
    ) -> Optional[Tuple[int, int, int]]:
        """
        Search through asteroid ranges for an available asteroid

        Returns:
            Tuple of (galaxy, system, position) if found, None otherwise
        """
        # Cleanup expired range cooldowns at start of search
        self.range_cooldown_mgr.cleanup_expired()
        
        for galaxy, start_sys, end_sys, position in ranges:
            # Check if this range is in cooldown (persisted in JSON)
            if self.range_cooldown_mgr.is_in_cooldown(galaxy, start_sys, end_sys, position):
                continue

            print(f"Checking range [{galaxy}:{start_sys}:{position}] -> [{galaxy}:{end_sys}:{position}]")

            last_visited_sys = None

            # Iterate through systems in this range
            for sys in range(start_sys, end_sys + 1):
                # Check if this specific asteroid is in cooldown
                if cooldown_mgr.is_in_cooldown(galaxy, sys, position):
                    continue

                # Smart Navigation
                if last_visited_sys is not None and sys == last_visited_sys + 1:
                    print(f"  Navigating to system {sys} [ArrowRight]...")
                    await page.keyboard.press("ArrowRight")
                    await self._human_pause(0.05, 0.18)
                elif last_visited_sys is not None and sys == last_visited_sys - 1:
                    print(f"  Navigating to system {sys} [ArrowLeft]...")
                    await page.keyboard.press("ArrowLeft")
                    await self._human_pause(0.05, 0.18)
                else:
                    print(f"  Navigating to system {sys} [Direct]...")
                    await self._type_safely(page, "#systemInput", str(sys))
                    await self._human_click(page, page.locator(".x-btn-go"))

                # Update last visited
                last_visited_sys = sys

                # Wait for page load
                try:
                    await page.wait_for_load_state("networkidle", timeout=self.network_timeout)
                except Exception:
                    pass
                await self._human_pause(0.12, 0.32)

                # Random delay
                await asyncio.sleep(random.uniform(self.search_delay_min, self.search_delay_max))

                # Check if asteroid is present
                asteroid_btn = page.locator(".btn-asteroid")
                if await asteroid_btn.count() > 0 and await asteroid_btn.first.is_visible():
                    # Asteroid found! Now check if we have enough time to reach it
                    timer_minutes = await self._get_asteroid_timer(page)

                    if timer_minutes is None:
                        print("  Could not read asteroid timer, skipping...")
                        continue

                    # Calculate required travel time
                    distance = abs(sys - self.base_system)
                    required_minutes = self._get_required_travel_time(distance)

                    print(f"ASTEROID FOUND: [{galaxy}:{sys}:{position}]")
                    print(f"  Asteroid timer: {timer_minutes} minutes")
                    print(f"  Distance: {distance} systems (from base {self.base_system})")
                    print(f"  Required time: {required_minutes} minutes")

                    if timer_minutes >= required_minutes:
                        print("  Sufficient time! Dispatching fleet...")
                        print("? Clicking asteroid...")
                        await self._human_click(page, asteroid_btn.first)
                        # Mark this range to skip for 1 hour (persisted to JSON)
                        self.range_cooldown_mgr.add_to_cooldown(galaxy, start_sys, end_sys, position)
                        return (galaxy, sys, position)
                    else:
                        print(f"  Insufficient time ({timer_minutes} < {required_minutes} min)")
                        print("  Adding asteroid and range to cooldown")
                        cooldown_mgr.add_to_cooldown(galaxy, sys, position)
                        # Also skip this range for 1 hour (persisted to JSON)
                        self.range_cooldown_mgr.add_to_cooldown(galaxy, start_sys, end_sys, position)
                        continue

            print(f"  No available asteroids in range [{galaxy}:{start_sys}-{end_sys}:{position}]")

        print("No available asteroids found in any range")
        return None

    async def _get_asteroid_timer(self, page: Page) -> Optional[int]:
        """
        Parse asteroid disappear timer from the page

        Returns:
            Timer in minutes, or None if not found
        """
        try:
            # Look for element with data-asteroid-disappear attribute
            timer_element = page.locator("[data-asteroid-disappear]").first

            if not await timer_element.is_visible():
                return None

            # Get the attribute value (in seconds)
            timer_seconds_str = await timer_element.get_attribute("data-asteroid-disappear")

            if not timer_seconds_str:
                return None

            timer_seconds = int(timer_seconds_str)
            timer_minutes = timer_seconds // 60

            return timer_minutes

        except Exception as e:
            print(f"  ⚠ Error parsing asteroid timer: {e}")
            return None

    def _get_required_travel_time(self, distance: int) -> int:
        """
        Get required travel time based on distance from base

        Args:
            distance: Absolute distance from base system

        Returns:
            Required time in minutes
        """
        for min_dist, max_dist, required_time in self.travel_time_ranges:
            if min_dist <= distance <= max_dist:
                return required_time

        # Default to longest time if distance exceeds all ranges
        return self.travel_time_ranges[-1][2]

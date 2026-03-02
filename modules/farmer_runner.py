"""
Farmer Runner
Automates plunder dispatch from the saved planets page with randomized delays,
sleep windows, and cooldown tracking.
"""

import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime, timedelta
from typing import Callable, Optional, List

from playwright.async_api import BrowserContext, Page
from urllib.parse import urlparse, parse_qs

from . import config

logger = logging.getLogger("OgameBot")

FARMER_STATE_FILE = os.path.abspath(os.path.join("data", "farmer_state.json"))


def load_farmer_state() -> dict:
    """Load persisted farmer state (counter, active_until epoch)."""
    try:
        with open(FARMER_STATE_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"counter": 0, "active_until": 0}
        return {
            "counter": int(data.get("counter", 0) or 0),
            "active_until": int(data.get("active_until", 0) or 0),
        }
    except Exception:
        return {"counter": 0, "active_until": 0}


def save_farmer_state(state: dict):
    """Persist farmer state safely."""
    try:
        with open(FARMER_STATE_FILE, "w") as f:
            json.dump(
                {
                    "counter": int(state.get("counter", 0) or 0),
                    "active_until": int(state.get("active_until", 0) or 0),
                },
                f,
                indent=2,
            )
    except Exception as exc:
        logger.error(f"Failed to save farmer state: {exc}")


class FarmerRunner:
    def __init__(self, farmer_config: dict):
        self.config = farmer_config or {}
        self.page: Optional[Page] = None
        self.error_count = 0
        self.running = False
        self.state = load_farmer_state()
        self.next_active_ping_ts = 0

        self.nav_timeout_ms = max(config.FLEET_PAGE_TIMEOUT, 12000)

    def update_config(self, farmer_config: dict):
        """Update in-memory farmer configuration snapshot."""
        previous_enabled = self.config.get("enabled", False) if isinstance(self.config, dict) else False
        self.config = farmer_config or self.config
        if (self.config or {}).get("enabled", False) and not previous_enabled:
            self.error_count = 0
        self.state = load_farmer_state()
        self.next_active_ping_ts = 0

    async def run(self, context: BrowserContext, stop_cb: Callable[[], bool]):
        """Main farmer loop."""
        if self.error_count > 5:
            logger.error("!! Farmer retries exhausted. Awaiting manual reset or config change.")
            return

        self.running = True
        logger.info("Farmer automation started")

        while not stop_cb() and self.config.get("enabled", False):
            sleep_seconds = self._sleep_window_remaining()
            if sleep_seconds > 0:
                wake_time = (datetime.now() + timedelta(seconds=sleep_seconds)).strftime("%H:%M")
                logger.info(
                    f"Farmer sleeping until {wake_time} ({int(sleep_seconds // 60)} minutes)"
                )
                await self._sleep_with_stop(sleep_seconds, stop_cb)
                continue

            # Active mode keep-alive (if enabled)
            await self._maybe_keep_active(context, stop_cb)

            try:
                delay_seconds = await self._execute_cycle(context, stop_cb)
                self.error_count = 0
            except Exception as exc:
                self.error_count += 1
                logger.error(f"!! Farmer cycle failed: {exc}")
                if self.error_count > 5:
                    logger.error("!! Farmer reached max retries. Pausing loop.")
                    break
                delay_seconds = random.randint(300, 600)

            await self._sleep_with_stop(delay_seconds, stop_cb)

        self.running = False
        logger.info("Farmer loop stopped")

    async def _execute_cycle(self, context: BrowserContext, stop_cb: Callable[[], bool]) -> int:
        """Perform a full farmer sweep and return cooldown seconds before next cycle."""
        page = await self._ensure_fresh_page(context)
        await self._navigate_to_saved_planets(page)
        await self._verify_page(page)

        targets = await self._collect_plunder_targets(page)
        total = len(targets)
        if total == 0:
            logger.warning("No plunder targets found on saved planets page")
            return random.randint(180, 360)

        logger.info(f"Found {total} saved planet plunder buttons. Beginning dispatch...")
        success_count = await self._dispatch_to_targets(page, targets, stop_cb)

        cooldown_minutes = self._choose_cooldown_minutes()
        cooldown_seconds = max(60, cooldown_minutes * 60)
        self._mark_cycle(cooldown_seconds)

        logger.info(
            f"Farmer dispatched plunder to {success_count}/{total} targets. Waiting {cooldown_minutes} minute(s) before next cycle"
        )
        return cooldown_seconds

    async def _ensure_fresh_page(self, context: BrowserContext) -> Page:
        """Always open a fresh tab to mirror human behavior and reduce stale DOM issues."""
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
        except Exception:
            pass
        self.page = await context.new_page()
        return self.page

    async def _navigate_to_saved_planets(self, page: Page):
        """Navigate to the saved planets page for the configured planet."""
        planet_id = self.config.get("planet_id") or config.MAIN_PLANET_ID
        url = f"https://mars.ogamex.net/galaxy/savedplanets?planet={planet_id}"
        logger.info(f"? Opening saved planets page for planet {planet_id}")
        await page.goto(url, wait_until="load", timeout=self.nav_timeout_ms)
        try:
            await page.wait_for_load_state("networkidle", timeout=config.NETWORK_IDLE_TIMEOUT)
        except Exception:
            pass

    async def _verify_page(self, page: Page):
        """Verify we landed on the correct saved planets page."""
        current_url = ""
        try:
            current_url = page.url or ""
        except Exception:
            pass
        if "/galaxy/savedplanets" not in current_url:
            raise RuntimeError(f"Unexpected page while starting farmer: {current_url}")

    async def _collect_plunder_targets(self, page: Page):
        """Collect plunder buttons and metadata."""
        locator = page.locator("a.btnActionPlunder")
        try:
            await locator.first.wait_for(state="visible", timeout=8000)
        except Exception:
            return []

        targets = []
        try:
            info = await locator.evaluate_all(
                "(nodes) => nodes.map((n, idx) => { const oc = (n.getAttribute('onclick')||''); const m = oc.match(/SendPlunder\\('(.*?)'\\)/); return {idx, target: m ? m[1] : '', disabled: n.classList.contains('disabled')}; })"
            )
            if isinstance(info, list):
                targets = [{"index": int(item.get("idx", i)), "id": item.get("target") or ""} for i, item in enumerate(info)]
        except Exception:
            pass

        if not targets:
            count = await locator.count()
            targets = [{"index": i, "id": ""} for i in range(count)]

        return targets

    async def _dispatch_to_targets(self, page: Page, targets: List[dict], stop_cb: Callable[[], bool]) -> int:
        """Click each plunder button with human-like jitter and error handling."""
        success_count = 0
        total = len(targets)

        # Optional slight shuffle to avoid perfect patterns
        if total > 2 and random.random() < 0.25:
            random.shuffle(targets)
            logger.info("Farmer randomized plunder order for safety.")

        for idx, target in enumerate(targets, start=1):
            if stop_cb():
                break

            btn = page.locator("a.btnActionPlunder").nth(target["index"])
            target_id = target.get("id") or f"index-{target['index']}"
            try:
                await btn.scroll_into_view_if_needed()
                await btn.wait_for(state="visible", timeout=self.nav_timeout_ms)
            except Exception as exc:
                logger.warning(f"?? Target {idx}/{total} ({target_id}) not interactable: {exc}")
                continue

            await asyncio.sleep(random.uniform(0.2, 0.5))

            try:
                await self._human_click(btn)
                success_count += 1
                logger.info(f"? Farmer clicked plunder {idx}/{total} target={target_id}")
            except Exception as exc:
                logger.error(f"!! Failed to click plunder {idx}/{total} target={target_id}: {exc}")

            # Jitter between clicks to mimic a human scanning the list
            jitter = random.uniform(0.8, 2.6)
            await self._sleep_with_stop(jitter, stop_cb)

        if success_count < total:
            logger.warning(f"Farmer could not click {total - success_count} target(s); check DOM or session.")

        return success_count

    async def _human_click(self, locator):
        """Click with small randomized delay to mimic human behavior."""
        try:
            await locator.click(delay=random.randint(40, 140))
        except Exception:
            await locator.click()
        await asyncio.sleep(random.uniform(0.05, 0.18))

    def _choose_cooldown_minutes(self) -> int:
        """Choose a random cooldown within configured min/max."""
        min_val = int(self.config.get("attack_cooldown_min", 0) or 0)
        max_val = int(self.config.get("attack_cooldown_max", min_val) or min_val)

        min_val = max(0, min(360, min_val))
        max_val = max(min_val, min(360, max_val))

        if min_val == max_val:
            return max(1, min_val)

        return max(1, random.randint(min_val, max_val))

    def _sleep_window_remaining(self) -> int:
        """Return seconds remaining in the sleep window (0 if active)."""
        if not self.config.get("sleep_mode"):
            return 0

        now = datetime.now()
        sleep_start = self.config.get("sleep_start", {}) or {}
        wake_up = self.config.get("wake_up", {}) or {}

        start_dt = now.replace(
            hour=int(sleep_start.get("hour", 0) or 0),
            minute=int(sleep_start.get("minute", 0) or 0),
            second=0,
            microsecond=0,
        )
        wake_dt = now.replace(
            hour=int(wake_up.get("hour", 0) or 0),
            minute=int(wake_up.get("minute", 0) or 0),
            second=0,
            microsecond=0,
        )

        if start_dt >= wake_dt:
            if now < wake_dt:
                start_dt -= timedelta(days=1)
            else:
                wake_dt += timedelta(days=1)

        if start_dt <= now < wake_dt:
            remaining = (wake_dt - now).total_seconds()
            # Optional jitter
            jitter = 0
            if self.config.get("random_sleep_mode"):
                jitter = random.randint(-5, 5) * 60
                remaining = max(0, remaining + jitter)
            logger.info(
                f"Farmer sleep window active now={now.strftime('%H:%M')} "
                f"start={start_dt.strftime('%H:%M')} wake={wake_dt.strftime('%H:%M')} "
                f"remaining={int(remaining)}s jitter={int(jitter/60)}m"
            )
            return int(remaining)

        return 0

    async def _sleep_with_stop(self, delay_seconds: float, stop_cb: Callable[[], bool]):
        """Sleep with stop checks to avoid long blocking waits."""
        remaining = max(0, float(delay_seconds))
        while remaining > 0:
            if stop_cb():
                return
            chunk = 1 if remaining > 1 else remaining
            await asyncio.sleep(chunk)
            remaining -= chunk

    def _mark_cycle(self, cooldown_seconds: int, increment_counter: bool = True):
        """Persist counter and expected delay for current farmer cycle."""
        now = int(time.time())
        if increment_counter:
            self.state["counter"] = int(self.state.get("counter", 0) or 0) + 1
        self.state["active_until"] = now + max(0, int(cooldown_seconds))
        save_farmer_state(self.state)

    def remaining_cooldown(self) -> int:
        """Return remaining seconds until next farmer cycle."""
        active_until = int(self.state.get("active_until", 0) or 0)
        now = int(time.time())
        remaining = active_until - now
        if remaining <= 0:
            if active_until != 0:
                self.state["active_until"] = 0
                save_farmer_state(self.state)
            return 0
        return remaining

    async def _maybe_keep_active(self, context: BrowserContext, stop_cb: Callable[[], bool]):
        """Ping fleet page periodically to keep the planet active."""
        if not self.config.get("active_mode"):
            return
        now = time.time()
        if self.next_active_ping_ts and now < self.next_active_ping_ts:
            return
        if self._sleep_window_remaining() > 0:
            return

        try:
            url = self._build_fleet_url()
            logger.info(f"Farmer active mode pinging {url}")
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)
            try:
                await page.wait_for_load_state("networkidle", timeout=config.NETWORK_IDLE_TIMEOUT)
            except Exception:
                pass
            await page.close()
        except Exception as exc:
            logger.error(f"Active mode ping failed: {exc}")
        finally:
            jitter = random.randint(13, 16) * 60
            self.next_active_ping_ts = time.time() + jitter

    def _build_fleet_url(self) -> str:
        """Build fleet URL using base of LIVE_URL and configured planet."""
        try:
            parsed = urlparse(config.LIVE_URL)
            base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else "https://mars.ogamex.net"
            planet_id = self.config.get("planet_id") or config.MAIN_PLANET_ID
            if planet_id:
                return f"{base_url}/fleet?planet={planet_id}"
            return f"{base_url}/fleet"
        except Exception:
            return "https://mars.ogamex.net/fleet"

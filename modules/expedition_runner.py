"""
Expedition Runner
Automates the autoexpedition page with slot checks, fleet selection, and cooldown logic.
"""

import asyncio
import json
import logging
import random
import time
import os
from datetime import datetime, timedelta
from typing import Optional, Callable

from playwright.async_api import BrowserContext, Page

from . import config

logger = logging.getLogger("OgameBot")

EXPEDITION_STATE_FILE = os.path.abspath(os.path.join("data", "expedition_state.json"))


def load_expedition_state() -> dict:
    """Load persisted expedition state (counter, active_until epoch)."""
    try:
        with open(EXPEDITION_STATE_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"counter": 0, "active_until": 0}
        return {
            "counter": int(data.get("counter", 0) or 0),
            "active_until": int(data.get("active_until", 0) or 0),
        }
    except Exception:
        return {"counter": 0, "active_until": 0}


def save_expedition_state(state: dict):
    """Persist expedition state safely."""
    try:
        with open(EXPEDITION_STATE_FILE, "w") as f:
            json.dump(
                {
                    "counter": int(state.get("counter", 0) or 0),
                    "active_until": int(state.get("active_until", 0) or 0),
                },
                f,
                indent=2,
            )
    except Exception as exc:
        logger.error(f"Failed to save expedition state: {exc}")


class ExpeditionRunner:
    def __init__(self, expedition_config: dict):
        self.config = expedition_config or {}
        self.page: Optional[Page] = None
        self.error_count = 0
        self.running = False
        self.state = load_expedition_state()

        # Timeouts
        self.nav_timeout_ms = max(config.FLEET_PAGE_TIMEOUT, 12000)
        self.modal_timeout_ms = max(config.MODAL_TIMEOUT, 5000)

    def update_config(self, expedition_config: dict):
        """Update in-memory expedition configuration snapshot."""
        previous_enabled = self.config.get("enabled", False) if isinstance(self.config, dict) else False
        self.config = expedition_config or self.config
        if (self.config or {}).get("enabled", False) and not previous_enabled:
            # Reset error budget when re-enabled
            self.error_count = 0
        # Refresh state from disk if it changes underneath us
        self.state = load_expedition_state()

    async def run(self, context: BrowserContext, stop_cb: Callable[[], bool]):
        """Main expedition loop."""
        if self.error_count > 5:
            logger.error("!! Expedition retries exhausted. Awaiting manual reset or config change.")
            return

        self.running = True
        logger.info("Expedition automation started")

        while not stop_cb() and self.config.get("enabled", False):
            # Sleep window guard
            sleep_seconds = self._sleep_window_remaining()
            if sleep_seconds > 0:
                logger.info(f"Expedition sleeping for {int(sleep_seconds // 60)} minutes (sleep window)")
                await self._sleep_with_stop(sleep_seconds, stop_cb)
                continue

            try:
                delay_seconds = await self._execute_cycle(context, stop_cb)
                self.error_count = 0
            except Exception as exc:
                self.error_count += 1
                logger.error(f"!! Expedition cycle failed: {exc}")
                if self.error_count > 5:
                    logger.error("!! Expedition reached max retries. Pausing loop.")
                    break
                delay_seconds = random.randint(300, 600)

            await self._sleep_with_stop(delay_seconds, stop_cb)

        self.running = False
        logger.info("Expedition loop stopped")

    async def _execute_cycle(self, context: BrowserContext, stop_cb: Callable[[], bool]) -> int:
        """Perform a single expedition attempt and return delay before next cycle (seconds)."""
        page = await self._ensure_page(context)

        # Respect active expedition window before touching slots
        remaining_active = self._remaining_active_seconds()
        if remaining_active > 0:
            logger.info(f"Active expedition in progress. Waiting {int(remaining_active/60)} minute(s) before next check.")
            return remaining_active

        # Step 1: Navigation + verification
        await self._navigate_to_expedition(page)
        await self._verify_page(page)

        # Step 2: Slot verification
        slots_used = await self._read_slots(page)
        if slots_used is None:
            raise RuntimeError("Could not read expedition slots")
        if slots_used > 0:
            retry_delay = random.randint(600, 1200)
            logger.info(f"Expeditions in progress ({slots_used}), retrying in {int(retry_delay/60)} minutes")
            return retry_delay

        # Step 3: Select fleet group + send fleet
        sent = await self._select_group_and_send(page)
        if not sent:
            retry_delay = random.randint(300, 600)
            logger.warning(f"Expedition send failed, retrying in {int(retry_delay/60)} minutes")
            return retry_delay

        # Step 4: Cooldown with jitter
        cooldown_minutes = self._get_dispatch_cooldown_minutes()
        jitter_minutes = random.randint(-5, 5)
        cooldown_minutes = max(0, cooldown_minutes + jitter_minutes)
        cooldown_seconds = cooldown_minutes * 60
        self._mark_expedition_sent(cooldown_seconds)
        logger.info(f"Expedition sent. Waiting {cooldown_minutes} minute(s) before next cycle")
        return cooldown_seconds

    async def _ensure_page(self, context: BrowserContext) -> Page:
        """Reuse or create an expedition tab."""
        try:
            if self.page and not self.page.is_closed():
                return self.page
        except Exception:
            pass

        self.page = await context.new_page()
        return self.page

    async def _navigate_to_expedition(self, page: Page):
        """Navigate to the autoexpedition page for the configured planet."""
        planet_id = self.config.get("planet_id") or config.MAIN_PLANET_ID
        url = f"https://cypher.ogamex.net/fleet/autoexpedition?planet={planet_id}"
        logger.info(f"? Opening expedition page for planet {planet_id}")
        await page.goto(url, wait_until="load", timeout=self.nav_timeout_ms)
        try:
            await page.wait_for_load_state("networkidle", timeout=config.NETWORK_IDLE_TIMEOUT)
        except Exception:
            pass

    async def _verify_page(self, page: Page):
        """Quick verification to ensure we are on the expedition page."""
        current_url = ""
        try:
            current_url = page.url or ""
        except Exception:
            pass
        if "/fleet/autoexpedition" not in current_url:
            raise RuntimeError(f"Unexpected page while starting expedition: {current_url}")

    async def _read_slots(self, page: Page) -> Optional[int]:
        """Parse the expedition slot counter (used/total)."""
        locator = page.locator("text=Expeditions :")
        try:
            await locator.first.wait_for(timeout=6000)
            text = await locator.first.inner_text()
            # Expect formats like "Expeditions : 0/14"
            numbers = [int(part) for part in "".join(ch if ch.isdigit() or ch == "/" else " " for ch in text).replace("/", " ").split() if part.isdigit()]
            if numbers:
                return numbers[0]
        except Exception as exc:
            logger.error(f"?? Could not read expedition slots: {exc}")
        return None

    async def _select_group_and_send(self, page: Page) -> bool:
        """Select fleet group and send the expedition."""
        select = page.locator("#fleetGroupSelect")
        await select.wait_for(state="visible", timeout=self.nav_timeout_ms)
        await select.scroll_into_view_if_needed()
        await self._wait_for_options(select)

        options = await select.evaluate(
            "(sel) => Array.from(sel.options).map(o => ({value:o.value,label:(o.textContent||'').trim()}))"
        )
        logger.info(f"? Expedition fleet options: {options}")

        target_label = self.config.get("fleet_group_name") or ""
        target_value = self.config.get("fleet_group_value") or ""
        matched = False

        # 1) Try label first
        try:
            await select.select_option(label=target_label)
            matched = True
            current_val = await select.evaluate("(sel) => sel.value")
            if current_val:
                target_value = current_val
        except Exception:
            matched = False

        # 2) Try by value
        if not matched and target_value:
            try:
                await select.select_option(value=target_value)
                matched = True
            except Exception:
                matched = False

        # 3) Force via JS if needed
        if not matched and target_value:
            try:
                await select.evaluate(
                    "(sel, val) => { sel.value = val; sel.dispatchEvent(new Event('input', {bubbles:true})); sel.dispatchEvent(new Event('change', {bubbles:true})); }",
                    target_value,
                )
                current_val = await select.evaluate("(sel) => sel.value")
                matched = current_val == target_value
            except Exception:
                matched = False

        if not matched:
            logger.error(f"!! Expedition fleet group selection failed for {target_label or target_value}")
            return False

        await asyncio.sleep(random.uniform(0.4, 0.9))

        send_button = page.locator("#btnSend")
        try:
            await page.wait_for_selector("#btnSend:not(.disabled)", timeout=8000)
        except Exception:
            logger.warning("? Send button still disabled, retrying selection dispatch")
            if target_value:
                await select.evaluate(
                    "(sel, val) => { sel.value = val; sel.dispatchEvent(new Event('change', {bubbles:true})); }",
                    target_value,
                )
            try:
                await page.wait_for_selector("#btnSend:not(.disabled)", timeout=4000)
            except Exception:
                logger.error("!! Send button did not enable")
                return False

        await self._human_click(page, send_button)

        # Wait for success modal
        try:
            confirm_btn = page.locator("button.swal2-confirm")
            await confirm_btn.wait_for(state="visible", timeout=self.modal_timeout_ms)
            await self._human_click(page, confirm_btn)
        except Exception as exc:
            logger.warning(f"? Expedition confirmation modal not handled cleanly: {exc}")

        return True

    async def _wait_for_options(self, select, minimum: int = 1, retries: int = 15, delay_ms: int = 200):
        """Wait until the select has at least `minimum` options."""
        for _ in range(retries):
            try:
                options = await select.evaluate("(sel) => Array.from(sel.options).filter(o => o.value).length")
                if options >= minimum:
                    return
            except Exception:
                pass
            await asyncio.sleep(delay_ms / 1000)

    async def _human_click(self, page: Page, locator):
        """Click with small randomized delay to mimic human behavior."""
        try:
            await locator.click(delay=random.randint(35, 120))
        except Exception:
            await locator.click()
        await asyncio.sleep(random.uniform(0.06, 0.18))

    def _get_dispatch_cooldown_minutes(self) -> int:
        """Convert configured cooldown to minutes."""
        dispatch = self.config.get("dispatch_cooldown", {}) or {}
        hours = int(dispatch.get("hour", 0) or 0)
        minutes = int(dispatch.get("minute", 0) or 0)
        minutes = max(0, min(59, minutes))
        hours = max(0, min(23, hours))
        return hours * 60 + minutes

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
            if self.config.get("random_sleep_mode"):
                jitter = random.randint(-5, 5) * 60
                remaining = max(0, remaining + jitter)
                logger.info(f"? Random sleep jitter applied: {int(jitter/60)} minute(s)")
            return int(remaining)

        return 0

    async def _sleep_with_stop(self, delay_seconds: int, stop_cb: Callable[[], bool]):
        """Sleep with stop checks to avoid long blocking waits."""
        remaining = max(0, int(delay_seconds))
        while remaining > 0:
            if stop_cb():
                return
            await asyncio.sleep(min(1, remaining))
            remaining -= 1

    def _remaining_active_seconds(self) -> int:
        """Return remaining seconds for active expedition based on persisted state."""
        active_until = int(self.state.get("active_until", 0) or 0)
        now = int(time.time())
        remaining = active_until - now
        if remaining <= 0:
            if active_until != 0:
                # Clear expired state
                self.state["active_until"] = 0
                save_expedition_state(self.state)
            return 0
        return remaining

    def _mark_expedition_sent(self, cooldown_seconds: int, increment_counter: bool = True):
        """Persist counter and expected return time for current expedition."""
        now = int(time.time())
        if increment_counter:
            self.state["counter"] = int(self.state.get("counter", 0) or 0) + 1
        self.state["active_until"] = now + max(0, int(cooldown_seconds))
        save_expedition_state(self.state)

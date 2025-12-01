"""
Fleet Dispatcher Module
Handles fleet selection and dispatch to asteroids
"""

import asyncio
import random
import time
from urllib.parse import urlparse, parse_qs
from playwright.async_api import Page
import modules.config as config


class FleetDispatcher:
    def __init__(self, fleet_group_name: str, fleet_group_value: str):
        self.fleet_group_name = fleet_group_name
        self.fleet_group_value = fleet_group_value

    async def _human_click(self, page: Page, selector: str):
        """Click with a small randomized delay to look human."""
        loc = page.locator(selector)
        try:
            await loc.click(delay=random.randint(35, 120))
        except Exception:
            await loc.click()
        await asyncio.sleep(random.uniform(0.06, 0.18))

    async def _log_debug_options(self, page: Page):
        """Log available fleet group options for debugging."""
        select = page.locator("#fleetGroupSelect")
        try:
            options = await select.evaluate(
                "(sel) => Array.from(sel.options).map(o => ({value:o.value,label:(o.textContent||'').trim()}))"
            )
            print(f"Debug fleet options: {options}")
        except Exception as e:
            print(f"Could not read fleet options: {e}")

    async def _wait_for_options(self, page: Page, minimum: int = 2, retries: int = 10, delay_ms: int = 200):
        """Wait until the select has at least `minimum` options with value."""
        select = page.locator("#fleetGroupSelect")
        for _ in range(retries):
            try:
                options = await select.evaluate(
                    "(sel) => Array.from(sel.options).filter(o => o.value).length"
                )
                if options >= minimum:
                    return True
            except Exception:
                pass
            await page.wait_for_timeout(delay_ms)
        return False

    def _build_fleet_url(self, fallback_planet: str = None):
        """Build fleet URL using base of LIVE_URL and planet param if available."""
        try:
            parsed = urlparse(config.LIVE_URL)
            base_url = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else "https://mars.ogamex.net"
            planet_id = None
            qs_planet = parse_qs(parsed.query).get("planet")
            if qs_planet and len(qs_planet) > 0:
                planet_id = qs_planet[0]
            if not planet_id:
                planet_id = fallback_planet or getattr(config, "MAIN_PLANET_ID", None)
            if planet_id:
                return f"{base_url}/fleet?planet={planet_id}"
            return f"{base_url}/fleet"
        except Exception:
            return "https://mars.ogamex.net/fleet"

    async def _select_fleet_group_fast(self, select, target_name: str, target_value: str) -> bool:
        """Fast-path selection to avoid long waits."""
        options = await select.evaluate(
            "(sel) => Array.from(sel.options).map(o => ({value:o.value,label:(o.textContent||'').trim()}))"
        )
        target_value = target_value or ""
        target_name = target_name or ""

        # Prefer value match (IDs)
        if target_value:
            for opt in options:
                if opt["value"] == target_value:
                    await select.evaluate(
                        "(sel, val) => { sel.value = val; sel.dispatchEvent(new Event('input', {bubbles:true})); sel.dispatchEvent(new Event('change', {bubbles:true})); }",
                        target_value,
                    )
                    return True

        # Fallback by label (exact)
        if target_name:
            for opt in options:
                if opt["label"] == target_name:
                    await select.evaluate(
                        "(sel, val) => { sel.value = val; sel.dispatchEvent(new Event('input', {bubbles:true})); sel.dispatchEvent(new Event('change', {bubbles:true})); }",
                        opt["value"],
                    )
                    self.fleet_group_value = opt["value"]
                    return True

        return False

    async def _ensure_fleet_page(self, page: Page) -> Page:
        """Ensure we are on a fleet page, capturing popups if a new tab opens."""
        try:
            current_url = page.url
        except Exception:
            current_url = ""
        print(f"[debug] current page url before fleet: {current_url}")

        # If on autoexpedition page, redirect to fleet page
        if current_url and "/fleet/autoexpedition" in current_url:
            parsed = urlparse(current_url)
            planet_param = parse_qs(parsed.query).get("planet", [None])[0]
            fleet_url = self._build_fleet_url(planet_param)
            print(f"[debug] redirecting from autoexpedition to fleet: {fleet_url}")
            await page.goto(fleet_url, timeout=15000)
            await page.wait_for_selector("#fleetGroupSelect", timeout=10000)
            return page

        # If already on fleet page or selector exists, return current
        try:
            if current_url and "/fleet" in current_url and "/fleet/autoexpedition" not in current_url:
                print("[debug] already on fleet page (current tab)")
                return page
            if await page.locator("#fleetGroupSelect").count() > 0:
                print("[debug] fleet selector present on current tab")
                return page
        except Exception:
            pass

        ctx = page.context
        print("[debug] polling pages for /fleet or selector")
        for attempt in range(6):  # shorter polling to reduce wait (~3-4s)
            for p in ctx.pages:
                try:
                    url = p.url or ""
                except Exception:
                    url = ""
                try:
                    has_selector = await p.locator("#fleetGroupSelect").count() > 0
                except Exception:
                    has_selector = False
                if ("/fleet" in url and "/fleet/autoexpedition" not in url) or has_selector:
                    print(f"[debug] using page {url} selector={has_selector}")
                    if "/fleet/autoexpedition" in url:
                        try:
                            planet_param = parse_qs(urlparse(url).query).get("planet", [None])[0]
                        except Exception:
                            planet_param = None
                        fleet_url = self._build_fleet_url(planet_param)
                        print(f"[debug] redirecting autoexpedition tab to fleet: {fleet_url}")
                        await p.goto(fleet_url, timeout=15000)
                        await p.wait_for_selector("#fleetGroupSelect", timeout=10000)
                    return p
            await ctx.wait_for_timeout(600)

        # Navigate current page directly as fallback
        fleet_url = self._build_fleet_url()

        print(f"[debug] navigating to fleet page fallback: {fleet_url}")
        await page.goto(fleet_url, timeout=15000)
        await page.wait_for_selector("#fleetGroupSelect", timeout=10000)
        return page
    
    async def dispatch_to_asteroid(self, page: Page, galaxy_url: str) -> bool:
        """
        Dispatch fleet to an asteroid
        
        Args:
            page: Playwright page object
            galaxy_url: URL to return to after dispatch
        
        Returns:
            True if dispatch successful, False otherwise
        """
        try:
            print("? Waiting for fleet page...")
            try:
                print(f"[debug] incoming page for dispatch: {await page.evaluate('window.location.href')}")
            except Exception as e:
                print(f"[debug] could not read current href: {e}")
            page = await self._ensure_fleet_page(page)
            print(f"V Fleet page ready at {page.url}")
            
            # Step 1: Select Fleet Group
            print(f"? Selecting fleet group: {self.fleet_group_name}")
            select = page.locator("#fleetGroupSelect")
            await select.wait_for(state="visible", timeout=5000)
            await select.scroll_into_view_if_needed()
            started = time.monotonic()
            await self._wait_for_options(page, minimum=1, retries=5, delay_ms=120)

            # Fast-path selection
            target_value = self.fleet_group_value
            matched = await self._select_fleet_group_fast(select, self.fleet_group_name, target_value)

            current_value = await select.evaluate("(sel) => sel.value")
            if not matched or (target_value and current_value != target_value):
                # retry with fresh options and label/value selection
                await self._log_debug_options(page)
                try:
                    await select.select_option(value=target_value)
                    matched = True
                    current_value = await select.evaluate("(sel) => sel.value")
                except Exception:
                    matched = False

                if not matched:
                    try:
                        await select.select_option(label=self.fleet_group_name)
                        matched = True
                        current_value = await select.evaluate("(sel) => sel.value")
                        if current_value:
                            self.fleet_group_value = current_value
                    except Exception:
                        matched = False

                expected = self.fleet_group_value or target_value
                if not matched or (expected and current_value != expected):
                    print(f"!! Fleet group selection failed. Expected {expected}, got {current_value}")
                    return False

            if not current_value:
                print("!! Fleet group selection failed (empty value after selection)")
                return False

            elapsed = (time.monotonic() - started) * 1000
            print(f"V Fleet group selected in {elapsed:.0f}ms: {self.fleet_group_name} (ID: {self.fleet_group_value or target_value})")

            await asyncio.sleep(random.uniform(0.6, 1.2))
            
            # Step 1: Click Next (Step 1 -> 2)
            print("? Clicking Next (1)...")
            next_btn_selector = "#btn-next-fleet2"
            await page.wait_for_selector(next_btn_selector, state="visible")
            
            # Wait for button to become enabled
            try:
                # Wait up to 5 seconds for the disabled class to be removed
                await page.wait_for_selector(f"{next_btn_selector}:not(.disabled)", state="visible", timeout=5000)
            except Exception:
                print("! Next button still disabled. Retrying selection event...")
                # Retry dispatching change event if button is still disabled
                if target_value:
                    await select.evaluate(
                        "(sel, val) => { sel.value = val; sel.dispatchEvent(new Event('change', {bubbles:true})); }",
                        target_value,
                    )
                    await asyncio.sleep(0.5)
                    try:
                        await page.wait_for_selector(f"{next_btn_selector}:not(.disabled)", state="visible", timeout=3000)
                    except Exception:
                        print("!! Next button failed to enable.")
                        return False

            await self._human_click(page, next_btn_selector)
            await asyncio.sleep(random.uniform(1.5, 2.5))
            
            # Step 3: Click Next (Step 2 -> 3)
            print("? Clicking Next (2)...")
            next_btn3_selector = "#btn-next-fleet3"
            await page.wait_for_selector(next_btn3_selector, state="visible")
            await asyncio.sleep(0.5) # Give UI a moment
            try:
                await page.wait_for_selector(f"{next_btn3_selector}:not(.disabled)", state="visible", timeout=5000)
            except Exception:
                print("! Next button (2) still disabled. Waiting a bit more...")
                await asyncio.sleep(2.0)
            
            await self._human_click(page, next_btn3_selector)
            await asyncio.sleep(random.uniform(0.7, 1.4))
            
            # Step 4: Ensure mission selection (Asteroid Mining) and click Send Fleet
            try:
                mission = page.locator(".mission-item.ASTEROID_MINING")
                await mission.wait_for(state="visible", timeout=8000)
                is_selected = await mission.evaluate("(el) => el.classList.contains('selected') || el.classList.contains('active')")
                if not is_selected:
                    await self._human_click(page, mission)
                    await asyncio.sleep(random.uniform(0.3, 0.6))
            except Exception as e:
                print(f"! Could not ensure asteroid mission selection: {e}")

            # Some UIs keep submit disabled until mission is selected; wait a bit more if needed
            print("? Sending fleet...")
            submit_btn_selector = "#btn-submit-fleet"
            await page.wait_for_selector(submit_btn_selector, state="visible")
            await asyncio.sleep(0.5) # Give UI a moment
            try:
                await page.wait_for_selector(f"{submit_btn_selector}:not(.disabled)", state="visible", timeout=5000)
            except Exception:
                print("! Submit button still disabled. Waiting a bit more...")
                # Retry mission click once more then wait
                try:
                    mission = page.locator(".mission-item.ASTEROID_MINING")
                    await self._human_click(page, mission)
                except Exception:
                    pass
                await asyncio.sleep(2.0)

            await self._human_click(page, submit_btn_selector)
            
            print("? Fleet sent successfully!")
            await asyncio.sleep(random.uniform(1.5, 2.4))
            
            # Return to galaxy
            print("? Returning to galaxy...")
            await page.goto(galaxy_url)
            await page.wait_for_selector("#systemInput", state="visible")
            print("V Back at galaxy view")
            
            return True
            
        except Exception as e:
            print(f"? Error during fleet dispatch: {e}")
            # Try to return to galaxy
            try:
                await page.goto(galaxy_url)
                await page.wait_for_selector("#systemInput", state="visible")
            except:
                pass
            return False

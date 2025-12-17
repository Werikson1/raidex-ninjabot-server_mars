"""
Fleet Dispatcher Module
Handles fleet selection and dispatch to asteroids using fleet groups
"""

import asyncio
import random
import time
from urllib.parse import urlparse, parse_qs
from playwright.async_api import Page
import modules.config as config


class FleetDispatcher:
    def __init__(self, fleet_group_name: str = "", fleet_group_value: str = ""):
        self.fleet_group_name = fleet_group_name
        self.fleet_group_value = fleet_group_value

    async def _human_click(self, page: Page, selector):
        """Click with a small randomized delay to look human."""
        if isinstance(selector, str):
            loc = page.locator(selector)
        else:
            loc = selector
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

    async def _wait_for_options(self, page: Page, minimum: int = 1, retries: int = 15, delay_ms: int = 200):
        """Wait until the fleet group select has at least `minimum` non-empty options."""
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

    async def _select_fleet_group(self, page: Page) -> bool:
        """Select the configured fleet group from #fleetGroupSelect."""
        try:
            start = time.monotonic()
            select = page.locator("#fleetGroupSelect")
            await select.wait_for(state="visible", timeout=12000)
            await select.scroll_into_view_if_needed()

            # Wait for options to be populated (page now injects fleet groups later)
            options_ready = await self._wait_for_options(page, minimum=1, retries=24, delay_ms=250)
            if not options_ready:
                await self._log_debug_options(page)
                print("!! Fleet group options did not load in time")
                return False

            target_label = self.fleet_group_name or ""
            target_value = self.fleet_group_value or ""

            # Skip work if already selected
            try:
                current_val = await select.evaluate("(sel) => sel.value || ''")
                current_text = await select.evaluate(
                    "(sel) => { const o = sel.selectedOptions[0]; return o ? (o.textContent||'').trim() : ''; }"
                )
                if (target_value and current_val == target_value) or (target_label and current_text == target_label):
                    if current_val:
                        self.fleet_group_value = current_val
                    return True
            except Exception:
                pass

            # Fetch options once for faster matching
            try:
                options = await select.evaluate(
                    "(sel) => Array.from(sel.options).map(o => ({value:o.value,label:(o.textContent||'').trim()}))"
                )
            except Exception:
                options = []

            matched = False
            norm = lambda s: (s or "").strip().casefold()

            # Helper: set value via JS quickly
            async def _set_value(val: str):
                if not val:
                    return False
                try:
                    await select.select_option(value=val)
                except Exception:
                    pass
                try:
                    await select.evaluate(
                        "(sel, val) => { sel.value = val; sel.dispatchEvent(new Event('input', {bubbles:true})); sel.dispatchEvent(new Event('change', {bubbles:true})); sel.dispatchEvent(new Event('blur', {bubbles:true})); }",
                        val,
                    )
                    current = await select.evaluate("(sel) => sel.value || ''")
                    return current == val
                except Exception:
                    return False
            
            # 1) Try by label first (visible text)
            if target_label and options:
                target_label_norm = norm(target_label)
                for opt in options:
                    if norm(opt["label"]) == target_label_norm:
                        matched = await _set_value(opt["value"])
                        if matched:
                            self.fleet_group_value = opt["value"]
                            target_value = opt["value"]
                            print(f"V Selected fleet group by label: {target_label}")
                        break
                # Soft fallback: partial label match if exact failed
                if not matched:
                    candidates = [opt for opt in options if target_label_norm in norm(opt["label"])]
                    if len(candidates) == 1:
                        chosen = candidates[0]
                        matched = await _set_value(chosen["value"])
                        if matched:
                            self.fleet_group_value = chosen["value"]
                            target_value = chosen["value"]
                            print(f"V Selected fleet group by partial label: {chosen['label']}")
            
            # 2) Try by value
            if not matched and target_value:
                matched = await _set_value(target_value)
                if matched:
                    print(f"V Selected fleet group by value: {target_value}")
            
            # 3) Force via JS if needed
            if not matched and target_value:
                matched = await _set_value(target_value)
                if matched:
                    print(f"V Selected fleet group via JS: {target_value}")
            
            if not matched:
                # Log available options for debug on failure
                await self._log_debug_options(page)
                print(f"!! Fleet group selection failed for {target_label or target_value}")
                return False

            current_val = await select.evaluate("(sel) => sel.value || ''")
            if target_value and current_val != target_value:
                await self._log_debug_options(page)
                print(f"!! Fleet group selection mismatch. Expected {target_value}, got {current_val}")
                return False

            elapsed_ms = (time.monotonic() - start) * 1000
            print(f"V Fleet group ready in {elapsed_ms:.0f}ms")
            
            # Short settle delay to stay below the 3s budget
            await asyncio.sleep(random.uniform(0.3, 0.55))
            return True
            
        except Exception as e:
            print(f"! Could not select fleet group: {e}")
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
            await page.wait_for_selector("#fleetGroupSelect", timeout=120000)
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
        for attempt in range(6):
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
                        await p.wait_for_selector("#fleetGroupSelect", timeout=12000)
                    return p
            await ctx.wait_for_timeout(600)

        # Navigate current page directly as fallback
        fleet_url = self._build_fleet_url()

        print(f"[debug] navigating to fleet page fallback: {fleet_url}")
        await page.goto(fleet_url, timeout=15000)
        await page.wait_for_selector("#fleetGroupSelect", timeout=15000)
        return page
    
    async def dispatch_to_asteroid(self, page: Page, galaxy_url: str) -> bool:
        """
        Dispatch fleet to an asteroid using fleet group selection.
        
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
            
            # Select fleet group from dropdown
            print(f"? Selecting fleet group: {self.fleet_group_name or self.fleet_group_value}")
            if not await self._select_fleet_group(page):
                print("!! Fleet group selection failed")
                return False

            await asyncio.sleep(random.uniform(1, 2.2))
            
            # Step 1: Click Next (Step 1 -> 2)
            print("? Clicking Next (1)...")
            next_btn_selector = "#btn-next-fleet2"
            await page.wait_for_selector(next_btn_selector, state="visible")
            
            # Wait for button to become enabled
            try:
                await page.wait_for_selector(f"{next_btn_selector}:not(.disabled)", state="visible", timeout=12000)
            except Exception:
                print("! Next button still disabled. Waiting a bit more...")
                await asyncio.sleep(1.0)
                try:
                    await page.wait_for_selector(f"{next_btn_selector}:not(.disabled)", state="visible", timeout=12000)
                except Exception:
                    print("!! Next button failed to enable.")
                    return False

            await self._human_click(page, next_btn_selector)
            await asyncio.sleep(random.uniform(1.5, 2.5))
            
            # Step 3: Click Next (Step 2 -> 3)
            print("? Clicking Next (2)...")
            next_btn3_selector = "#btn-next-fleet3"
            await page.wait_for_selector(next_btn3_selector, state="visible")
            await asyncio.sleep(0.5)
            try:
                await page.wait_for_selector(f"{next_btn3_selector}:not(.disabled)", state="visible", timeout=12000)
            except Exception:
                print("! Next button (2) still disabled. Waiting a bit more...")
                try:
                    mission = page.locator(".mission-item.ASTEROID_MINING")
                    await self._human_click(page, mission)
                except Exception:
                    pass
                await asyncio.sleep(2.0)
            
            await self._human_click(page, next_btn3_selector)
            await asyncio.sleep(random.uniform(1.7, 1.4))
            
            # Step 4: Ensure mission selection (Asteroid Mining) and click Send Fleet
            try:
                mission = page.locator(".mission-item.ASTEROID_MINING")
                await mission.wait_for(state="visible", timeout=12000)
                is_selected = await mission.evaluate("(el) => el.classList.contains('selected') || el.classList.contains('active')")
                if not is_selected:
                    await self._human_click(page, mission)
                    await asyncio.sleep(random.uniform(1.3, 2.6))
            except Exception as e:
                print(f"! Could not ensure asteroid mission selection: {e}")

            print("? Sending fleet...")
            submit_btn_selector = "#btn-submit-fleet"
            await page.wait_for_selector(submit_btn_selector, state="visible")
            await asyncio.sleep(0.5)
            try:
                await page.wait_for_selector(f"{submit_btn_selector}:not(.disabled)", state="visible", timeout=12000)
            except Exception:
                print("! Submit button still disabled. Waiting a bit more...")
                try:
                    mission = page.locator(".mission-item.ASTEROID_MINING")
                    await self._human_click(page, mission)
                except Exception:
                    pass
                await asyncio.sleep(2.0)

            await self._human_click(page, submit_btn_selector)
            
            print("V Fleet sent successfully!")
            await asyncio.sleep(random.uniform(1.5, 2.4))
            
            # Return to galaxy
            print("? Returning to galaxy...")
            await page.goto(galaxy_url)
            await page.wait_for_selector("#systemInput", state="visible")
            print("V Back at galaxy view")
            
            return True
            
        except Exception as e:
            print(f"? Error during fleet dispatch: {e}")
            try:
                await page.goto(galaxy_url)
                await page.wait_for_selector("#systemInput", state="visible")
            except:
                pass
            return False

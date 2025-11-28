"""
Fleet Dispatcher Module
Handles fleet selection and dispatch to asteroids
"""

import asyncio
import random
from playwright.async_api import Page


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

    async def _ensure_fleet_page(self, page: Page) -> Page:
        """Ensure we are on a fleet page, capturing popups if a new tab opens."""
        try:
            current_url = page.url
        except Exception:
            current_url = ""
        print(f"[debug] current page url before fleet: {current_url}")

        # If already on fleet page or selector exists, return current
        try:
            if current_url and "/fleet" in current_url:
                print("[debug] already on fleet page (current tab)")
                return page
            if await page.locator("#fleetGroupSelect").count() > 0:
                print("[debug] fleet selector present on current tab")
                return page
        except Exception:
            pass

        ctx = page.context
        print("[debug] polling pages for /fleet or selector")
        for attempt in range(15):  # up to ~15s
            for p in ctx.pages:
                try:
                    url = p.url or ""
                except Exception:
                    url = ""
                try:
                    has_selector = await p.locator("#fleetGroupSelect").count() > 0
                except Exception:
                    has_selector = False
                if "/fleet" in url or has_selector:
                    print(f"[debug] using page {url} selector={has_selector}")
                    return p
            await ctx.wait_for_timeout(1000)

        # Last fallback: wait for navigation on current page
        print("[debug] final fallback waiting for navigation on current page")
        await page.wait_for_url("**/fleet**", timeout=15000)
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
            await select.wait_for(state="visible")
            await select.scroll_into_view_if_needed()
            await self._wait_for_options(page, minimum=2, retries=20, delay_ms=200)

            options = await select.evaluate(
                "(sel) => Array.from(sel.options).map(o => ({value:o.value,label:(o.textContent||'').trim()}))"
            )
            print(f"Debug fleet options: {options}")

            target_value = self.fleet_group_value
            matched = False

            # 1) Try by label first (less brittle to trailing spaces)
            try:
                await select.select_option(label=self.fleet_group_name)
                matched = True
                # update target_value to the selected option
                selected_value = await select.evaluate("(sel) => sel.value")
                if selected_value:
                    target_value = selected_value
                    self.fleet_group_value = selected_value
            except Exception:
                matched = False

            # 2) Try by value if label path failed
            if not matched:
                try:
                    await select.select_option(value=target_value)
                    matched = True
                except Exception:
                    matched = False

            # 3) Last resort: force via JS and change/input events
            if not matched and target_value:
                try:
                    await select.evaluate(
                        "(sel, val) => { sel.value = val; sel.dispatchEvent(new Event('input', {bubbles:true})); sel.dispatchEvent(new Event('change', {bubbles:true})); }",
                        target_value,
                    )
                    current = await select.evaluate("(sel) => sel.value")
                    matched = current == target_value
                except Exception:
                    matched = False

            current_value = await select.evaluate("(sel) => sel.value")
            if not matched or current_value != target_value:
                await self._log_debug_options(page)
                print(f"!! Fleet group selection failed. Expected {target_value}, got {current_value}")
                return False

            print(f"V Fleet group selected: {self.fleet_group_name} (ID: {target_value})")
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
            
            # Step 4: Click Send Fleet
            print("? Sending fleet...")
            submit_btn_selector = "#btn-submit-fleet"
            await page.wait_for_selector(submit_btn_selector, state="visible")
            await asyncio.sleep(0.5) # Give UI a moment
            try:
                await page.wait_for_selector(f"{submit_btn_selector}:not(.disabled)", state="visible", timeout=5000)
            except Exception:
                print("! Submit button still disabled. Waiting a bit more...")
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

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

    async def _log_debug_options(self, page: Page, select=None):
        """Log available fleet group options for debugging."""
        select = select or page.locator("#fleetGroupSelect")
        try:
            options = await select.evaluate(
                "(sel) => Array.from(sel.options).map(o => ({value:o.value,label:(o.textContent||'').trim()}))"
            )
            print(f"Debug fleet options: {options}")
        except Exception as e:
            print(f"Could not read fleet options: {e}")

    async def _wait_for_options(
        self,
        page: Page,
        select=None,
        minimum: int = 1,
        timeout_ms: int = 15000,
        poll_ms: int = 250,
    ):
        """Wait until the fleet group select has at least `minimum` usable options."""
        select = select or page.locator("#fleetGroupSelect")
        deadline = time.monotonic() + (max(0, int(timeout_ms)) / 1000.0)
        while time.monotonic() < deadline:
            try:
                options = await select.evaluate("""
                    (sel) => {
                        const opts = Array.from(sel.options || []);
                        const norm = (s) => (s || '').trim().toLowerCase();
                        const usable = opts.filter(o => {
                            const val = (o.value || '').trim();
                            const label = norm(o.textContent);
                            if (val) return true;
                            if (!label) return false;
                            // Skip the common placeholder option
                            if (label === 'select fleet group') return false;
                            return true;
                        });
                        return usable.length;
                    }
                """)
                if int(options or 0) >= minimum:
                    return True
            except Exception:
                pass
            await page.wait_for_timeout(poll_ms)
        return False

    async def _resolve_fleet_group_select(self, page: Page):
        """
        Resolve the fleet group <select> element, allowing fallbacks if the id changes.
        Returns (locator, hint_str).
        """
        candidates = [
            ("#fleetGroupSelect", page.locator("#fleetGroupSelect")),
            ("select#fleetGroupSelect", page.locator("select#fleetGroupSelect")),
            ("select[aria-haspopup='menu']", page.locator("select[aria-haspopup='menu']")),
            ("xpath //select[@id='fleetGroupSelect']", page.locator("xpath=//select[@id='fleetGroupSelect']")),
            ("xpath //select[@aria-haspopup='menu']", page.locator("xpath=//select[@aria-haspopup='menu']")),
            ("select has 'Select fleet group'", page.locator("select").filter(has_text="Select fleet group")),
            ("select[id*='fleetGroup']", page.locator("select[id*='fleetGroup']")),
        ]

        for hint, loc in candidates:
            try:
                if await loc.count() <= 0:
                    continue
                single = loc.first
                try:
                    if await single.is_visible():
                        return single, hint
                except Exception:
                    return single, hint
            except Exception:
                continue

        return page.locator("#fleetGroupSelect"), "#fleetGroupSelect"

    async def _select_fleet_group_via_xpath(self, page: Page, target_label: str, target_value: str) -> bool:
        """Last-resort selection using XPath (document.evaluate) in the page context."""
        if not target_label and not target_value:
            return False

        try:
            result = await page.evaluate(
                """
                ({label, value}) => {
                    const xpaths = [
                        "//select[@id='fleetGroupSelect']",
                        "//select[@aria-haspopup='menu']",
                        "//select[contains(@id,'fleetGroup')]",
                    ];

                    const byXPath = (xp) =>
                        document.evaluate(
                            xp,
                            document,
                            null,
                            XPathResult.FIRST_ORDERED_NODE_TYPE,
                            null
                        ).singleNodeValue;

                    let sel = null;
                    let used = null;
                    for (const xp of xpaths) {
                        const node = byXPath(xp);
                        if (node) {
                            sel = node;
                            used = xp;
                            break;
                        }
                    }
                    if (!sel) return { ok: false, reason: "select_not_found" };

                    const opts = Array.from(sel.options || []);
                    const norm = (s) => (s || "").trim().toLowerCase();

                    let idx = -1;
                    if (value) idx = opts.findIndex((o) => (o.value || "") === value);
                    if (idx < 0 && label) idx = opts.findIndex((o) => norm(o.textContent) === norm(label));
                    if (idx < 0 && label) idx = opts.findIndex((o) => norm(o.textContent).includes(norm(label)));
                    if (idx < 0) return { ok: false, reason: "option_not_found", used };

                    sel.selectedIndex = idx;
                    sel.value = (opts[idx] && opts[idx].value) ? opts[idx].value : sel.value;
                    sel.dispatchEvent(new Event("input", { bubbles: true }));
                    sel.dispatchEvent(new Event("change", { bubbles: true }));
                    sel.dispatchEvent(new Event("blur", { bubbles: true }));

                    const selected = sel.selectedOptions && sel.selectedOptions[0];
                    return {
                        ok: true,
                        used,
                        value: sel.value || "",
                        label: selected ? (selected.textContent || "").trim() : "",
                    };
                }
                """,
                {"label": target_label, "value": target_value},
            )
        except Exception as e:
            print(f"! XPath fallback evaluate failed: {e}")
            return False

        try:
            if not isinstance(result, dict) or not result.get("ok"):
                return False
            chosen_value = (result.get("value") or "").strip()
            if chosen_value:
                self.fleet_group_value = chosen_value
            return True
        except Exception:
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

    async def _ensure_fleet2_target(self, page: Page, galaxy: int, system: int, position: int) -> bool:
        """Force-fill the Fleet Step 2 target coordinates and planet type (moon)."""
        try:
            await page.wait_for_selector("#fleet2_target_x", timeout=12000)
            await page.wait_for_selector("#fleet2_target_y", timeout=12000)
            await page.wait_for_selector("#fleet2_target_z", timeout=12000)
        except Exception:
            return False

        try:
            result = await page.evaluate(
                """
                ({g, s, p}) => {
                    const set = (id, val) => {
                        const el = document.getElementById(id);
                        if (!el) return false;
                        el.value = String(val);
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new Event('blur', { bubbles: true }));
                        return true;
                    };

                    const ok =
                        set('fleet2_target_x', g) &&
                        set('fleet2_target_y', s) &&
                        set('fleet2_target_z', p);

                    // Asteroid Mining uses moon target type in this UI
                    const moon = document.querySelector('#target_planet_type_container a[data-planet-type="2"]');
                    if (moon) moon.click();

                    const read = (id) => {
                        const el = document.getElementById(id);
                        return el ? String(el.value || '').trim() : '';
                    };

                    return {
                        ok,
                        x: read('fleet2_target_x'),
                        y: read('fleet2_target_y'),
                        z: read('fleet2_target_z'),
                        moonClicked: !!moon,
                    };
                }
                """,
                {"g": int(galaxy), "s": int(system), "p": int(position)},
            )
            if isinstance(result, dict):
                ok = bool(result.get("ok"))
                if ok:
                    return True
        except Exception as e:
            print(f"! Could not set fleet2 target coords: {e}")

        return False

    async def _wait_for_fleet3(self, page: Page, timeout_ms: int = 15000) -> bool:
        """Wait for mission step (fleet3) container to become visible."""
        try:
            await page.wait_for_selector("#fleet3_content_container", state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    async def _select_fleet_group(self, page: Page) -> bool:
        """Select the configured fleet group from #fleetGroupSelect."""
        try:
            start = time.monotonic()
            select, select_hint = await self._resolve_fleet_group_select(page)
            try:
                await select.wait_for(state="attached", timeout=20000)
            except Exception:
                pass
            try:
                await select.wait_for(state="visible", timeout=12000)
                await select.scroll_into_view_if_needed()
            except Exception:
                pass

            # Wait for options to be populated (page now injects fleet groups later)
            options_ready = await self._wait_for_options(page, select=select, minimum=1, timeout_ms=20000, poll_ms=250)
            if not options_ready:
                # Some pages only populate fleet groups after a user interaction
                try:
                    await select.click()
                except Exception:
                    pass
                options_ready = await self._wait_for_options(page, select=select, minimum=1, timeout_ms=20000, poll_ms=300)
            if not options_ready:
                await self._log_debug_options(page, select=select)
                print(f"!! Fleet group options did not load in time (selector={select_hint})")
                return False

            target_label = self.fleet_group_name or ""
            target_value = self.fleet_group_value or ""
            xpath_attempted = False

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

            # Helpers: set by value or by label (covers pages with empty option values)
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

            async def _set_label(label: str):
                if not label:
                    return False
                try:
                    await select.select_option(label=label)
                except Exception:
                    pass
                try:
                    ok = await select.evaluate(
                        """
                        (sel, label) => {
                            const norm = (s) => (s || '').trim().toLowerCase();
                            const target = norm(label);
                            const opts = Array.from(sel.options || []);
                            const idx = opts.findIndex(o => norm(o.textContent) === target);
                            if (idx < 0) return false;
                            sel.selectedIndex = idx;
                            sel.dispatchEvent(new Event('input', {bubbles:true}));
                            sel.dispatchEvent(new Event('change', {bubbles:true}));
                            sel.dispatchEvent(new Event('blur', {bubbles:true}));
                            return true;
                        }
                        """,
                        label,
                    )
                    if not ok:
                        return False
                    current_label = await select.evaluate(
                        "(sel) => { const o = sel.selectedOptions && sel.selectedOptions[0]; return o ? (o.textContent||'').trim() : ''; }"
                    )
                    return norm(current_label) == norm(label)
                except Exception:
                    return False
             
            # 1) Try by label first (visible text)
            if target_label and options:
                target_label_norm = norm(target_label)
                for opt in options:
                    if norm(opt["label"]) == target_label_norm:
                        if opt.get("value"):
                            matched = await _set_value(opt["value"])
                        else:
                            matched = await _set_label(opt["label"])
                        if matched:
                            current_val = await select.evaluate("(sel) => sel.value || ''")
                            if current_val:
                                self.fleet_group_value = current_val
                                target_value = current_val
                            print(f"V Selected fleet group by label: {target_label}")
                        break
                # Soft fallback: partial label match if exact failed
                if not matched:
                    candidates = [opt for opt in options if target_label_norm in norm(opt["label"])]
                    if len(candidates) == 1:
                        chosen = candidates[0]
                        if chosen.get("value"):
                            matched = await _set_value(chosen["value"])
                        else:
                            matched = await _set_label(chosen["label"])
                        if matched:
                            current_val = await select.evaluate("(sel) => sel.value || ''")
                            if current_val:
                                self.fleet_group_value = current_val
                                target_value = current_val
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

            # 4) Extra attempt via XPath (last resort)
            if not matched and not xpath_attempted:
                xpath_attempted = True
                print("! Retrying fleet group selection via XPath fallback...")
                if await self._select_fleet_group_via_xpath(page, target_label, target_value):
                    # Re-resolve to ensure we validate against the right <select>
                    select, select_hint = await self._resolve_fleet_group_select(page)
                    try:
                        current_val = await select.evaluate("(sel) => sel.value || ''")
                        if current_val:
                            self.fleet_group_value = current_val
                            target_value = current_val
                    except Exception:
                        pass
                    matched = True
                    print(f"V Selected fleet group via XPath fallback (selector={select_hint})")
            
            if not matched:
                # Log available options for debug on failure
                await self._log_debug_options(page, select=select)
                print(f"!! Fleet group selection failed for {target_label or target_value}")
                return False

            current_val = await select.evaluate("(sel) => sel.value || ''")
            if target_value and current_val and current_val != target_value:
                # If label matches, accept and update stored value (IDs can change server-side)
                current_label = ""
                try:
                    current_label = await select.evaluate(
                        "(sel) => { const o = sel.selectedOptions && sel.selectedOptions[0]; return o ? (o.textContent||'').trim() : ''; }"
                    )
                except Exception:
                    current_label = ""

                if target_label and norm(current_label) == norm(target_label):
                    print(
                        f"! Fleet group value mismatch but label matches ('{current_label}'). "
                        f"Updating value {target_value} -> {current_val}"
                    )
                    self.fleet_group_value = current_val
                    target_value = current_val
                else:
                    # One more chance (if we didn't already) using XPath before failing hard
                    if not xpath_attempted:
                        xpath_attempted = True
                        print("! Fleet group mismatch. Retrying via XPath fallback...")
                        if await self._select_fleet_group_via_xpath(page, target_label, target_value):
                            select, select_hint = await self._resolve_fleet_group_select(page)
                            try:
                                current_val = await select.evaluate("(sel) => sel.value || ''")
                                if current_val:
                                    self.fleet_group_value = current_val
                                    target_value = current_val
                            except Exception:
                                pass
                        else:
                            await self._log_debug_options(page, select=select)
                            print(f"!! Fleet group selection mismatch. Expected {target_value}, got {current_val}")
                            return False
                    else:
                        await self._log_debug_options(page, select=select)
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
            for p in reversed(list(ctx.pages)):
                try:
                    if p.is_closed():
                        continue
                except Exception:
                    pass
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

    async def _close_stale_fleet_pages(self, context, keep_page: Page):
        """Close extra /fleet tabs to reduce stale DOM issues."""
        closed = 0
        for p in list(context.pages):
            if p == keep_page:
                continue
            try:
                if p.is_closed():
                    continue
            except Exception:
                continue
            try:
                url = p.url or ""
            except Exception:
                url = ""
            if "/fleet" in url and "/fleet/autoexpedition" not in url:
                try:
                    await p.close()
                    closed += 1
                except Exception:
                    pass
        if closed:
            print(f"[debug] closed {closed} stale fleet tab(s)")
    
    async def dispatch_to_asteroid(self, page: Page, galaxy_url: str, target_coords=None) -> bool:
        """
        Dispatch fleet to an asteroid using fleet group selection.
        
        Args:
            page: Playwright page object
            galaxy_url: URL to return to after dispatch
            target_coords: Optional tuple (galaxy, system, position) to force-fill destination
        
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
            try:
                await self._close_stale_fleet_pages(page.context, page)
            except Exception:
                pass
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

            # Step 2: Ensure target coords (helps when asteroid click fails to prefill /fleet)
            if target_coords and len(target_coords) == 3:
                try:
                    tgt_g, tgt_s, tgt_p = target_coords
                    print(f"[debug] ensuring fleet2 target coords: [{tgt_g}:{tgt_s}:{tgt_p}]")
                    await self._ensure_fleet2_target(page, int(tgt_g), int(tgt_s), int(tgt_p))
                    # Give the page a moment to recalc distance/briefing
                    await asyncio.sleep(random.uniform(0.35, 0.7))
                except Exception:
                    pass
            
            # Step 3: Click Next (Step 2 -> 3)
            next_btn3_selector = "#btn-next-fleet3"
            reached_fleet3 = False
            for attempt in range(1, 4):
                print(f"? Clicking Next (2) [attempt {attempt}/3]...")
                await page.wait_for_selector(next_btn3_selector, state="visible")
                await asyncio.sleep(0.35)
                try:
                    await page.wait_for_selector(f"{next_btn3_selector}:not(.disabled)", state="visible", timeout=12000)
                except Exception:
                    print("! Next button (2) still disabled. Waiting a bit more...")
                    await asyncio.sleep(1.5)

                await self._human_click(page, next_btn3_selector)
                await asyncio.sleep(random.uniform(0.6, 1.1))

                if await self._wait_for_fleet3(page, timeout_ms=12000):
                    reached_fleet3 = True
                    break

                # Re-apply target coords and retry (page sometimes ignores first click)
                if target_coords and len(target_coords) == 3:
                    try:
                        tgt_g, tgt_s, tgt_p = target_coords
                        print("! Fleet3 not visible yet. Re-applying target coords and retrying...")
                        await self._ensure_fleet2_target(page, int(tgt_g), int(tgt_s), int(tgt_p))
                        await asyncio.sleep(random.uniform(0.35, 0.7))
                    except Exception:
                        pass

            if not reached_fleet3:
                print("!! Could not reach mission step (fleet3) - aborting dispatch")
                return False
            
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
            await page.wait_for_selector(submit_btn_selector, state="visible", timeout=20000)
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

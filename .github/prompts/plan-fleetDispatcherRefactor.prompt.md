# Plan: Refatorar Fleet Dispatcher para usar Fleet Group

## Objetivo
Remover a lógica de `asteroid_miner_amount` e usar o seletor `#fleetGroupSelect` igual ao Expedition.

---

## 1. `modules/fleet_dispatcher.py`

**Substituir TODO o arquivo por:**

```python
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

    async def _select_fleet_group(self, page: Page) -> bool:
        """Select the configured fleet group from #fleetGroupSelect."""
        try:
            select = page.locator("#fleetGroupSelect")
            await select.wait_for(state="visible", timeout=6000)
            await select.scroll_into_view_if_needed()
            
            # Wait for options to be populated
            await self._wait_for_options(page, minimum=1, retries=10, delay_ms=200)
            
            # Log available options for debug
            await self._log_debug_options(page)
            
            target_label = self.fleet_group_name or ""
            target_value = self.fleet_group_value or ""
            matched = False
            
            # 1) Try by label first (visible text)
            if target_label:
                try:
                    await select.select_option(label=target_label)
                    matched = True
                    current_val = await select.evaluate("(sel) => sel.value")
                    if current_val:
                        self.fleet_group_value = current_val
                    print(f"✓ Selected fleet group by label: {target_label}")
                except Exception:
                    matched = False
            
            # 2) Try by value
            if not matched and target_value:
                try:
                    await select.select_option(value=target_value)
                    matched = True
                    print(f"✓ Selected fleet group by value: {target_value}")
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
                    if matched:
                        print(f"✓ Selected fleet group via JS: {target_value}")
                except Exception:
                    matched = False
            
            if not matched:
                print(f"!! Fleet group selection failed for {target_label or target_value}")
                return False
            
            await asyncio.sleep(random.uniform(0.3, 0.6))
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

            await asyncio.sleep(random.uniform(0.6, 1.2))
            
            # Step 1: Click Next (Step 1 -> 2)
            print("? Clicking Next (1)...")
            next_btn_selector = "#btn-next-fleet2"
            await page.wait_for_selector(next_btn_selector, state="visible")
            
            # Wait for button to become enabled
            try:
                await page.wait_for_selector(f"{next_btn_selector}:not(.disabled)", state="visible", timeout=5000)
            except Exception:
                print("! Next button still disabled. Waiting a bit more...")
                await asyncio.sleep(1.0)
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
            await asyncio.sleep(0.5)
            try:
                await page.wait_for_selector(f"{next_btn3_selector}:not(.disabled)", state="visible", timeout=5000)
            except Exception:
                print("! Next button (2) still disabled. Waiting a bit more...")
                try:
                    mission = page.locator(".mission-item.ASTEROID_MINING")
                    await self._human_click(page, mission)
                except Exception:
                    pass
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

            print("? Sending fleet...")
            submit_btn_selector = "#btn-submit-fleet"
            await page.wait_for_selector(submit_btn_selector, state="visible")
            await asyncio.sleep(0.5)
            try:
                await page.wait_for_selector(f"{submit_btn_selector}:not(.disabled)", state="visible", timeout=5000)
            except Exception:
                print("! Submit button still disabled. Waiting a bit more...")
                try:
                    mission = page.locator(".mission-item.ASTEROID_MINING")
                    await self._human_click(page, mission)
                except Exception:
                    pass
                await asyncio.sleep(2.0)

            await self._human_click(page, submit_btn_selector)
            
            print("✓ Fleet sent successfully!")
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
```

---

## 2. `templates/asteroid_miner.html`

### 2.1 Substituir o campo `Asteroid Miner Amount` por Fleet Group

**De:**
```html
<div class="form-group">
    <label>Asteroid Miner Amount</label>
    <input type="number" id="ASTEROID_MINER_AMOUNT" name="ASTEROID_MINER_AMOUNT" min="1" step="1" class="compact-input" placeholder="Quantidade de naves">
</div>
```

**Para:**
```html
<div class="form-group">
    <label>Fleet Group</label>
    <select id="asteroidFleetGroup" name="ASTEROID_FLEET_GROUP" class="compact-input">
        <option value="">Carregando grupos...</option>
    </select>
</div>
```

### 2.2 Adicionar no JavaScript (após `const planetSelect`)

```javascript
const fleetGroupSelect = document.getElementById('asteroidFleetGroup');
```

### 2.3 Adicionar função `populateFleetGroups`

```javascript
const populateFleetGroups = async (currentValue, currentName) => {
    try {
        const data = await fetchJson('/api/fleet/groups');
        const groups = data.groups || [];
        fleetGroupSelect.innerHTML = '';
        if (!groups.length) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'No fleet groups found';
            fleetGroupSelect.appendChild(opt);
            return;
        }
        groups.forEach(g => {
            const opt = document.createElement('option');
            opt.value = g.value;
            opt.textContent = g.name;
            fleetGroupSelect.appendChild(opt);
        });
        if (currentValue) {
            setSelectValue(fleetGroupSelect, currentValue);
        } else if (currentName) {
            const option = Array.from(fleetGroupSelect.options).find(o => o.textContent === currentName);
            if (option) {
                fleetGroupSelect.value = option.value;
            }
        }
    } catch (error) {
        console.error('Error loading fleet groups:', error);
    }
};
```

### 2.4 No `loadConfig`, adicionar chamada:

```javascript
// Dentro de loadConfig, após populatePlanets:
const asteroidMode = config.asteroid_mode || {};
await populateFleetGroups(asteroidMode.fleet_group_value, asteroidMode.fleet_group_name);
```

### 2.5 Adicionar auto-save para fleet group:

```javascript
// Auto-save fleet group selection
fleetGroupSelect.addEventListener('change', async () => {
    try {
        const fleetOption = fleetGroupSelect.options[fleetGroupSelect.selectedIndex];
        await fetchJson('/api/asteroid/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                fleet_group_name: fleetOption ? fleetOption.textContent : '',
                fleet_group_value: fleetGroupSelect.value
            })
        });
        console.log('Fleet group saved:', fleetGroupSelect.value);
    } catch (error) {
        console.error('Error saving fleet group:', error);
        alert('Failed to save fleet group selection');
    }
});
```

---

## 3. Atualizar `modules/asteroid_miner_runner.py`

Onde o `FleetDispatcher` é instanciado, alterar de:

```python
FleetDispatcher(
    fleet_group_name=...,
    fleet_group_value=...,
    asteroid_miner_amount=config.get("ASTEROID_MINER_AMOUNT", 0)
)
```

Para:

```python
FleetDispatcher(
    fleet_group_name=asteroid_mode.get("fleet_group_name", ""),
    fleet_group_value=asteroid_mode.get("fleet_group_value", "")
)
```

---

## 4. Atualizar `web_app.py` (endpoint `/api/asteroid/config`)

Garantir que o endpoint salva `fleet_group_name` e `fleet_group_value` no `asteroid_mode`:

```python
# No POST /api/asteroid/config
if 'fleet_group_name' in data:
    asteroid_mode['fleet_group_name'] = data['fleet_group_name']
if 'fleet_group_value' in data:
    asteroid_mode['fleet_group_value'] = data['fleet_group_value']
```

---

## Checklist

- [ ] Substituir `modules/fleet_dispatcher.py`
- [ ] Atualizar `templates/asteroid_miner.html` (HTML + JS)
- [ ] Atualizar `modules/asteroid_miner_runner.py` (instanciação do FleetDispatcher)
- [ ] Atualizar `web_app.py` (salvar fleet_group no config)
- [ ] Testar seleção de fleet group no Asteroid Miner

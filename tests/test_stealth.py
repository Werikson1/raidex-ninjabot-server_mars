"""
Stealth Verification Script
Tests if the stealth evasions are working correctly
"""

import asyncio
import os
import sys
from playwright.async_api import async_playwright

# Ensure project root is importable when running the test directly
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from modules.stealth import apply_stealth, get_stealth_args, get_stealth_user_agent


async def test_stealth():
    print("=" * 70)
    print("TESTING STEALTH MODE")
    print("=" * 70)

    async with async_playwright() as p:
        probe = await p.chromium.launch(headless=True)
        chrome_version = probe.version
        await probe.close()
        stealth_args = get_stealth_args() + ["--start-maximized"]
        user_agent = get_stealth_user_agent(chrome_version=chrome_version)
        viewport = {"width": 1366, "height": 768}

        context = await p.chromium.launch_persistent_context(
            user_data_dir="test_profile",
            headless=False,
            args=stealth_args,
            viewport=viewport,
            locale="en-US",
            color_scheme="light",
            user_agent=user_agent,
            ignore_default_args=["--enable-automation"],
        )

        await apply_stealth(context, user_agent=user_agent, chrome_version=chrome_version)

        # Always start from a fresh page to guarantee init scripts ran
        page = await context.new_page()

        print("\n> Navigating to bot detection test site...")
        await page.goto("https://bot.sannysoft.com/")
        await page.wait_for_load_state("networkidle")

        print("\n> Checking detection indicators...\n")

        webdriver = await page.evaluate("navigator.webdriver")
        print(f"  navigator.webdriver: {webdriver} {'OK' if webdriver in (None, False) else 'DETECTED'}")

        plugins = await page.evaluate("navigator.plugins.length")
        print(f"  navigator.plugins: {plugins} {'OK' if plugins > 0 else 'SUSPICIOUS (0 plugins)'}")

        languages = await page.evaluate("navigator.languages")
        print(f"  navigator.languages: {languages}")

        has_chrome = await page.evaluate('typeof window.chrome !== "undefined"')
        print(f"  window.chrome: {has_chrome}")

        try:
            await page.evaluate("navigator.permissions.query({name: 'notifications'})")
            print("  navigator.permissions: OK")
        except Exception:
            print("  navigator.permissions: ERROR")

        print("\n" + "=" * 70)
        print("Press Ctrl+C to close the browser after inspection.")
        print("=" * 70)

        # Keep browser open for manual inspection
        await asyncio.sleep(30)
        await context.close()


if __name__ == "__main__":
    asyncio.run(test_stealth())

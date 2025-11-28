"""
Bot fingerprint probe using the new stealth context.
Runs a quick check against cypher.ogamex.net and reports key signals.
"""

import asyncio
from pprint import pprint

from playwright.async_api import async_playwright

from modules.stealth import apply_stealth, get_stealth_args, get_stealth_user_agent


async def main():
    stealth_args = get_stealth_args() + ["--start-maximized"]
    user_agent = get_stealth_user_agent()
    viewport = {"width": 1366, "height": 768}

    async with async_playwright() as p:
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

        await apply_stealth(context, user_agent=user_agent)

        page = context.pages[0] if context.pages else await context.new_page()

        await page.goto("https://cypher.ogamex.net/", wait_until="networkidle")

        detection = await page.evaluate(
            """(() => ({
                webdriver: navigator.webdriver,
                plugins: navigator.plugins.length,
                languages: navigator.languages,
                platform: navigator.platform,
                userAgent: navigator.userAgent,
                uaData: navigator.userAgentData ? navigator.userAgentData.brands : null,
            }))()"""
        )

        scripts = await page.evaluate(
            """Array.from(document.scripts).map(s => ({
                src: s.src || 'inline',
                content: s.src ? null : (s.textContent || '').slice(0, 200)
            }))"""
        )

        print("=== BOT DETECTION CHECK ===")
        print(f"Navigator.webdriver: {detection.get('webdriver')}")
        print(f"Plugins count: {detection.get('plugins')}")
        print(f"Platform: {detection.get('platform')}")
        print(f"User-Agent: {detection.get('userAgent')}")
        print(f"UA Brands: {detection.get('uaData')}")
        print()
        print("=== SCRIPTS LOADED ===")

        suspicious = []
        keywords = ["analytics", "track", "bot", "captcha", "recaptcha", "cloudflare", "fingerprint", "detect"]
        for i, script in enumerate(scripts):
            src = script["src"]
            is_suspicious = any(kw in src.lower() for kw in keywords)
            if is_suspicious:
                suspicious.append(src)
                print(f"!! SUSPICIOUS: {src}")
            elif i < 15:
                print(f"   {src}")

        print()
        print(f"Total scripts: {len(scripts)}")
        print(f"Suspicious scripts: {len(suspicious)}")

        print()
        print("=== INLINE SCRIPT ANALYSIS ===")
        inline_count = 0
        for script in scripts:
            if script["src"] == "inline" and script["content"]:
                inline_count += 1
                content = script["content"].lower()
                if any(kw in content for kw in ["webdriver", "automation", "headless", "phantom", "selenium"]):
                    print("!! FOUND BOT DETECTION IN INLINE SCRIPT:")
                    print(script["content"][:300])
        print(f"Total inline scripts: {inline_count}")

        await context.close()


if __name__ == "__main__":
    asyncio.run(main())

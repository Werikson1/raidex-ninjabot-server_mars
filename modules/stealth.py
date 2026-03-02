"""
Stealth Module - Bot Detection Evasion
Injects JavaScript to hide automation signals from detection systems.
Fingerprint values are aligned to the local host + Chromium version to avoid mismatches.
"""

import json
import os
import platform
from typing import Dict, List, Tuple

DEFAULT_LANGUAGES = ["en-US", "en", "pt-BR", "pt"]


def _get_device_memory_gb() -> int:
    """Best-effort device memory (GB) rounded to int."""
    try:
        import psutil  # type: ignore

        total_gb = max(1, int(round(psutil.virtual_memory().total / (1024 ** 3))))
        return min(total_gb, 64)
    except Exception:
        # Fallback: assume 8GB if unknown
        return 8


def _get_system_fingerprint() -> Dict[str, str]:
    """Collect host platform details to keep JS fingerprint aligned with the machine."""
    system_name = platform.system() or "Windows"
    release = platform.release() or "10"
    arch = platform.machine() or "x86_64"

    platform_name = "Windows" if system_name.lower().startswith("win") else ("Linux" if system_name.lower().startswith("linux") else system_name)
    platform_version = release if platform_name == "Windows" else "0.0.0"

    # UA platform token
    if platform_name == "Windows":
        ua_platform = f"Windows NT {platform_version}; Win64; x64"
        platform_value = "Windows"
        arch_token = "x86"
    elif platform_name == "Linux":
        ua_platform = "X11; Linux x86_64"
        platform_value = "Linux"
        arch_token = "x86"
    else:
        ua_platform = f"{platform_name}; {arch}"
        platform_value = platform_name
        arch_token = "x86"

    hw_threads = os.cpu_count() or 4
    device_memory = _get_device_memory_gb()

    return {
        "platform_name": platform_value,
        "platform_version": f"{platform_version}.0.0",
        "ua_platform": ua_platform,
        "architecture": arch_token,
        "hardware_concurrency": max(1, int(hw_threads)),
        "device_memory": max(1, int(device_memory)),
    }


def _build_brands(chrome_version: str) -> Tuple[List[Dict[str, str]], str]:
    """Return CH brands array and full version respecting the detected Chromium build."""
    full_version = chrome_version or "120.0.0.0"
    try:
        major = full_version.split(".")[0]
    except Exception:
        major = "120"

    brands = [
        {"brand": "Google Chrome", "version": major},
        {"brand": "Chromium", "version": major},
        {"brand": "Not A(Brand", "version": "99"},
    ]
    return brands, full_version


def build_user_agent(chrome_version: str = None, ua_platform: str = None) -> str:
    """Construct a UA string aligned with the local Chromium build and platform."""
    sys_fp = _get_system_fingerprint()
    ua_platform = ua_platform or sys_fp["ua_platform"]
    full_version = chrome_version or "120.0.0.0"
    return f"Mozilla/5.0 ({ua_platform}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{full_version} Safari/537.36"


def build_stealth_headers(user_agent: str = None, brands: List[Dict[str, str]] = None, platform_name: str = None) -> Dict[str, str]:
    """
    Build a realistic set of HTTP headers to reduce automation fingerprints.
    Caller should pass the same UA/brands used in JS fingerprinting.
    """
    sys_fp = _get_system_fingerprint()
    ua = user_agent or build_user_agent()
    brands = brands or _build_brands(ua.split("Chrome/")[-1] if "Chrome/" in ua else "")[0]
    platform_name = platform_name or sys_fp["platform_name"]

    def _format_brands(items: List[Dict[str, str]]) -> str:
        return ", ".join([f'"{b["brand"]}";v="{b["version"]}"' for b in items if b.get("brand") and b.get("version")])

    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
        "Cache-Control": "max-age=0",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-CH-UA": _format_brands(brands),
        "Sec-CH-UA-Platform": f'"{platform_name}"',
        "Sec-CH-UA-Mobile": "?0",
    }


def _build_plugin_script() -> str:
    """Return JS that creates PluginArray/MimeTypeArray with correct prototype surface."""
    return """
// Plugins + MimeTypes surface (simple but structured)
const _mimeTypes = [
    { type: 'application/pdf', suffixes: 'pdf', description: 'Portable Document Format' },
    { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format' },
];

class MimeType {
    constructor(data, plugin) {
        this.type = data.type;
        this.suffixes = data.suffixes;
        this.description = data.description;
        this.enabledPlugin = plugin || null;
    }
}
class MimeTypeArray extends Array {
    item(i) { return this[i] || null; }
    namedItem(name) { return this.find(m => m.type === name) || null; }
}

class Plugin {
    constructor(data, mimes) {
        this.name = data.name;
        this.filename = data.filename;
        this.description = data.description;
        mimes.forEach((mt, idx) => { this[idx] = mt; });
        this.length = mimes.length;
    }
    item(i) { return this[i] || null; }
    namedItem(name) { return Array.prototype.find.call(this, m => m.type === name) || null; }
}
class PluginArray extends Array {
    item(i) { return this[i] || null; }
    namedItem(name) { return this.find(p => p.name === name) || null; }
    refresh() { return this.length; }
}
Object.defineProperty(PluginArray.prototype, Symbol.toStringTag, { value: 'PluginArray' });
Object.defineProperty(MimeTypeArray.prototype, Symbol.toStringTag, { value: 'MimeTypeArray' });
Object.defineProperty(Plugin.prototype, Symbol.toStringTag, { value: 'Plugin' });
Object.defineProperty(MimeType.prototype, Symbol.toStringTag, { value: 'MimeType' });

const _plugins = [];
const mimeEntries = _mimeTypes.map(mt => new MimeType(mt));
const _pdfPlugin = new Plugin(
    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
    mimeEntries
);
mimeEntries.forEach(mt => { mt.enabledPlugin = _pdfPlugin; });
_plugins.push(_pdfPlugin);

const pluginArray = new PluginArray(..._plugins);
const mimeArray = new MimeTypeArray(...mimeEntries);
Object.setPrototypeOf(pluginArray, PluginArray.prototype);
Object.setPrototypeOf(mimeArray, MimeTypeArray.prototype);
// Expose constructors so instanceof checks pass
window.PluginArray = PluginArray;
window.MimeTypeArray = MimeTypeArray;
window.Plugin = Plugin;
window.MimeType = MimeType;

Object.defineProperty(navigator, 'plugins', { get: () => pluginArray });
Object.defineProperty(navigator, 'mimeTypes', { get: () => mimeArray });
"""


def _build_stealth_js(fingerprint: Dict[str, str], languages: List[str]) -> str:
    """Render the JS stealth shim using the provided fingerprint values."""
    brands_json = json.dumps(fingerprint["brands"])
    languages_json = json.dumps(languages or DEFAULT_LANGUAGES)
    platform_name = fingerprint["platform_name"]
    platform_version = fingerprint["platform_version"]
    architecture = fingerprint["architecture"]
    ua_full_version = fingerprint["ua_full_version"]
    hardware_concurrency = fingerprint["hardware_concurrency"]
    device_memory = fingerprint["device_memory"]
    platform_token = "Win32" if platform_name == "Windows" else platform_name

    return f"""
// Overwrite webdriver and known Playwright globals
Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
try {{ delete window.webdriver; }} catch (e) {{}}
try {{ if (window.navigator && 'webdriver' in window.navigator) {{ Object.defineProperty(window.navigator, 'webdriver', {{ get: () => undefined }}); }} }} catch (e) {{}}
try {{ if (window.chrome && window.chrome.runtime && 'id' in window.chrome.runtime) {{ Object.defineProperty(window.chrome, 'runtime', {{ get: () => {{}} }}); }} }} catch (e) {{}}
delete window.__nightmare;
delete window.__selenium_unwrapped;
delete window._Selenium_IDE_Recorder;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

// Stable languages, platform, hardware details
const languageList = {languages_json};
Object.defineProperty(navigator, 'languages', {{ get: () => languageList }});
Object.defineProperty(navigator, 'platform', {{ get: () => '{platform_token}' }});
Object.defineProperty(navigator, 'hardwareConcurrency', {{ get: () => {hardware_concurrency} }});
Object.defineProperty(navigator, 'deviceMemory', {{ get: () => {device_memory} }});

// Permissions shim to avoid "denied" for notifications
try {{
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications'
            ? Promise.resolve({{ state: Notification.permission }})
            : originalQuery(parameters)
    );
}} catch (e) {{ }}

// User-Agent Data / Client Hints
const brands = {brands_json};
const uaData = {{
    brands,
    mobile: false,
    platform: '{platform_name}',
    getHighEntropyValues: async () => ({{ 
        platform: '{platform_name}',
        platformVersion: '{platform_version}',
        architecture: '{architecture}',
        model: '',
        uaFullVersion: '{ua_full_version}',
        fullVersionList: brands,
    }}),
    toJSON: () => ({{ brands, mobile: false, platform: '{platform_name}' }})
}};
Object.defineProperty(navigator, 'userAgentData', {{ get: () => uaData }});

// Chrome runtime presence
if (!window.chrome) {{ window.chrome = {{}}; }}
window.chrome.runtime = {{ id: undefined }};

// Outer window sizing to look non-headless
const {{ innerWidth, innerHeight }} = window;
Object.defineProperty(window, 'outerWidth', {{ get: () => innerWidth + 12 }});
Object.defineProperty(window, 'outerHeight', {{ get: () => innerHeight + 96 }});

// WebGL vendor/renderer spoof
const overrideGlParam = (proto) => {{
    if (!proto || !proto.getParameter) return;
    const originalGetParameter = proto.getParameter;
    proto.getParameter = function(parameter) {{
        if (parameter === 37445) return 'Intel Inc.'; // UNMASKED_VENDOR_WEBGL
        if (parameter === 37446) return 'Intel(R) Iris(TM) Graphics 6100'; // UNMASKED_RENDERER_WEBGL
        return originalGetParameter.call(this, parameter);
    }};
}};
overrideGlParam(WebGLRenderingContext && WebGLRenderingContext.prototype);
overrideGlParam(typeof WebGL2RenderingContext !== 'undefined' && WebGL2RenderingContext.prototype);

// Audio fingerprint: soften the entropy surface
try {{
    const originalGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function() {{
        const data = originalGetChannelData.call(this);
        const jitter = 0.0000001;
        for (let i = 0; i < data.length; i += 1000) {{ data[i] = data[i] + jitter; }}
        return data;
    }};
}} catch (e) {{ }}

// Timing jitter for Date/performance to avoid perfectly deterministic timings
try {{
    const originalNow = Date.now;
    Date.now = () => originalNow() + Math.floor(Math.random() * 7);
    const originalPerformanceNow = performance.now;
    performance.now = () => originalPerformanceNow.call(performance) + Math.random();
}} catch (e) {{ }}

// Notification permission stable
try {{
    if (Notification && Notification.permission === 'default') {{
        Object.defineProperty(Notification, 'permission', {{ get: () => 'granted' }});
    }}
}} catch (e) {{ }}

{_build_plugin_script()}
"""


def _build_fingerprint_payload(user_agent: str = None, chrome_version: str = None, brands: List[Dict[str, str]] = None) -> Dict[str, str]:
    """Bundle all fingerprint values for JS + headers in one place."""
    sys_fp = _get_system_fingerprint()
    ua = user_agent or build_user_agent(chrome_version, sys_fp["ua_platform"])
    # Try to derive version from UA if chrome_version is absent
    if not chrome_version and "Chrome/" in ua:
        chrome_version = ua.split("Chrome/")[-1].split(" ")[0]
    detected_brands, full_version = _build_brands(chrome_version or "120.0.0.0")
    use_brands = brands or detected_brands

    return {
        "user_agent": ua,
        "brands": use_brands,
        "ua_full_version": full_version,
        "platform_name": sys_fp["platform_name"],
        "platform_version": sys_fp["platform_version"],
        "ua_platform": sys_fp["ua_platform"],
        "architecture": sys_fp["architecture"],
        "hardware_concurrency": sys_fp["hardware_concurrency"],
        "device_memory": sys_fp["device_memory"],
    }


async def apply_stealth(
    context,
    user_agent: str = None,
    chrome_version: str = None,
    brands: List[Dict[str, str]] = None,
    languages: List[str] = None,
):
    """
    Apply stealth evasions and realistic headers to the browser context.
    Pass the UA/brands you used in launch_persistent_context to keep network + JS aligned.
    """
    fp = _build_fingerprint_payload(user_agent=user_agent, chrome_version=chrome_version, brands=brands)
    languages = languages or DEFAULT_LANGUAGES
    stealth_js = _build_stealth_js(
        fingerprint=fp,
        languages=languages,
    )
    await context.add_init_script(stealth_js)
    for page in context.pages:
        try:
            await page.add_init_script(stealth_js)
            await page.reload()
        except Exception:
            pass
    headers = build_stealth_headers(user_agent=fp["user_agent"], brands=fp["brands"], platform_name=fp["platform_name"])
    await context.set_extra_http_headers(headers)


def get_stealth_args():
    """
    Returns Chrome arguments that help hide automation with minimal noisy flags.
    """
    return [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
    ]


def get_stealth_user_agent(chrome_version: str = None):
    """
    Returns a realistic Chrome user agent aligned to the detected Chromium version.
    """
    return build_user_agent(chrome_version=chrome_version)

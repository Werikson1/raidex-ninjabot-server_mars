"""
Stealth Module - Bot Detection Evasion
Injects JavaScript to hide automation signals from detection systems
"""

# JavaScript code to inject into browser context
STEALTH_JS = """
// Overwrite webdriver and known Playwright globals
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
delete window.__nightmare;
delete window.__selenium_unwrapped;
delete window._Selenium_IDE_Recorder;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

// Stable languages, platform, hardware details
const languageList = ['en-US', 'en', 'pt-BR', 'pt'];
Object.defineProperty(navigator, 'languages', { get: () => languageList });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

// Fake plugins + mimeTypes (length > 0 looks human)
const fakePlugin = {
    description: 'Chrome PDF Plugin',
    filename: 'internal-pdf-viewer',
    name: 'Chrome PDF Plugin',
    length: 1,
    0: { type: 'application/x-google-chrome-pdf', suffixes: 'pdf', description: 'Portable Document Format' }
};
const fakeMime = {
    type: 'application/pdf',
    suffixes: 'pdf',
    description: 'Portable Document Format'
};
Object.defineProperty(navigator, 'plugins', { get: () => [fakePlugin] });
Object.defineProperty(navigator, 'mimeTypes', { get: () => [fakeMime] });

// Permissions shim to avoid "denied" for notifications
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
);

// User-Agent Data / Client Hints
const brands = [
    { brand: 'Chromium', version: '120' },
    { brand: 'Not.A/Brand', version: '24' },
    { brand: 'Google Chrome', version: '120' },
];
const uaData = {
    brands,
    mobile: false,
    platform: 'Windows',
    getHighEntropyValues: async () => ({
        platform: 'Windows',
        platformVersion: '15.0.0',
        architecture: 'x86',
        model: '',
        uaFullVersion: '120.0.6099.71',
        fullVersionList: brands,
    }),
    toJSON: () => ({ brands, mobile: false, platform: 'Windows' })
};
Object.defineProperty(navigator, 'userAgentData', { get: () => uaData });

// Chrome runtime presence
if (!window.chrome) { window.chrome = {}; }
window.chrome.runtime = { id: undefined };

// Outer window sizing to look non-headless
const { innerWidth, innerHeight } = window;
Object.defineProperty(window, 'outerWidth', { get: () => innerWidth + 12 });
Object.defineProperty(window, 'outerHeight', { get: () => innerHeight + 96 });

// WebGL vendor/renderer spoof
const overrideGlParam = (proto) => {
    if (!proto || !proto.getParameter) return;
    const originalGetParameter = proto.getParameter;
    proto.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.'; // UNMASKED_VENDOR_WEBGL
        if (parameter === 37446) return 'Intel(R) Iris(TM) Graphics 6100'; // UNMASKED_RENDERER_WEBGL
        return originalGetParameter.call(this, parameter);
    };
};
overrideGlParam(WebGLRenderingContext && WebGLRenderingContext.prototype);
overrideGlParam(typeof WebGL2RenderingContext !== 'undefined' && WebGL2RenderingContext.prototype);

// Audio fingerprint: soften the entropy surface
const originalGetChannelData = AudioBuffer.prototype.getChannelData;
AudioBuffer.prototype.getChannelData = function() {
    const data = originalGetChannelData.call(this);
    const jitter = 0.0000001;
    for (let i = 0; i < data.length; i += 1000) { data[i] = data[i] + jitter; }
    return data;
};

// Timing jitter for Date/performance to avoid perfectly deterministic timings
const originalNow = Date.now;
Date.now = () => originalNow() + Math.floor(Math.random() * 7);
const originalPerformanceNow = performance.now;
performance.now = () => originalPerformanceNow.call(performance) + Math.random();

// Notification permission stable
if (Notification && Notification.permission === 'default') {
    Object.defineProperty(Notification, 'permission', { get: () => 'granted' });
}
"""

async def apply_stealth(context, user_agent=None):
    """
    Apply stealth evasions and realistic headers to the browser context.
    """
    await context.add_init_script(STEALTH_JS)
    headers = build_stealth_headers(user_agent=user_agent)
    await context.set_extra_http_headers(headers)

def get_stealth_args():
    """
    Returns Chrome arguments that help hide automation.
    """
    return [
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--disable-web-security',
        '--disable-features=IsolateOrigins,site-per-process',
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-infobars',
        '--window-position=0,0',
        '--ignore-certificate-errors',
        '--ignore-certificate-errors-spki-list',
        '--disable-gpu'
    ]

def get_stealth_user_agent():
    """
    Returns a realistic Chrome user agent.
    """
    return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.71 Safari/537.36'

def build_stealth_headers(user_agent=None):
    """
    Build a realistic set of HTTP headers to reduce automation fingerprints.
    """
    ua = user_agent or get_stealth_user_agent()
    return {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8",
        "Cache-Control": "max-age=0",
        "DNT": "1",
        "Upgrade-Insecure-Requests": "1",
        "Sec-CH-UA": '"Chromium";v="120", "Not.A/Brand";v="24", "Google Chrome";v="120"',
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-CH-UA-Mobile": "?0",
    }

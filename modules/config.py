"""
Configuration file for Ogamex Bot
All bot settings are centralized here for easy modification
"""

import os
import json
from typing import Tuple
from urllib.parse import urlparse

# Path to the JSON configuration file
CONFIG_FILE = os.path.abspath("config.json")

def load_config():
    """Loads configuration from the JSON file."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠ Config file not found at {CONFIG_FILE}. Using defaults/failing.")
        return {}
    except json.JSONDecodeError:
        print(f"⚠ Error decoding {CONFIG_FILE}.")
        return {}

# Load initial config
_config = load_config()

def _normalize_time_dict(raw: dict, default: dict) -> dict:
    """Normalize hour/minute dictionaries with safe defaults."""
    raw = raw or {}
    try:
        hour = int(raw.get("hour", default.get("hour", 0)))
    except Exception:
        hour = default.get("hour", 0)
    try:
        minute = int(raw.get("minute", default.get("minute", 0)))
    except Exception:
        minute = default.get("minute", 0)
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return {"hour": hour, "minute": minute}

def _get_base_url(raw_url: str = None) -> str:
    """Return scheme + host for a given URL or default to mars host."""
    try:
        parsed = urlparse(raw_url) if raw_url else None
        if parsed and parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return "https://mars.ogamex.net"

# URLs and Paths
USE_LOCAL_FILE = _config.get("USE_LOCAL_FILE", False)
LOCAL_FILE_PATH = os.path.abspath(_config.get("LOCAL_FILE_PATH", os.path.join("debug", "galaxy_view.html")))
MAIN_PLANET_ID = _config.get("MAIN_PLANET_ID", "ae2da001-49d9-4c0e-b1f7-71b564ca0259")
ASTEROID_PLANET_ID = _config.get("ASTEROID_PLANET_ID", MAIN_PLANET_ID)
LIVE_URL = _config.get("LIVE_URL", f"https://mars.ogamex.net/galaxy?planet={MAIN_PLANET_ID}")
BASE_URL = _get_base_url(LIVE_URL)
USER_DATA_DIR = os.path.abspath(_config.get("USER_DATA_DIR", "user_data"))
HEADLESS_MODE = _config.get("HEADLESS_MODE", False)
TELEGRAM_BOT_TOKEN = _config.get("TELEGRAM_BOT_TOKEN", os.environ.get("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_CHAT_ID = str(_config.get("TELEGRAM_CHAT_ID", os.environ.get("TELEGRAM_CHAT_ID", "")) or "")
TELEGRAM_USERNAME = _config.get("TELEGRAM_USERNAME", os.environ.get("TELEGRAM_USERNAME", "@ogame_xbot"))
TELEGRAM_ENABLED = bool(_config.get("TELEGRAM_ENABLED", bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)))
# Asteroid miner runtime toggle (persisted)
ASTEROID_ENABLED = bool(_config.get("ASTEROID_ENABLED", True))
# Asteroid miner ship amount (when not using fleet groups)
ASTEROID_MINER_AMOUNT = int(_config.get("ASTEROID_MINER_AMOUNT", 0) or 0)
# Web server binding (override via env or config)
WEB_HOST = _config.get("WEB_HOST", os.environ.get("WEB_HOST", "0.0.0.0"))
try:
    WEB_PORT = int(_config.get("WEB_PORT", os.environ.get("WEB_PORT", 5001)))
except Exception:
    WEB_PORT = 5001

# Fleet Group Configuration - dynamically fetched from game
# Used only for expedition/farmer modes
FLEET_GROUPS = {}

FLEET_GROUP_NAME = _config.get("FLEET_GROUP_NAME", "")
FLEET_GROUP_VALUE = _config.get("FLEET_GROUP_VALUE", "")

# Cooldown Configuration
COOLDOWN_FILE = os.path.abspath(os.path.join("data", "asteroid_cooldowns.json"))
COOLDOWN_HOURS = _config.get("COOLDOWN_HOURS", 1)

# Search Configuration
SEARCH_DELAY_MIN = _config.get("SEARCH_DELAY_MIN", 0.7)
SEARCH_DELAY_MAX = _config.get("SEARCH_DELAY_MAX", 1.0)

NO_ASTEROID_WAIT_MIN = _config.get("NO_ASTEROID_WAIT_MIN", 25)
NO_ASTEROID_WAIT_MAX = _config.get("NO_ASTEROID_WAIT_MAX", 40)

FLEET_FAIL_WAIT_MINUTES = _config.get("FLEET_FAIL_WAIT_MINUTES", 25)

# Travel Time Configuration
BASE_SYSTEM = _config.get("BASE_SYSTEM", 230)

# Distance ranges and minimum required asteroid time (in minutes)
TRAVEL_TIME_RANGES = _config.get("TRAVEL_TIME_RANGES", [
    # Based on measured one-way travel times from BASE_SYSTEM=230.
    # Times are rounded up to the next full minute (e.g., 19:53 -> 20).
    (0, 20, 20),      # 0-20 systems   = 19:53 -> 20 min
    (21, 40, 23),     # 21-40 systems  = 22:59 -> 23 min
    (41, 60, 26),     # 41-60 systems  = 25:44 -> 26 min
    (61, 80, 29),     # 61-80 systems  = 28:12 -> 29 min
    (81, 100, 31),    # 81-100 systems = 30:28 -> 31 min
    (101, 120, 33),   # 101-120        = 32:35 -> 33 min
    (121, 140, 35),   # 121-140        = 34:34 -> 35 min
    (141, 160, 37),   # 141-160        = 36:27 -> 37 min
    (161, 180, 39),   # 161-180        = 38:14 -> 39 min
    (181, 200, 40),   # 181-200        = 39:56 -> 40 min
    (201, 220, 42),   # 201-220        = 41:34 -> 42 min
    (221, 240, 44),   # 221-240        = 43:08 -> 44 min
    (241, 499, 46),   # 241+ (269 max @ SS230->499) = 45:19 -> 46 min
])

# Timeouts
NETWORK_IDLE_TIMEOUT = _config.get("NETWORK_IDLE_TIMEOUT", 5000)
FLEET_PAGE_TIMEOUT = _config.get("FLEET_PAGE_TIMEOUT", 10000)
MODAL_TIMEOUT = _config.get("MODAL_TIMEOUT", 5000)

def get_asteroid_galaxy_url(config_override: dict = None) -> str:
    """Build galaxy URL for asteroid navigation using selected planet."""
    cfg_source = config_override if config_override is not None else load_config()
    planet_id = cfg_source.get("ASTEROID_PLANET_ID") or cfg_source.get("MAIN_PLANET_ID", MAIN_PLANET_ID)
    live_url = cfg_source.get("LIVE_URL", LIVE_URL)
    base_url = _get_base_url(live_url)
    return f"{base_url}/galaxy?planet={planet_id}"

# Expose resolved asteroid galaxy URL using current config snapshot
ASTEROID_GALAXY_URL = get_asteroid_galaxy_url(_config)

def get_expedition_config(config_override: dict = None) -> dict:
    """Return sanitized expedition configuration."""
    cfg_source = config_override if config_override is not None else load_config()
    exp_cfg = cfg_source.get("expedition_mode", {}) or {}

    # Planet + fleet group defaults fall back to main miner config
    planet_id = exp_cfg.get("planet_id") or cfg_source.get("MAIN_PLANET_ID", MAIN_PLANET_ID)
    fleet_group_name = exp_cfg.get("fleet_group_name", cfg_source.get("FLEET_GROUP_NAME", FLEET_GROUP_NAME))
    fleet_group_value = exp_cfg.get(
        "fleet_group_value",
        cfg_source.get("FLEET_GROUP_VALUE", FLEET_GROUPS.get(fleet_group_name, FLEET_GROUP_VALUE))
    )

    sleep_start_default = {"hour": 23, "minute": 0}
    wake_up_default = {"hour": 7, "minute": 30}
    dispatch_default = {"hour": 1, "minute": 15}

    return {
        "enabled": bool(exp_cfg.get("enabled", False)),
        "planet_id": planet_id,
        "fleet_group_name": fleet_group_name,
        "fleet_group_value": fleet_group_value,
        "headless": bool(exp_cfg.get("headless", cfg_source.get("HEADLESS_MODE", HEADLESS_MODE))),
        "sleep_start": _normalize_time_dict(exp_cfg.get("sleep_start", {}), sleep_start_default),
        "wake_up": _normalize_time_dict(exp_cfg.get("wake_up", {}), wake_up_default),
        "dispatch_cooldown": _normalize_time_dict(exp_cfg.get("dispatch_cooldown", {}), dispatch_default),
        "sleep_mode": bool(exp_cfg.get("sleep_mode", False)),
        "random_sleep_mode": bool(exp_cfg.get("random_sleep_mode", False)),
    }

# Expose default expedition config snapshot
EXPEDITION_MODE = get_expedition_config(_config)


def _sanitize_min_max(raw_min, raw_max, default_min: int, default_max: int, hard_min: int = 0, hard_max: int = 360) -> Tuple[int, int]:
    """Clamp and normalize a min/max integer pair with safe defaults."""
    try:
        min_val = int(raw_min if raw_min is not None else default_min)
    except Exception:
        min_val = default_min
    try:
        max_val = int(raw_max if raw_max is not None else default_max)
    except Exception:
        max_val = default_max

    min_val = max(hard_min, min(hard_max, min_val))
    max_val = max(hard_min, min(hard_max, max_val))

    if max_val < min_val:
        max_val = min_val

    return min_val, max_val


def get_farmer_config(config_override: dict = None) -> dict:
    """Return sanitized farmer configuration."""
    cfg_source = config_override if config_override is not None else load_config()
    farmer_cfg = cfg_source.get("farmer_mode", {}) or {}

    planet_id = farmer_cfg.get("planet_id") or cfg_source.get("MAIN_PLANET_ID", MAIN_PLANET_ID)

    sleep_start_default = {"hour": 22, "minute": 0}
    wake_up_default = {"hour": 5, "minute": 0}
    cooldown_min_default = 45  # minutes
    cooldown_max_default = 75  # minutes

    cd_min, cd_max = _sanitize_min_max(
        farmer_cfg.get("attack_cooldown_min"),
        farmer_cfg.get("attack_cooldown_max"),
        cooldown_min_default,
        cooldown_max_default,
        hard_min=0,
        hard_max=360,
    )

    return {
        "enabled": bool(farmer_cfg.get("enabled", False)),
        "planet_id": planet_id,
        "headless": bool(farmer_cfg.get("headless", cfg_source.get("HEADLESS_MODE", HEADLESS_MODE))),
        "sleep_start": _normalize_time_dict(farmer_cfg.get("sleep_start", {}), sleep_start_default),
        "wake_up": _normalize_time_dict(farmer_cfg.get("wake_up", {}), wake_up_default),
        "sleep_mode": bool(farmer_cfg.get("sleep_mode", False)),
        "random_sleep_mode": bool(farmer_cfg.get("random_sleep_mode", False)),
        "attack_cooldown_min": cd_min,
        "attack_cooldown_max": cd_max,
        "active_mode": bool(farmer_cfg.get("active_mode", False)),
    }


# Expose default farmer config snapshot
FARMER_MODE = get_farmer_config(_config)

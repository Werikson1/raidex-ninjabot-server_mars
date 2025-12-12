from flask import Flask, render_template, jsonify, request
import asyncio
import json
import os
import urllib.request
from bs4 import BeautifulSoup
from bot import bot_instance, log_queue
import modules.config as config_module
from modules.expedition_runner import load_expedition_state
from modules.farmer_runner import load_farmer_state
from modules.telegram_bot import telegram_controller


def _deep_merge(base: dict, updates: dict) -> dict:
    """Merge dicts recursively without dropping missing keys."""
    for key, value in updates.items():
        if isinstance(value, dict):
            base[key] = _deep_merge(base.get(key, {}) if isinstance(base.get(key), dict) else {}, value)
        else:
            base[key] = value
    return base


def _get_base_url():
    """Derive base URL from LIVE_URL to support other servers."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(config_module.LIVE_URL)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        pass
    return "https://mars.ogamex.net"


def _fetch_fleet_groups():
    """
    Fetch fleet group options from the live fleet page (or local fallback).
    Returns a list of {"name": str, "value": str}.
    """
    def _parse_groups(html_text: str):
        if not html_text:
            return []
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            select = soup.find("select", id="fleetGroupSelect")
            if not select:
                return []

            groups = []
            for opt in select.find_all("option"):
                value = (opt.get("value") or "").strip()
                name = (opt.get_text() or "").strip()
                if not value or not name or value.lower() == "select":
                    continue
                groups.append({"name": name, "value": value})
            return groups
        except Exception:
            return []

    html = None
    url = f"{_get_base_url()}/fleet"

    # Prefer the logged-in Playwright context to avoid stale/unauthenticated HTML
    if bot_instance.browser_context and bot_instance.loop:
        try:
            async def _scrape_with_context():
                page = await bot_instance.browser_context.new_page()
                try:
                    await page.goto(url, timeout=30000)
                    await page.wait_for_selector("#fleetGroupSelect", timeout=10000)
                    return await page.content()
                finally:
                    await page.close()

            future = asyncio.run_coroutine_threadsafe(_scrape_with_context(), bot_instance.loop)
            html = future.result(timeout=40)
        except Exception:
            html = None

    # Fallback to plain HTTP fetch if browser context not available
    if html is None:
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except Exception:
            html = None

    groups = _parse_groups(html)

    # Fallback to local reference page if live fetch fails or returns empty
    if not groups:
        try:
            local_path = os.path.abspath(os.path.join("pages_view", "fleet_page.html"))
            with open(local_path, "r", encoding="utf-8") as f:
                groups = _parse_groups(f.read())
        except Exception:
            groups = []

    # Last resort: use configured fleet group name/value if present
    if not groups:
        cfg = config_module.load_config()
        name = cfg.get("FLEET_GROUP_NAME", "")
        value = cfg.get("FLEET_GROUP_VALUE", "")
        if name or value:
            groups = [{"name": name or value, "value": value or name}]

    return groups

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('asteroid_miner.html')

@app.route('/expedition')
def expedition_page():
    return render_template('expedition.html')

@app.route('/farmer')
def farmer_page():
    return render_template('farmer.html')

@app.route('/empire')
def empire_page():
    return render_template('empire.html')

@app.route('/api/status')
def status():
    return jsonify({
        "running": bot_instance.running,
        "logs": list(log_queue)
    })

@app.route('/api/cooldowns')
def get_cooldowns():
    return jsonify(bot_instance.get_cooldowns())

@app.route('/api/start', methods=['POST'])
def start_bot():
    if not bot_instance.running:
        bot_instance.start()
        return jsonify({"status": "started"})
    return jsonify({"status": "already running"})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    if bot_instance.running:
        bot_instance.stop()
        return jsonify({"status": "stopping"})
    return jsonify({"status": "not running"})

@app.route('/api/config', methods=['GET'])
def get_config():
    # Read directly from file to get latest on disk
    try:
        with open(config_module.CONFIG_FILE, 'r') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/config', methods=['POST'])
def update_config():
    try:
        new_config = request.json
        # Validate (basic)
        if not isinstance(new_config, dict):
            return jsonify({"error": "Invalid config format"}), 400

        existing = config_module.load_config()
        merged = _deep_merge(existing, new_config)

        # Write to file
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(merged, f, indent=4)

        # Reload config in module (optional, bot reloads on loop start anyway)
        config_module._config = merged

        return jsonify({"status": "saved", "config": merged})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/expedition/config', methods=['GET'])
def get_expedition_config():
    try:
        return jsonify(config_module.get_expedition_config())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/expedition/config', methods=['POST'])
def save_expedition_config():
    try:
        payload = request.json
        if not isinstance(payload, dict):
            return jsonify({"error": "Invalid expedition config format"}), 400

        full_cfg = config_module.load_config()
        full_cfg["expedition_mode"] = _deep_merge(full_cfg.get("expedition_mode", {}), payload)

        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(full_cfg, f, indent=4)

        config_module._config = full_cfg
        return jsonify({"status": "saved", "expedition_mode": config_module.get_expedition_config(full_cfg)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/expedition/planets', methods=['GET'])
def get_expedition_planets():
    try:
        empire_path = os.path.abspath(os.path.join("data", "empire_data.json"))
        with open(empire_path, 'r') as f:
            data = json.load(f)
        planets = []
        for planet in data.get("planets", []):
            pid = planet.get("id")
            name = planet.get("name")
            coords = planet.get("coords")
            if pid:
                planets.append({"id": pid, "name": name, "coords": coords})

            moon_id = planet.get("moon_id")
            if moon_id:
                moon_name = planet.get("moon_name") or f"{name} - Moon"
                planets.append({"id": moon_id, "name": moon_name, "coords": coords})

        return jsonify({"planets": planets})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/fleet/groups', methods=['GET'])
def get_fleet_groups():
    try:
        groups = _fetch_fleet_groups()
        if not groups:
            # Fallback to static config if scraping fails
            groups = [
                {"name": name, "value": value}
                for name, value in config_module.FLEET_GROUPS.items()
            ]
        return jsonify({"groups": groups})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/empire/data', methods=['GET'])
def get_empire_data():
    return jsonify(bot_instance.get_empire_data())

@app.route('/api/empire/crawl', methods=['POST'])
def trigger_crawl():
    success, message = bot_instance.trigger_empire_crawl()
    if success:
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"status": "error", "message": message}), 400

from modules.brain import brain_manager

@app.route('/api/brain/status', methods=['GET'])
def get_brain_status():
    return jsonify({"running": brain_manager.running})

@app.route('/brain')
def brain_page():
    return render_template('brain.html')

@app.route('/api/brain/targets', methods=['GET'])
def get_brain_targets_config():
    try:
        saved = brain_manager.read_saved_targets()
        return jsonify({"targets": saved})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/brain/targets', methods=['POST'])
def save_brain_targets_config():
    payload = request.json
    if not isinstance(payload, dict):
        return jsonify({"error": "Invalid targets payload"}), 400

    saved = brain_manager.save_targets_to_disk(payload)
    if saved is None:
        return jsonify({"error": "Failed to save targets"}), 500

    return jsonify({"status": "saved", "targets": saved})

@app.route('/api/brain/planets', methods=['GET'])
def get_brain_planets():
    # We trigger a fetch if no planets are cached or just return what we have?
    # BrainManager doesn't cache planets persistently yet, but we can trigger a fetch.
    # Since fetch requires a browser context, we need to run it in the bot loop or use the existing context.
    # This is tricky because the bot loop is running.
    
    # We can use bot_instance to schedule the fetch.
    # But BrainManager is separate.
    # Let's add a method to bot_instance to run brain tasks or expose context.
    
    # Ideally, BrainManager should be integrated into Bot or Bot should delegate.
    # For now, let's try to use bot_instance to run the fetch.
    
    # We can add a queue or similar.
    # Or we can just return the empire data planets if they have IDs?
    # But we know they don't.
    
    # Let's trigger a fetch via bot_instance.
    success, result = bot_instance.run_brain_action("fetch_planets")
    if success:
        return jsonify({"planets": result})
    else:
        return jsonify({"error": result}), 500

@app.route('/api/brain/start', methods=['POST'])
def start_brain():
    data = request.json
    planet_id = data.get('planet_id')
    targets = data.get('targets')
    
    if not planet_id or not targets:
        return jsonify({"error": "Missing planet_id or targets"}), 400
        
    brain_manager.set_targets(planet_id, targets)
    
    # Only start the task if it's not already running
    if not brain_manager.running:
        success, msg = bot_instance.start_brain_task(brain_manager)
        if success:
            return jsonify({"status": "started"})
        else:
            return jsonify({"error": msg}), 500
    else:
        return jsonify({"status": "started", "message": "Targets updated, brain already running"})

@app.route('/api/brain/stop', methods=['POST'])
def stop_brain():
    bot_instance.stop_brain_task()
    return jsonify({"status": "stopped"})

@app.route('/api/asteroid/start', methods=['POST'])
def start_asteroid_miner():
    bot_instance.enable_asteroid_miner()
    try:
        cfg = config_module.load_config()
        cfg["ASTEROID_ENABLED"] = True
        galaxy_url = config_module.get_asteroid_galaxy_url(cfg)
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
        if bot_instance.asteroid_runner:
            bot_instance.asteroid_runner.reset(galaxy_url)
    except Exception as e:
        return jsonify({"status": "asteroid_miner_started", "warning": str(e)})
    return jsonify({"status": "asteroid_miner_started"})

@app.route('/api/asteroid/stop', methods=['POST'])
def stop_asteroid_miner():
    bot_instance.disable_asteroid_miner()
    try:
        cfg = config_module.load_config()
        cfg["ASTEROID_ENABLED"] = False
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
    except Exception as e:
        return jsonify({"status": "asteroid_miner_stopped", "warning": str(e)})
    return jsonify({"status": "asteroid_miner_stopped"})

@app.route('/api/asteroid/config', methods=['POST'])
def save_asteroid_config():
    try:
        payload = request.json or {}
        if not isinstance(payload, dict):
            return jsonify({"error": "Invalid asteroid config format"}), 400

        cfg = config_module.load_config()
        asteroid_mode = cfg.get("asteroid_mode", {})
        
        # Handle planet_id (root level)
        if "planet_id" in payload:
            cfg["ASTEROID_PLANET_ID"] = payload.get("planet_id") or cfg.get("ASTEROID_PLANET_ID")

        # Handle fleet group selection
        if "fleet_group_name" in payload:
            asteroid_mode["fleet_group_name"] = payload.get("fleet_group_name", "")
        if "fleet_group_value" in payload:
            asteroid_mode["fleet_group_value"] = payload.get("fleet_group_value", "")

        # Handle sleep settings (asteroid_mode sub-object)
        sleep_fields = ["sleep_mode", "random_sleep_mode", "sleep_start", "wake_up"]
        if any(field in payload for field in sleep_fields):
            if "sleep_mode" in payload:
                asteroid_mode["sleep_mode"] = bool(payload.get("sleep_mode"))
            if "random_sleep_mode" in payload:
                asteroid_mode["random_sleep_mode"] = bool(payload.get("random_sleep_mode"))
            if "sleep_start" in payload:
                asteroid_mode["sleep_start"] = payload.get("sleep_start")
            if "wake_up" in payload:
                asteroid_mode["wake_up"] = payload.get("wake_up")

        cfg["asteroid_mode"] = asteroid_mode

        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)

        config_module._config = cfg
        galaxy_url = config_module.get_asteroid_galaxy_url(cfg)
        if bot_instance.asteroid_runner:
            bot_instance.asteroid_runner.reset(galaxy_url)

        return jsonify({
            "status": "saved",
            "planet_id": cfg.get("ASTEROID_PLANET_ID"),
            "galaxy_url": galaxy_url,
            "asteroid_mode": cfg.get("asteroid_mode", {})
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/asteroid/status', methods=['GET'])
def get_asteroid_miner_status():
    cfg = config_module.load_config()
    cfg_enabled = bool(cfg.get("ASTEROID_ENABLED", True))
    runtime_enabled = bot_instance.is_asteroid_miner_enabled()
    if cfg_enabled and not runtime_enabled:
        bot_instance.enable_asteroid_miner()
    return jsonify({
        "enabled": runtime_enabled or cfg_enabled,
        "enabled_config": cfg_enabled,
        "enabled_runtime": runtime_enabled,
        "running": bot_instance.running
    })

@app.route('/api/expedition/start', methods=['POST'])
def start_expedition_mode():
    bot_instance.enable_expedition_mode()
    try:
        cfg = config_module.load_config()
        cfg["expedition_mode"] = _deep_merge(cfg.get("expedition_mode", {}), {"enabled": True})
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
    except Exception as e:
        # Do not fail toggling due to disk issues, just report
        return jsonify({"status": "expedition_enabled", "warning": str(e)})
    return jsonify({"status": "expedition_enabled"})

@app.route('/api/expedition/stop', methods=['POST'])
def stop_expedition_mode():
    bot_instance.disable_expedition_mode()
    try:
        cfg = config_module.load_config()
        cfg["expedition_mode"] = _deep_merge(cfg.get("expedition_mode", {}), {"enabled": False})
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
    except Exception as e:
        return jsonify({"status": "expedition_disabled", "warning": str(e)})
    return jsonify({"status": "expedition_disabled"})

@app.route('/api/expedition/status', methods=['GET'])
def get_expedition_status():
    exp_cfg = config_module.get_expedition_config()
    enabled_cfg = exp_cfg.get("enabled", False)
    enabled_runtime = bot_instance.is_expedition_enabled()
    # Sync runtime flag to config intent to keep toggle aligned after restarts
    if enabled_cfg and not enabled_runtime:
        bot_instance.expedition_enabled = True
    state = load_expedition_state()
    return jsonify({
        "enabled": enabled_cfg or enabled_runtime,
        "enabled_config": enabled_cfg,
        "enabled_runtime": enabled_runtime,
        "running": bot_instance.running,
        "config": exp_cfg,
        "state": state
    })

@app.route('/api/farmer/config', methods=['GET'])
def get_farmer_config():
    try:
        return jsonify(config_module.get_farmer_config())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/farmer/config', methods=['POST'])
def save_farmer_config():
    try:
        payload = request.json
        if not isinstance(payload, dict):
            return jsonify({"error": "Invalid farmer config format"}), 400

        full_cfg = config_module.load_config()
        full_cfg["farmer_mode"] = _deep_merge(full_cfg.get("farmer_mode", {}), payload)

        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(full_cfg, f, indent=4)

        config_module._config = full_cfg
        return jsonify({"status": "saved", "farmer_mode": config_module.get_farmer_config(full_cfg)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/farmer/start', methods=['POST'])
def start_farmer_mode():
    bot_instance.enable_farmer_mode()
    try:
        cfg = config_module.load_config()
        cfg["farmer_mode"] = _deep_merge(cfg.get("farmer_mode", {}), {"enabled": True})
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
    except Exception as e:
        return jsonify({"status": "farmer_enabled", "warning": str(e)})
    return jsonify({"status": "farmer_enabled"})

@app.route('/api/farmer/stop', methods=['POST'])
def stop_farmer_mode():
    bot_instance.disable_farmer_mode()
    try:
        cfg = config_module.load_config()
        cfg["farmer_mode"] = _deep_merge(cfg.get("farmer_mode", {}), {"enabled": False})
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
    except Exception as e:
        return jsonify({"status": "farmer_disabled", "warning": str(e)})
    return jsonify({"status": "farmer_disabled"})

@app.route('/api/farmer/status', methods=['GET'])
def get_farmer_status():
    farmer_cfg = config_module.get_farmer_config()
    enabled_cfg = farmer_cfg.get("enabled", False)
    enabled_runtime = bot_instance.is_farmer_enabled()
    if enabled_cfg and not enabled_runtime:
        bot_instance.farmer_enabled = True
    state = load_farmer_state()
    return jsonify({
        "enabled": enabled_cfg or enabled_runtime,
        "enabled_config": enabled_cfg,
        "enabled_runtime": enabled_runtime,
        "running": bot_instance.running,
        "config": farmer_cfg,
        "state": state
    })

@app.route('/api/farmer/planets', methods=['GET'])
def get_farmer_planets():
    # Reuse expedition planet listing
    return get_expedition_planets()


# ============================================================================
# Telegram Bot Controller Integration
# ============================================================================

def _get_bot_status():
    """Get current bot status for Telegram commands."""
    cooldowns = bot_instance.get_cooldowns()
    return {
        "bot_running": bot_instance.running,
        "asteroid_enabled": bot_instance.is_asteroid_miner_enabled(),
        "expedition_enabled": bot_instance.is_expedition_enabled(),
        "farmer_enabled": bot_instance.is_farmer_enabled(),
        "active_cooldowns": len(cooldowns) if cooldowns else 0,
    }


def _start_asteroid_via_telegram():
    """Start asteroid miner via Telegram command."""
    try:
        bot_instance.enable_asteroid_miner()
        cfg = config_module.load_config()
        cfg["ASTEROID_ENABLED"] = True
        galaxy_url = config_module.get_asteroid_galaxy_url(cfg)
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
        if bot_instance.asteroid_runner:
            bot_instance.asteroid_runner.reset(galaxy_url)
        return True
    except Exception as e:
        print(f"Error starting asteroid via telegram: {e}")
        return False


def _stop_asteroid_via_telegram():
    """Stop asteroid miner via Telegram command."""
    try:
        bot_instance.disable_asteroid_miner()
        cfg = config_module.load_config()
        cfg["ASTEROID_ENABLED"] = False
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
        return True
    except Exception as e:
        print(f"Error stopping asteroid via telegram: {e}")
        return False


def _start_expedition_via_telegram():
    """Start expedition mode via Telegram command."""
    try:
        bot_instance.enable_expedition_mode()
        cfg = config_module.load_config()
        cfg["expedition_mode"] = _deep_merge(cfg.get("expedition_mode", {}), {"enabled": True})
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
        return True
    except Exception as e:
        print(f"Error starting expedition via telegram: {e}")
        return False


def _stop_expedition_via_telegram():
    """Stop expedition mode via Telegram command."""
    try:
        bot_instance.disable_expedition_mode()
        cfg = config_module.load_config()
        cfg["expedition_mode"] = _deep_merge(cfg.get("expedition_mode", {}), {"enabled": False})
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
        return True
    except Exception as e:
        print(f"Error stopping expedition via telegram: {e}")
        return False


def _start_farmer_via_telegram():
    """Start farmer mode via Telegram command."""
    try:
        bot_instance.enable_farmer_mode()
        cfg = config_module.load_config()
        cfg["farmer_mode"] = _deep_merge(cfg.get("farmer_mode", {}), {"enabled": True})
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
        return True
    except Exception as e:
        print(f"Error starting farmer via telegram: {e}")
        return False


def _stop_farmer_via_telegram():
    """Stop farmer mode via Telegram command."""
    try:
        bot_instance.disable_farmer_mode()
        cfg = config_module.load_config()
        cfg["farmer_mode"] = _deep_merge(cfg.get("farmer_mode", {}), {"enabled": False})
        with open(config_module.CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)
        config_module._config = cfg
        return True
    except Exception as e:
        print(f"Error stopping farmer via telegram: {e}")
        return False


def _initialize_telegram_bot():
    """Initialize and start the Telegram bot controller."""
    telegram_controller.set_callbacks(
        get_status=_get_bot_status,
        start_asteroid=_start_asteroid_via_telegram,
        stop_asteroid=_stop_asteroid_via_telegram,
        start_expedition=_start_expedition_via_telegram,
        stop_expedition=_stop_expedition_via_telegram,
        start_farmer=_start_farmer_via_telegram,
        stop_farmer=_stop_farmer_via_telegram,
    )
    telegram_controller.start()


if __name__ == '__main__':
    # Start Telegram bot controller
    _initialize_telegram_bot()
    
    app.run(
        debug=True,
        use_reloader=False,
        host=config_module.WEB_HOST,
        port=config_module.WEB_PORT,
    )

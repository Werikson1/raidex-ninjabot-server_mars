import modules.config as cfg


def test_farmer_config_clamps_and_orders_cooldown():
    raw = {
        "farmer_mode": {
            "attack_cooldown_min": 5,
            "attack_cooldown_max": 2,
            "sleep_start": {"hour": 30, "minute": 90},
            "wake_up": {"hour": -1, "minute": -5},
        }
    }

    sanitized = cfg.get_farmer_config(raw)
    assert sanitized["attack_cooldown_min"] == 5
    assert sanitized["attack_cooldown_max"] == 5
    assert sanitized["sleep_start"] == {"hour": 23, "minute": 59}
    assert sanitized["wake_up"] == {"hour": 0, "minute": 0}


def test_farmer_config_defaults_when_missing():
    sanitized = cfg.get_farmer_config({})
    assert "planet_id" in sanitized
    assert sanitized["attack_cooldown_min"] <= sanitized["attack_cooldown_max"]
    assert isinstance(sanitized.get("sleep_mode"), bool)

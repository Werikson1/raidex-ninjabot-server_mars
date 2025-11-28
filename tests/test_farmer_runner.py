from modules.farmer_runner import FarmerRunner


def test_choose_cooldown_range_respected():
    runner = FarmerRunner({"attack_cooldown_min": 10, "attack_cooldown_max": 15})
    for _ in range(20):
        val = runner._choose_cooldown_minutes()
        assert 10 <= val <= 15


def test_choose_cooldown_minimum_one_minute():
    runner = FarmerRunner({"attack_cooldown_min": 0, "attack_cooldown_max": 0})
    assert runner._choose_cooldown_minutes() == 1

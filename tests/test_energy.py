from app.core.energy import EnergyMeter


def test_calculate_energy_uses_model_specific_intensity():
    energy = EnergyMeter.calculate_energy("gpt-4", prompt_tokens=100, completion_tokens=50)
    assert energy == round(150 * 0.03, 6)


def test_register_model_updates_intensity(monkeypatch):
    EnergyMeter.register_model("eco-model", 0.001)
    energy = EnergyMeter.calculate_energy("eco-model", 10, 10)
    assert energy == round(20 * 0.001, 6)

import pytest
from app.core.config_manager import ConfigManager


def test_loads_llm_model():
    cfg = ConfigManager("config.yaml")
    assert cfg.get("llm_model") == "qwen3:8b"


def test_loads_stt_model():
    cfg = ConfigManager("config.yaml")
    assert cfg.get("stt_model") == "small"


def test_loads_wakeword_settings():
    cfg = ConfigManager("config.yaml")
    assert cfg.get("wakeword_models_dir") == "config/wakeword_models"
    assert isinstance(cfg.get("wakeword_threshold"), float)


def test_default_value_for_missing_key():
    cfg = ConfigManager("config.yaml")
    assert cfg.get("nonexistent_key", "default") == "default"


def test_none_default_for_missing_key():
    cfg = ConfigManager("config.yaml")
    assert cfg.get("nonexistent_key") is None


def test_all_returns_dict():
    cfg = ConfigManager("config.yaml")
    data = cfg.all()
    assert isinstance(data, dict)
    assert "llm_model" in data


def test_reload():
    cfg = ConfigManager("config.yaml")
    cfg.reload()
    assert cfg.get("llm_model") == "qwen3:8b"

"""Tests for the LLM configuration defaults and project configuration file."""

from src.utils.config_manager import ConfigManager


MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"


def test_project_llm_config_uses_the_pinned_model():
    config = ConfigManager("config/llm_config.yaml", "config/does-not-exist.env")

    assert config.get_llm_config()["model"] == MODEL_ID


def test_missing_llm_config_uses_the_same_pinned_model(tmp_path):
    config = ConfigManager(
        str(tmp_path / "missing-llm-config.yaml"),
        str(tmp_path / "missing-settings.env"),
    )

    assert config.get_llm_config()["model"] == MODEL_ID

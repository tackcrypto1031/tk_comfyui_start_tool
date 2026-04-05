"""Tests for the i18n translation system."""
import pytest
from src.gui.i18n import t, set_language, get_language, TRANSLATIONS


def setup_function():
    """Reset to English before each test."""
    set_language("en")


def test_set_language_valid():
    set_language("zh-TW")
    assert get_language() == "zh-TW"


def test_set_language_invalid_ignored():
    set_language("en")
    set_language("fr")  # unsupported language
    assert get_language() == "en"


def test_get_language_default_after_reset():
    set_language("en")
    assert get_language() == "en"


def test_t_returns_english_string():
    set_language("en")
    assert t("ready") == "Ready"
    assert t("env_create") == "Create"
    assert t("sidebar_environments") == "Environments"


def test_t_returns_chinese_string():
    set_language("zh-TW")
    assert t("ready") == "就緒"
    assert t("env_create") == "建立"
    assert t("sidebar_environments") == "環境管理"


def test_t_fallback_to_english_for_missing_key():
    set_language("zh-TW")
    # Key that doesn't exist in any language returns the key itself
    assert t("nonexistent_key_xyz") == "nonexistent_key_xyz"


def test_t_fallback_when_key_missing_in_current_lang():
    # Temporarily add a key only in English to test fallback
    TRANSLATIONS["en"]["_test_only_en"] = "test_value"
    try:
        set_language("zh-TW")
        result = t("_test_only_en")
        assert result == "test_value"
    finally:
        del TRANSLATIONS["en"]["_test_only_en"]
        set_language("en")


def test_all_english_keys_present_in_chinese():
    """Every English key should have a Chinese translation."""
    en_keys = set(TRANSLATIONS["en"].keys())
    zh_keys = set(TRANSLATIONS["zh-TW"].keys())
    missing = en_keys - zh_keys
    assert not missing, f"Missing zh-TW translations for: {missing}"


def test_language_switcher_round_trip():
    set_language("en")
    en_val = t("ready")
    set_language("zh-TW")
    zh_val = t("ready")
    set_language("en")
    assert t("ready") == en_val
    assert en_val != zh_val

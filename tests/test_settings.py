"""Настройки для тестов."""

from pydantic_settings import BaseSettings

def test_settings_value():
    class TestSettings(BaseSettings):
        value: int = 42
    s = TestSettings()
    assert s.value == 42 
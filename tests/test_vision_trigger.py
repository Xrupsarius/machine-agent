"""Unit tests for VisionTrigger."""
import pytest
from app.vision.vision_trigger import VisionTrigger


@pytest.fixture
def trigger():
    return VisionTrigger()


# ------------------------------------------------------------------
# is_vision_query
# ------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "посмотри на экран",
    "Посмотри на экран",
    "ПОСМОТРИ НА ЭКРАН",
    "посмотри на мой экран",
    "что на экране",
    "что ты видишь",
    "опиши экран",
    "what do you see",
    "describe the screen",
    "look at the screen",
    "что происходит на экране",
    "какие окна открыты",
    "анализируй экран",
    "сделай скриншот",
    "take a screenshot",
    "сфотографируй экран",
])
def test_is_vision_query_positive(trigger, text):
    assert trigger.is_vision_query(text) is True


@pytest.mark.parametrize("text", [
    "открой браузер",
    "запусти firefox",
    "создай файл",
    "какая погода",
    "что мы делали",
    "история команд",
    "найди файл",
])
def test_is_vision_query_negative(trigger, text):
    assert trigger.is_vision_query(text) is False


def test_is_vision_query_case_insensitive(trigger):
    assert trigger.is_vision_query("ОПИШИ ЭКРАН") is True


# ------------------------------------------------------------------
# is_find_query
# ------------------------------------------------------------------

@pytest.mark.parametrize("text", [
    "найди на экране кнопку закрыть",
    "где на экране кнопка submit",
    "найди кнопку ОК",
    "найди элемент search",
    "find element submit button",
    "find button OK",
    "find on screen the menu",
    "where on screen is the button",
])
def test_is_find_query_positive(trigger, text):
    assert trigger.is_find_query(text) is True


@pytest.mark.parametrize("text", [
    "посмотри на экран",
    "опиши экран",
    "что на экране",
    "открой браузер",
    "создай файл",
])
def test_is_find_query_negative(trigger, text):
    assert trigger.is_find_query(text) is False


# ------------------------------------------------------------------
# extract_element
# ------------------------------------------------------------------

def test_extract_element_from_find_query(trigger):
    element = trigger.extract_element("найди на экране кнопку закрыть")
    assert "кнопку закрыть" in element or "закрыть" in element


def test_extract_element_strips_punctuation(trigger):
    element = trigger.extract_element("найди кнопку ОК!")
    assert "!" not in element


def test_extract_element_no_trigger_returns_full_text(trigger):
    text = "submit button"
    element = trigger.extract_element(text)
    assert "submit" in element.lower()


def test_extract_element_not_empty(trigger):
    element = trigger.extract_element("найди элемент search box")
    assert len(element) > 0

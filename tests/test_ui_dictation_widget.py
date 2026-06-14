from app.core.event_bus import EventBus
from app.stt.dictation_controller import (
    EVENT_DICTATION_PARTIAL, EVENT_DICTATION_COMMITTED,
    EVENT_DICTATION_STARTED, EVENT_DICTATION_STOPPED,
)
from app.ui.dictation_widget import DictationWidget, EVENT_DICTATION_TOGGLE


def test_partial_shows_committed_and_interim(qapp):
    bus = EventBus()
    w = DictationWidget(bus)
    bus.publish(EVENT_DICTATION_PARTIAL, {"committed": "привет", "interim": "мир"})
    text = w.display_text
    assert "привет" in text
    assert "мир" in text


def test_committed_accumulates(qapp):
    bus = EventBus()
    w = DictationWidget(bus)
    bus.publish(EVENT_DICTATION_COMMITTED, {"text": "Привет, ребята."})
    bus.publish(EVENT_DICTATION_COMMITTED, {"text": "Сегодня химия."})
    text = w.display_text
    assert "Привет, ребята." in text
    assert "Сегодня химия." in text


def test_committed_clears_interim(qapp):
    bus = EventBus()
    w = DictationWidget(bus)
    bus.publish(EVENT_DICTATION_PARTIAL, {"committed": "цель", "interim": "урока"})
    bus.publish(EVENT_DICTATION_COMMITTED, {"text": "Цель урока."})
    bus.publish(EVENT_DICTATION_PARTIAL, {"committed": "", "interim": ""})
    text = w.display_text
    assert "Цель урока." in text


def test_button_reflects_running_state(qapp):
    bus = EventBus()
    w = DictationWidget(bus)
    bus.publish(EVENT_DICTATION_STARTED, {})
    assert w._button.text() == "Стоп"
    bus.publish(EVENT_DICTATION_STOPPED, {})
    assert w._button.text() == "Старт"


def test_button_click_publishes_toggle(qapp):
    bus = EventBus()
    toggled = []
    bus.subscribe(EVENT_DICTATION_TOGGLE, lambda _: toggled.append(1))
    w = DictationWidget(bus)
    w._button.click()
    assert toggled == [1]

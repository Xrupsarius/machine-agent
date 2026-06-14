from app.core.event_bus import EventBus
from app.ui.chat_widget import ChatWidget, EVENT_CHAT_MESSAGE


def test_assistant_message_shown(qapp):
    bus = EventBus()
    w = ChatWidget(bus)
    bus.publish(EVENT_CHAT_MESSAGE, {"role": "assistant", "text": "Привет, чем помочь?"})
    text = w.display_text
    assert "Привет, чем помочь?" in text
    assert "Собеседник" in text


def test_user_message_shown(qapp):
    bus = EventBus()
    w = ChatWidget(bus)
    bus.publish(EVENT_CHAT_MESSAGE, {"role": "user", "text": "как дела"})
    text = w.display_text
    assert "как дела" in text
    assert "Вы" in text


def test_messages_accumulate(qapp):
    bus = EventBus()
    w = ChatWidget(bus)
    bus.publish(EVENT_CHAT_MESSAGE, {"role": "user", "text": "первый вопрос"})
    bus.publish(EVENT_CHAT_MESSAGE, {"role": "assistant", "text": "первый ответ"})
    text = w.display_text
    assert "первый вопрос" in text
    assert "первый ответ" in text


def test_empty_text_ignored(qapp):
    bus = EventBus()
    w = ChatWidget(bus)
    bus.publish(EVENT_CHAT_MESSAGE, {"role": "assistant", "text": ""})
    assert w.display_text.strip() == ""

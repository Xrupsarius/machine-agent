import pytest
from app.core.event_bus import EventBus


def test_subscribe_and_publish():
    bus = EventBus()
    received = []
    bus.subscribe("test", lambda data: received.append(data))
    bus.publish("test", "hello")
    assert received == ["hello"]


def test_multiple_subscribers():
    bus = EventBus()
    log = []
    bus.subscribe("evt", lambda d: log.append(f"a:{d}"))
    bus.subscribe("evt", lambda d: log.append(f"b:{d}"))
    bus.publish("evt", 1)
    assert "a:1" in log and "b:1" in log


def test_unsubscribe():
    bus = EventBus()
    called = []
    handler = lambda d: called.append(d)
    bus.subscribe("evt", handler)
    bus.unsubscribe("evt", handler)
    bus.publish("evt", "x")
    assert called == []


def test_no_subscribers_no_error():
    bus = EventBus()
    bus.publish("nonexistent", "data")


def test_duplicate_subscribe_ignored():
    bus = EventBus()
    called = []
    handler = lambda d: called.append(d)
    bus.subscribe("evt", handler)
    bus.subscribe("evt", handler)
    bus.publish("evt", 1)
    assert called == [1]


def test_handler_exception_does_not_stop_others():
    bus = EventBus()
    log = []

    def bad(d):
        raise RuntimeError("boom")

    bus.subscribe("evt", bad)
    bus.subscribe("evt", lambda d: log.append(d))
    bus.publish("evt", "ok")
    assert log == ["ok"]


def test_publish_no_data():
    bus = EventBus()
    received = []
    bus.subscribe("evt", lambda d: received.append(d))
    bus.publish("evt")
    assert received == [None]


def test_clear():
    bus = EventBus()
    called = []
    bus.subscribe("evt", lambda d: called.append(d))
    bus.clear()
    bus.publish("evt", "x")
    assert called == []

import pytest
from app.core.service_registry import ServiceRegistry, ServiceNotFoundError


def test_register_and_get():
    reg = ServiceRegistry()
    reg.register("svc", object())
    assert reg.get("svc") is not None


def test_has_returns_true_after_register():
    reg = ServiceRegistry()
    reg.register("x", 42)
    assert reg.has("x")


def test_has_returns_false_if_missing():
    reg = ServiceRegistry()
    assert not reg.has("missing")


def test_get_raises_if_not_found():
    reg = ServiceRegistry()
    with pytest.raises(ServiceNotFoundError):
        reg.get("ghost")


def test_overwrite_service():
    reg = ServiceRegistry()
    reg.register("svc", "first")
    reg.register("svc", "second")
    assert reg.get("svc") == "second"


def test_all_names():
    reg = ServiceRegistry()
    reg.register("a", 1)
    reg.register("b", 2)
    names = reg.all_names()
    assert "a" in names and "b" in names


def test_multiple_services_independent():
    reg = ServiceRegistry()
    svc_a = object()
    svc_b = object()
    reg.register("a", svc_a)
    reg.register("b", svc_b)
    assert reg.get("a") is svc_a
    assert reg.get("b") is svc_b

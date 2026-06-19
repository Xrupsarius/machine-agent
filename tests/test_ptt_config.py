from app.core.ptt_config import build_hypr_conf, is_modifier


def test_is_modifier_true_for_modifiers():
    assert is_modifier("Alt_L")
    assert is_modifier("Control_R")
    assert is_modifier("Super_L")


def test_is_modifier_false_for_normal_keys():
    assert not is_modifier("F8")
    assert not is_modifier("Insert")
    assert not is_modifier("g")


def test_build_conf_normal_key_uses_plain_binds():
    conf = build_hypr_conf("F8", "/tmp/app.pid")
    assert "bind  = , F8, exec, kill -USR1" in conf
    assert "bindr = , F8, exec, kill -USR2" in conf
    assert "/tmp/app.pid" in conf
    assert "WARNING" not in conf


def test_build_conf_modifier_uses_nonconsuming_and_warns():
    conf = build_hypr_conf("Alt_L", "/tmp/app.pid")
    assert "bindn  = , Alt_L" in conf
    assert "bindrn = , Alt_L" in conf
    assert "WARNING" in conf


def test_build_conf_mentions_both_signals():
    conf = build_hypr_conf("Insert", "/x.pid")
    assert "SIGUSR1" in conf
    assert "SIGUSR2" in conf

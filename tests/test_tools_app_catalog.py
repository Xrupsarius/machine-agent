import json
import os

from app.tools.app_catalog import AppCatalog, _parse_desktop, _clean_argv, is_app_list_query


def _write_desktop(path, name, exec_line, extra=""):
    path.write_text(
        f"[Desktop Entry]\nType=Application\nName={name}\nExec={exec_line}\n{extra}",
        encoding="utf-8",
    )


def test_clean_argv_strips_field_codes():
    assert _clean_argv("chromium %U") == ["chromium"]
    assert _clean_argv("flatpak run --branch=stable com.x.App %f") == [
        "flatpak", "run", "--branch=stable", "com.x.App",
    ]


def test_parse_desktop_basic(tmp_path):
    f = tmp_path / "x.desktop"
    _write_desktop(f, "X-Ray", "xray %U", "Keywords=scan;image;\nGenericName=Viewer")
    entry = _parse_desktop(str(f))
    assert entry["name"] == "X-Ray"
    assert entry["binary"] == "xray"
    assert entry["argv"] == ["xray"]
    assert "scan" in entry["keywords"] and "Viewer" in entry["keywords"]


def test_parse_desktop_skips_nodisplay(tmp_path):
    f = tmp_path / "hidden.desktop"
    _write_desktop(f, "Hidden", "hiddenbin", "NoDisplay=true")
    assert _parse_desktop(str(f)) is None


def test_parse_desktop_skips_non_application(tmp_path):
    f = tmp_path / "link.desktop"
    f.write_text("[Desktop Entry]\nType=Link\nName=L\nExec=x\n", encoding="utf-8")
    assert _parse_desktop(str(f)) is None


def _catalog_with(apps, tmp_path):
    cat = AppCatalog(cache_path=str(tmp_path / "cat.json"))
    cat._apps = apps
    return cat


def test_resolve_exact_name(tmp_path):
    cat = _catalog_with([{"name": "Obsidian", "binary": "obsidian", "argv": ["obsidian"], "keywords": []}], tmp_path)
    assert cat.resolve("obsidian") == ["obsidian"]
    assert cat.resolve("Obsidian") == ["obsidian"]


def test_resolve_substring_in_keywords(tmp_path):
    cat = _catalog_with([{"name": "Image Viewer", "binary": "eog", "argv": ["eog"], "keywords": ["photo"]}], tmp_path)
    assert cat.resolve("photo") == ["eog"]


def test_resolve_fuzzy(tmp_path):
    cat = _catalog_with([{"name": "XRay", "binary": "xray", "argv": ["xray"], "keywords": []}], tmp_path)
    assert cat.resolve("x-ray") == ["xray"]


def test_app_names_sorted_unique(tmp_path):
    cat = _catalog_with([
        {"name": "Obsidian", "binary": "obsidian", "argv": ["obsidian"], "keywords": []},
        {"name": "Chromium", "binary": "chromium", "argv": ["chromium"], "keywords": []},
        {"name": "Obsidian", "binary": "obsidian2", "argv": ["obsidian2"], "keywords": []},
    ], tmp_path)
    assert cat.app_names() == ["Chromium", "Obsidian"]


def test_is_app_list_query_ru():
    for q in [
        "какие у меня есть приложения",
        "выведи список приложений",
        "какие программы на компьютере",
        "что у меня установлено",
        "скажи какие приложения есть",
    ]:
        assert is_app_list_query(q), q


def test_is_app_list_query_en():
    assert is_app_list_query("list my apps")
    assert is_app_list_query("what applications are installed")


def test_is_app_list_query_negatives():
    for q in ["открой приложение для погоды", "закрой это окно", "привет как дела"]:
        assert not is_app_list_query(q), q


def test_resolve_path_binary_exact(tmp_path):
    cat = _catalog_with([], tmp_path)
    cat._binaries = ["obsidian", "telegram-desktop"]
    assert cat.resolve("obsidian") == ["obsidian"]
    assert cat.resolve("telegram") is None  # only exact binary match


def test_resolve_no_match_returns_none(tmp_path):
    cat = _catalog_with([{"name": "Obsidian", "binary": "obsidian", "argv": ["obsidian"], "keywords": []}], tmp_path)
    assert cat.resolve("totallydifferentthing") is None


def test_resolve_flatpak_argv(tmp_path):
    cat = _catalog_with([{"name": "App", "binary": "flatpak", "argv": ["flatpak", "run", "com.x.App"], "keywords": []}], tmp_path)
    assert cat.resolve("app") == ["flatpak", "run", "com.x.App"]


def test_scan_and_cache_roundtrip(tmp_path, monkeypatch):
    apps_dir = tmp_path / "applications"
    apps_dir.mkdir()
    _write_desktop(apps_dir / "a.desktop", "Alpha", "alpha %U")
    _write_desktop(apps_dir / "b.desktop", "Beta", "beta")
    monkeypatch.setattr("app.tools.app_catalog._DESKTOP_DIRS", (str(apps_dir),))

    cache = tmp_path / "cat.json"
    cat = AppCatalog(cache_path=str(cache))
    cat.load_or_scan()
    assert {a["binary"] for a in cat.apps} == {"alpha", "beta"}
    assert cache.exists()

    cat2 = AppCatalog(cache_path=str(cache))
    assert cat2._load_cache() is True
    assert cat2.resolve("alpha") == ["alpha"]


def test_stale_cache_is_ignored(tmp_path, monkeypatch):
    cache = tmp_path / "cat.json"
    cache.write_text(json.dumps({"apps": [{"name": "Old", "binary": "old", "argv": ["old"], "keywords": []}]}), encoding="utf-8")
    old = os.path.getmtime(cache) - 999999
    os.utime(cache, (old, old))
    cat = AppCatalog(cache_path=str(cache), max_age_hours=1)
    assert cat._load_cache() is False

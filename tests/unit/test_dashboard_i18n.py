"""tests/unit/test_dashboard_i18n.py – Both dashboard languages stay complete and consistent."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dashboard.helpers import file_key, flag_data_uri, fmt_rupiah
from dashboard.strings import DEFAULT_LANG, LANGS, STRINGS, translate

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def test_both_languages_have_exactly_the_same_keys():
    assert set(STRINGS["id"]) == set(STRINGS["en"])
    assert set(LANGS) == set(STRINGS)


def test_placeholders_match_between_languages():
    for key, indonesian in STRINGS["id"].items():
        english = STRINGS["en"][key]
        assert set(PLACEHOLDER.findall(indonesian)) == set(PLACEHOLDER.findall(english)), key


def test_no_empty_text():
    for lang, table in STRINGS.items():
        for key, text in table.items():
            assert text.strip(), f"{lang}/{key} is empty"


def test_every_validation_issue_code_has_a_label_in_both_languages():
    codes: set[str] = set()
    for name in ("rules.py", "matching.py"):
        source = Path("app/validation", name).read_text(encoding="utf-8")
        codes |= set(re.findall(r'code="([A-Z_]+)"', source))
    assert codes, "no issue codes found: the pattern needs updating"
    for lang in LANGS:
        missing = {c for c in codes if f"issue.{c}" not in STRINGS[lang]}
        assert not missing, f"{lang} lacks labels for {sorted(missing)}"


def test_every_key_used_by_a_view_exists():
    used: set[str] = set()
    for path in [
        *Path("dashboard/views").glob("*.py"),
        Path("dashboard/app.py"),
        Path("dashboard/widgets.py"),
    ]:
        used |= set(
            re.findall(r"""\bt\(\s*["']([a-z_.0-9]+)["']""", path.read_text(encoding="utf-8"))
        )
    missing = {k for k in used if k not in STRINGS[DEFAULT_LANG]}
    assert not missing, f"keys used in the code but not defined: {sorted(missing)}"


def test_translate_formats_values_and_falls_back():
    assert translate("en", "scan.button", n=3) == "Scan 3 receipt(s)"
    assert translate("id", "scan.button", n=3) == "Scan 3 nota"
    assert (
        translate("fr", "nav.scan") == STRINGS["id"]["nav.scan"]
    )  # unknown language -> Indonesian
    assert translate("en", "no.such.key") == "no.such.key"


def test_fmt_rupiah():
    assert fmt_rupiah(1250000) == "Rp 1.250.000"
    assert fmt_rupiah(0) == "Rp 0"
    assert fmt_rupiah(None) == "Rp -"


def test_flags_are_inline_svg_images():
    for lang in LANGS:
        assert flag_data_uri(lang).startswith("data:image/svg+xml;base64,")
    assert flag_data_uri("id") != flag_data_uri("en")


def test_same_image_gets_the_same_key():
    assert file_key(b"abc") == file_key(b"abc")
    assert file_key(b"abc") != file_key(b"abd")


def test_build_queue_scans_each_distinct_image_once():
    from dashboard.helpers import build_queue

    a, b = {"name": "a.jpg", "data": b"aaa"}, {"name": "b.jpg", "data": b"bbb"}
    copy_of_a = {"name": "a-again.jpg", "data": b"aaa"}

    queue = build_queue([a, copy_of_a, b], done={})

    assert [q["name"] for q in queue] == ["a.jpg", "b.jpg"]  # the second copy of a is dropped
    assert all(len(q["key"]) == 64 for q in queue)


def test_build_queue_skips_images_that_were_already_scanned():
    from dashboard.helpers import build_queue, file_key

    done = {file_key(b"aaa"): {"result": {}}}  # what the scan page keeps after a scan

    queue = build_queue(
        [{"name": "a.jpg", "data": b"aaa"}, {"name": "b.jpg", "data": b"bbb"}], done
    )

    assert [q["name"] for q in queue] == ["b.jpg"]
    assert build_queue([{"name": "a.jpg", "data": b"aaa"}], done) == []


def test_upload_limit_is_the_same_in_the_dashboard_config_the_ui_and_the_api():
    import tomllib

    pytest.importorskip("pydantic_settings")  # the dashboard image has no API settings
    from app.config import Settings
    from dashboard.helpers import MAX_UPLOAD_MB

    with open("dashboard/.streamlit/config.toml", "rb") as f:
        config = tomllib.load(f)

    assert config["server"]["maxUploadSize"] == MAX_UPLOAD_MB
    assert Settings(_env_file=None).max_upload_mb == MAX_UPLOAD_MB


def test_toolbar_menu_is_hidden():
    import tomllib

    with open("dashboard/.streamlit/config.toml", "rb") as f:
        assert tomllib.load(f)["client"]["toolbarMode"] == "minimal"

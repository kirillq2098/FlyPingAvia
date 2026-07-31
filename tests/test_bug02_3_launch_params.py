"""BUG-02.3: launch-params parser (Node) — Huawei/EMUI hash encoding fixtures."""

from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import quote

import pytest

ROOT = Path(__file__).resolve().parents[1]
LP = ROOT / "flypingavia/web/static/launch-params.js"


def _node(expr: str) -> str:
    script = f"""
const LP = require({str(LP)!r});
const out = ({expr});
process.stdout.write(typeof out === 'string' ? out : JSON.stringify(out));
"""
    r = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        raise AssertionError(r.stderr or r.stdout)
    return r.stdout


def _init(user_id: int = 42) -> str:
    return (
        f"query_id=AAE&user=%7B%22id%22%3A{user_id}%2C%22first_name%22%3A%22A%22%7D"
        "&auth_date=1710000000&hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )


def _theme() -> str:
    return quote(
        '{"bg_color":"#ffffff","text_color":"#000000","hint_color":"#999999",'
        '"link_color":"#2481cc","button_color":"#2481cc","button_text_color":"#ffffff",'
        '"secondary_bg_color":"#f1f1f1","header_bg_color":"#ffffff"}',
        safe="",
    )


@pytest.fixture(scope="module")
def lp_ok():
    assert LP.is_file()
    assert "FlyPingLaunchParams" in LP.read_text(encoding="utf-8")


def test_normal_hash(lp_ok):
    init = _init(1)
    h = f"#tgWebAppData={quote(init, safe='')}&tgWebAppVersion=8.0&tgWebAppPlatform=android"
    out = _node(f"LP.extractInitDataFromUrl({h!r}, '')")
    import json

    data = json.loads(out)
    assert "hash=" in data["initData"]
    assert "auth_date=" in data["initData"]


def test_search_param(lp_ok):
    init = _init(2)
    s = f"?tgWebAppData={quote(init, safe='')}&tgWebAppPlatform=android"
    out = _node(f"LP.extractInitDataFromUrl('', {s!r})")
    import json

    assert "hash=" in json.loads(out)["initData"]


def test_spa_hash_path(lp_ok):
    init = _init(3)
    h = f"#/app?tgWebAppData={quote(init, safe='')}&tgWebAppVersion=8.0"
    out = _node(f"LP.extractInitDataFromUrl({h!r}, '')")
    import json

    assert "hash=" in json.loads(out)["initData"]


def test_double_percent_encoding(lp_ok):
    init = _init(4)
    inner = f"tgWebAppData={quote(init, safe='')}&tgWebAppVersion=8.0&tgWebAppPlatform=android"
    h = "#" + quote(inner, safe="")
    assert "tgWebAppData=" not in h
    assert "tgWebAppData%3D" in h
    out = _node(f"LP.extractInitDataFromUrl({h!r}, '')")
    import json

    data = json.loads(out)
    assert "hash=" in data["initData"]
    diag = json.loads(_node(f"LP.diagnoseLaunchUrl({h!r}, '')"))
    assert diag["has_tgwebappdata"] is True
    assert diag["decode_passes"] >= 1
    assert diag["extract_ok"] is True


def test_plus_encoding(lp_ok):
    # plus-as-space in values should still recover
    init = _init(5).replace("%20", "+")
    h = f"#tgWebAppData={quote(init, safe='+')}&tgWebAppVersion=8.0"
    out = _node(f"LP.extractInitDataFromUrl({h!r}, '')")
    import json

    assert "hash=" in json.loads(out)["initData"]


def test_partial_decode_sdk_split_bug(lp_ok):
    """Simulate Huawei partial decode: inner '=' exposed; SDK split('=') keeps only query_id."""
    init = (
        "query_id=AAE&user=%7B%22id%22%3A9%7D&auth_date=1710000000"
        "&hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    # Unencoded tgWebAppData value with real & separators — broken for SDK, OK for our reassembly
    h = f"#tgWebAppData={init}&tgWebAppVersion=8.0&tgWebAppPlatform=android"
    out = _node(f"LP.extractInitDataFromUrl({h!r}, '')")
    import json

    data = json.loads(out)
    assert "hash=" in data["initData"]
    assert "auth_date=" in data["initData"]
    # SDK-style broken parse would yield only "query_id"
    sdk_broken = h.split("&")[0].split("=")
    assert sdk_broken[1] == "query_id"  # demonstrates SDK bug


def test_huawei_like_theme_only_no_init(lp_ok):
    """Hash with theme/platform but no tgWebAppData — extract must fail cleanly."""
    theme = _theme()
    # Pad theme-like payload toward ~715 chars observed on device (names only matter).
    extra = "&tgWebAppDefaultColors=" + quote('{"bg_color":"#ffffff","bottom_bar_bg_color":"#ffffff"}', safe="")
    h = f"#tgWebAppVersion=8.0&tgWebAppPlatform=android&tgWebAppThemeParams={theme}{extra}"
    while len(h) < 700:
        h += "&tgWebAppDebug=0"
    assert 500 < len(h) < 1200
    out = _node(f"LP.extractInitDataFromUrl({h!r}, '')")
    import json

    data = json.loads(out)
    assert data["initData"] == ""
    diag = json.loads(_node(f"LP.diagnoseLaunchUrl({h!r}, '')"))
    assert diag["has_tgwebappdata"] is False
    assert diag["has_tgwebapptheme"] is True
    assert diag["has_tgwebappplatform"] is True
    assert "tgWebAppThemeParams" in diag["hash_params"]
    assert diag["extract_ok"] is False


def test_diagnose_never_includes_secret_values(lp_ok):
    init = _init(7)
    h = f"#tgWebAppData={quote(init, safe='')}&tgWebAppVersion=8.0"
    diag = _node(f"LP.diagnoseLaunchUrl({h!r}, '')")
    assert "0123456789abcdef" not in diag
    assert "query_id=AAE" not in diag
    assert "first_name" not in diag
    assert "tgWebAppData" in diag


def test_leading_question_in_hash(lp_ok):
    init = _init(8)
    h = f"#?tgWebAppData={quote(init, safe='')}&tgWebAppPlatform=android"
    out = _node(f"LP.extractInitDataFromUrl({h!r}, '')")
    import json

    assert "hash=" in json.loads(out)["initData"]

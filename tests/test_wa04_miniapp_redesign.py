"""WA-04: Mini App visual system aligned with website/ brand."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "flypingavia" / "web" / "static"
WEBSITE = ROOT / "website"


def _read(*parts: str) -> str:
    return (STATIC.joinpath(*parts)).read_text(encoding="utf-8")


def test_local_telegram_sdk_and_cache_bust() -> None:
    html = _read("index.html")
    assert 'src="/assets/telegram-web-app.js"' in html
    assert "launch-params.js" in html
    assert "diag-session.js" in html
    assert "telegram.org/js/telegram-web-app.js" not in html
    assert "fonts.css?v=0.3.0-" in html
    assert "app.css?v=0.3.0-" in html
    assert "app.js?v=0.3.0-" in html
    assert (STATIC / "telegram-web-app.js").is_file()
    assert (STATIC / "launch-params.js").is_file()
    assert (STATIC / "diag-session.js").is_file()


def test_brand_tokens_from_website() -> None:
    css = _read("app.css")
    site = (WEBSITE / "app" / "globals.css").read_text(encoding="utf-8")
    for token in ("#f7f8fa", "#0b4db8", "#083a8c", "#0e9f6e", "#07111f"):
        assert token in css.lower() or token.replace("#", "#").upper() in css
        assert token in site.lower()
    assert "--color-primary" in css
    assert "--radius-sm" in css
    assert "--radius-lg" in css
    assert "safe-area-inset" in css
    assert "prefers-reduced-motion" in css
    assert "100dvh" in css
    assert "theme-dark" in css


def test_logo_asset_and_wordmark() -> None:
    assert (STATIC / "icons" / "favicon.svg").is_file()
    html = _read("index.html")
    assert "Fly" in html and "Ping" in html
    assert "favicon.svg" in html
    assert "viewBox=\"0 0 22 22\"" in html


def test_empty_loading_error_states() -> None:
    js = _read("app.js")
    css = _read("app.css")
    assert "empty-state" in js and "empty-state" in css
    assert "skeleton" in js and "skeleton-card" in css
    assert "error-state" in js
    assert "data-retry-watches" in js
    assert "aria-label" in _read("index.html")


def test_no_bot_loop_and_production_paths() -> None:
    js = _read("app.js")
    html = _read("index.html")
    assert "isInsideTelegramWebView" in js
    assert "waitForInitData" in js
    assert 'indexOf("/api/")' in js
    assert "localhost" not in js
    assert "trycloudflare" not in js
    # Browser fallback may mention t.me via health link, but HTML must not auto-redirect.
    assert "meta http-equiv=\"refresh\"" not in html.lower()
    assert "location.href" not in html


def test_accessibility_and_tap_targets() -> None:
    css = _read("app.css")
    html = _read("index.html")
    assert "--tap-min: 44px" in css
    assert 'role="tablist"' in html
    assert 'aria-live="polite"' in html
    assert "field-error" in html
    assert "sr-only" in css


def test_website_unchanged_source_of_truth() -> None:
    # Marketing site source must remain (no accidental redesign of website/).
    assert (WEBSITE / "app" / "globals.css").is_file()
    assert (WEBSITE / "components" / "ui" / "Logo.tsx").is_file()
    site_css = (WEBSITE / "app" / "globals.css").read_text(encoding="utf-8")
    assert "--blue: #0b4db8" in site_css


def test_version_still_030() -> None:
    from flypingavia.version import __version__

    assert __version__ == "0.3.1"


def test_self_hosted_fonts() -> None:
    fonts = STATIC / "fonts"
    assert (STATIC / "fonts.css").is_file()
    assert any(fonts.glob("manrope-*.woff2"))
    assert any(fonts.glob("ibm-plex-mono-*.woff2"))
    assert "Manrope" in _read("fonts.css")
    assert "IBM Plex Mono" in _read("fonts.css")

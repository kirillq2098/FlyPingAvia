"""WA-04 UX: simplify threshold input without backend contract changes."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "flypingavia" / "web" / "static"
API_APP = ROOT / "flypingavia" / "api" / "app.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_market_band_hidden_in_miniapp_ui() -> None:
    js = _read(STATIC / "app.js")
    assert '<div class="band">' not in js
    assert '<div class="band-row cheap"><span>Выгодная цена</span>' not in js
    assert '<div class="band-row typical"><span>Средняя цена</span>' not in js
    assert '<div class="band-row expensive"><span>Высокая цена</span>' not in js
    assert "относительно рынка · " not in js


def test_threshold_label_and_copy_updated() -> None:
    html = _read(STATIC / "index.html")
    assert "При какой цене сообщить?" in html
    assert "Ваш порог, ₽" not in html


def test_threshold_starts_empty_after_quote() -> None:
    js = _read(STATIC / "app.js")
    assert "if (!opts.keepThreshold) {" in js
    assert 'thresholdInput.value = "";' in js
    assert '$("#threshold").value = Math.round(q.cheap_max || q.price || 0);' not in js


def test_recommended_threshold_used_as_placeholder_only() -> None:
    js = _read(STATIC / "app.js")
    assert "const recommended = Math.round(q.cheap_max || q.price || 0);" in js
    assert '"Например, " + money(recommended)' in js
    assert '"Введите желаемую цену"' in js
    # API payload still uses explicit user-entered threshold.
    assert "max_price: threshold" in js


def test_empty_submit_validation_is_human_readable() -> None:
    js = _read(STATIC / "app.js")
    assert "Укажите цену, при которой вам сообщить" in js
    assert "Введите порог числом, например 12000" not in js


def test_low_threshold_warning_flow_preserved() -> None:
    js = _read(STATIC / "app.js")
    assert "shouldWarnLowThresholdLocal(threshold)" in js
    assert "showLowThresholdWarn" in js
    assert "confirm_low_threshold: !!confirmLow" in js
    assert "LOW_THRESHOLD_CONFIRMATION_REQUIRED" in _read(API_APP)


def test_no_auto_presets_for_market_band_thresholds() -> None:
    html = _read(STATIC / "index.html")
    js = _read(STATIC / "app.js")
    assert 'data-preset="cheap"' not in html
    assert 'data-preset="typical"' not in html
    assert '$$("[data-preset]")' not in js


def test_backend_market_band_contract_unchanged() -> None:
    api_code = _read(API_APP)
    assert "market_band_source" in api_code
    assert "cheap_max" in api_code
    assert "typical" in api_code
    assert "expensive_min" in api_code

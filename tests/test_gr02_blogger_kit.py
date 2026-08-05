"""GR-02: блогер-кит — документация без изменений кода продукта."""

from __future__ import annotations

import re
from pathlib import Path

from flypingavia.version import __version__

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "docs" / "BLOGGER_KIT.md"
BACKLOG = ROOT / "docs" / "FEATURE_BACKLOG.md"

PAYLOAD_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# payload в таблицах / примерах start=
START_PAYLOAD_RE = re.compile(
    r"(?:start=|`|\|\s*)((?:blogger|tg|partner)_[A-Za-z0-9_-]+|[A-Za-z0-9_-]{3,64})(?:`|\s*\||\s*$)"
)
CYRILLIC_IN_PAYLOAD = re.compile(r"start=([^\s`|]+)")


def test_blogger_kit_exists_and_structure() -> None:
    assert KIT.is_file()
    text = KIT.read_text(encoding="utf-8")
    low = text.lower()

    assert "креатив 1" in low and "креатив 2" in low and "креатив 3" in low
    assert "сценарий 1" in low and "сценарий 2" in low and "сценарий 3" in low

    assert "t.me/FlyPingBot?start=" in text or "t.me/<BOT_USERNAME>?start=" in text
    assert "blogger_" in text and "tg_" in text and "partner_" in text

    assert "не продаёт билеты" in low or "не продает билеты" in low
    assert "самый дешёвый" in low or "самый дешевый" in low
    assert "нельзя" in low
    assert "referral" in low or "реферальн" in low
    assert "не реализован" in low

    assert "чек-лист" in low or "checklist" in low
    assert "можно говорить" in low
    assert "faq" in low

    assert "bot_token" not in low
    assert re.search(r"\d{8,12}:[A-Za-z0-9_-]{20,}", text) is None
    assert "share_<token>" in text
    assert re.search(r"start=share_[A-Za-z0-9_-]{8,}", text) is None


def test_blogger_kit_payloads_valid() -> None:
    text = KIT.read_text(encoding="utf-8")
    for raw in ("tg_travelnews", "blogger_annatrip", "partner_weekend"):
        assert PAYLOAD_RE.match(raw)
        assert re.search(r"[А-Яа-яЁё]", raw) is None

    for m in CYRILLIC_IN_PAYLOAD.finditer(text):
        payload = m.group(1).rstrip(")")
        # плейсхолдеры <name> / [payload] / [BOT_USERNAME]
        if "<" in payload or ">" in payload or "[" in payload or "]" in payload:
            continue
        assert re.search(r"[А-Яа-яЁё]", payload) is None, payload
        assert PAYLOAD_RE.match(payload), payload

    assert "кириллиц" in text.lower()
    assert "пробел" in text.lower()


def test_blogger_kit_backlog_and_version() -> None:
    backlog = BACKLOG.read_text(encoding="utf-8")
    assert "GR-02 · Done" in backlog
    section = backlog.split("### GR-02")[1].split("###")[0]
    assert "**Статус:** Done" in section or "Статус:** Done" in section
    assert "BLOGGER_KIT.md" in section

    assert __version__ == "0.3.1"
    assert (ROOT / "docs" / "MARKETING.md").read_text(encoding="utf-8").find(
        "BLOGGER_KIT"
    ) >= 0
    assert (ROOT / "docs" / "CHANGELOG.md").read_text(encoding="utf-8").find("GR-02") >= 0


def test_gr02_did_not_change_product_code_paths() -> None:
    """Смоук: кит — docs; handlers/api не обязаны меняться для GR-02."""
    # файл кита есть; ключевые модули продукта на месте (не удалялись)
    assert (ROOT / "flypingavia" / "bot" / "handlers.py").is_file()
    assert (ROOT / "flypingavia" / "api" / "app.py").is_file()
    assert KIT.is_file()

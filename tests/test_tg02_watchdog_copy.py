"""TG-02: FlyPing как сторож цены — fixed copy в Telegram и Mini App."""

from __future__ import annotations

from pathlib import Path

from flypingavia.bot import formatters as fmt
from flypingavia.bot import keyboards as kb
from flypingavia.bot.formatters import format_price_card
from flypingavia.services.prices import PriceBand, PriceQuote


ROOT = Path(__file__).resolve().parents[1]


def test_start_watchdog_positioning() -> None:
    text = fmt.format_start_message("Кирилл")
    low = text.lower()
    assert "сторож цены" in low
    assert "один раз" in low
    assert "уведомление" in low
    assert "подходящ" in low
    assert "поисковик" not in low
    assert "метапоиск" not in low
    assert "самую низкую" not in low
    assert "самая низкая" not in low
    assert "парсинг" not in low
    assert "checker" not in low
    assert "watch" not in low
    assert "fsm" not in low
    assert "api" not in low
    assert "Кирилл" in text
    assert len(text) < 900


def test_start_html_escape_and_empty_name() -> None:
    text = fmt.format_start_message("<script>")
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
    empty = fmt.format_start_message(None)
    assert "None" not in empty
    assert empty.startswith("Привет! 👋")
    blank = fmt.format_start_message("   ")
    assert blank.startswith("Привет! 👋")


def test_help_partner_not_seller() -> None:
    text = fmt.format_help_message()
    low = text.lower()
    assert "не продаёт" in low or "не продает" in low
    assert "партнёр" in low or "партнер" in low
    assert "Watch" not in text
    assert "checker" not in low
    assert "fsm" not in low


def test_empty_watches_cta() -> None:
    text = fmt.format_empty_watches_message()
    assert "подпис" in text.lower()
    assert "создайте" in text.lower() or "создай" in text.lower()
    assert "Watch" not in text


def test_add_intro_ties_to_promise() -> None:
    text = fmt.format_add_watch_intro()
    assert "подписк" in text.lower()
    assert "откуда" in text.lower()
    assert "Watch" not in text


def test_welcome_alias() -> None:
    assert fmt.welcome_text("Анна") == fmt.format_start_message("Анна")
    assert fmt.help_text() == fmt.format_help_message()


def test_alert_copy_has_watchdog_line() -> None:
    quote = PriceQuote(price=15_000, currency="RUB", origin_code="MOW", destination_code="AYT")
    band = PriceBand(10_000, 18_000, 25_000, sample_size=5, currency="RUB")
    text = format_price_card(
        origin="MOW",
        destination="AYT",
        depart_date=None,
        quote=quote,
        band=band,
        threshold=20_000,
        threshold_contract=True,
    )
    assert "FlyPing заметил цену не выше вашего порога." in text
    assert "забронировали" not in text.lower()
    assert "гарантир" not in text.lower()
    assert "лучшая цена на рынке" not in text.lower()


def test_main_menu_buttons_and_webapp() -> None:
    with_url = kb.main_menu("https://app.example.com")
    texts = [b.text for row in with_url.keyboard for b in row]
    assert kb.BTN_CREATE_WATCH in texts
    assert kb.BTN_MY_WATCHES in texts
    assert kb.BTN_OPEN_FLYPING in texts
    assert with_url.keyboard[0][0].web_app is not None

    no_url = kb.main_menu(None)
    texts2 = [b.text for row in no_url.keyboard for b in row]
    assert kb.BTN_OPEN_FLYPING not in texts2
    assert kb.BTN_CREATE_WATCH in texts2
    assert kb.BTN_MY_WATCHES in texts2


def test_list_empty_kb_callback_unchanged() -> None:
    markup = kb.list_empty_kb()
    btn = markup.inline_keyboard[0][0]
    assert btn.callback_data == "menu:add"
    assert "подписк" in btn.text.lower()


def test_handlers_use_formatters_and_button_constants() -> None:
    src = (ROOT / "flypingavia/bot/handlers.py").read_text(encoding="utf-8")
    assert "format_start_message" in src
    assert "format_help_message" in src
    assert "format_empty_watches_message" in src
    assert "format_add_watch_intro" in src
    assert "BTN_CREATE_WATCH" in src
    assert "BTN_MY_WATCHES" in src
    assert 'F.text == "➕ Добавить"' not in src
    assert "menu:add" in src
    assert "menu:list" in src
    # /start не создаёт Watch — только clear state + ensure user
    start_chunk = src.split("async def cmd_start")[1].split("async def cmd_help")[0]
    assert "add_watch" not in start_chunk
    assert "format_start_message" in start_chunk


def test_frontend_tg02_and_wa03_preserved() -> None:
    html = (ROOT / "flypingavia/web/static/index.html").read_text(encoding="utf-8")
    js = (ROOT / "flypingavia/web/static/app.js").read_text(encoding="utf-8")
    css = (ROOT / "flypingavia/web/static/app.css").read_text(encoding="utf-8")

    assert "проверять цену за вас" in js
    assert "Создать подписку" in html or "Создать подписку" in js
    assert "data-empty-create" in js
    assert "Watch" not in html.split("id=\"")[0]  # soft: user-facing copy in body
    # User-visible Russian UI should not say Watch
    assert ">Watch<" not in html
    assert "Пока нет подписок" in js or "Пока нет подписок" in html

    assert "auth-gate" in html
    assert '"tma "' in js
    assert "flexibilityDays" in js or "flexibility_days" in js
    assert "formatLastChecked" in js
    assert "--tg-bg-color" in css
    assert "themeChanged" in js


def test_copy_guide_exists_fixed() -> None:
    guide = (ROOT / "docs/COPY_GUIDE.md").read_text(encoding="utf-8")
    assert "сторож цены" in guide.lower()
    assert "A/B" in guide or "a/b" in guide.lower()
    assert "не внедрялось" in guide.lower() or "не внедрял" in guide.lower()
    assert "партнёр" in guide.lower() or "партнер" in guide.lower()


def test_feature_backlog_tg02_done() -> None:
    backlog = (ROOT / "docs/FEATURE_BACKLOG.md").read_text(encoding="utf-8")
    assert "### TG-02" in backlog
    # status line under TG-02 card
    chunk = backlog.split("### TG-02")[1].split("### TG-03")[0]
    assert "**Статус:** Done" in chunk

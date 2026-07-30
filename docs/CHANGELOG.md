# Changelog — FlyPingAvia

Связанные документы: [Architecture](TECH_ARCHITECTURE.md) · [Decisions](DECISIONS.md) · [Roadmap](MASTER_ROADMAP.md)

История по значимым коммитам ветки продукта. Формат близкий к Keep a Changelog; версии — по смыслу релизов в git. Git tags создавать вручную после merge и production smoke (см. README).

## [Unreleased]

### Added

- **TG-02:** единое позиционирование FlyPing как сторожа цены в Telegram и Mini App (`format_start_message` / `format_help_message`, COPY_GUIDE, fixed copy без A/B).

### Changed

-

## [0.3.0] — 2026-07-30

### Added

- Telegram Mini App authentication via signed initData (WA-03).
- Flexible dates MVP (CS-07).
- Last checked timestamp (TR-04).
- Stable production HTTPS configuration (WA-02 code).
- Notification market context and anti-spam (NT-02/03/04).
- Low-threshold confirmation (CS-05).
- Alert events log (AN-03).

### Changed

- Unified application version metadata (RL-02): `pyproject.toml` → `flypingavia.version` → `__version__`, FastAPI, `/api/health`, CLI `--version`, Docker OCI label.

### Security

- User isolation in Mini App API.
- Production rejects development authentication fallback (`WEBAPP_DEV_USER_ID` must be 0).

### Documentation

- `docs/SECURITY.md`; обновлены FEATURE_BACKLOG, USER_JOURNEY, TECH_ARCHITECTURE, PRODUCTION checklist path.

## [0.2.0] — 2026-07

Ориентир: Mini App MVP до auth hardening.

### Added

- Telegram Mini App: поиск, вилка цен, подписки (`feat: Telegram Mini App…`)
- Города словами и поиск по аэропортам города
- Кнопки меню, карточки маршрутов, вилка дёшево/обычно/дорого
- Пассажиры и билет туда–обратно в модели/потоках (позже UI pax скрыт)
- Watchdog/supervise для бота и HTTPS-туннеля (development)
- Папка `docs/`: vision, strategy, feature backlog, user journey, sprint 01, roadmap, competitive analysis, architecture, monetization, marketing, decisions, KPI, changelog

### Changed

- Документация и README вокруг MVP Mini App

### Known

- До RL-02: `flypingavia.__version__` мог отличаться от `pyproject.toml` / FastAPI.

## [0.1.0] — 2026-07

### Added

- MVP Telegram-бот мониторинга цен (`feat: MVP 0.1.0`)
- Demo / Travelpayouts quotes, алерты, affiliate URL
- SQLite User/Watch, APScheduler checker

### Notes

- При релизе после merge — опциональный ручной tag `v0.3.0` (не создаётся автоматически).

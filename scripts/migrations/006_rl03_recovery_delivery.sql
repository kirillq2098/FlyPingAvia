-- RL-03 fix: pending recovery delivery (не закрывать incident до успешной отправки)
-- Runtime: create_all + ALTER catch-up в init_db для SQLite.

-- Новая колонка (SQLite / Postgres-совместимый стиль проекта).
-- На чистой БД колонка создаётся через SQLAlchemy create_all.

ALTER TABLE system_health_incidents ADD COLUMN recovery_notified_at DATETIME;

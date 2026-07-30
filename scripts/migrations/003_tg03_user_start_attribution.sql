-- TG-03: first/last start attribution на users
-- Проект использует SQL-миграции + init_db SQLite ALTER (Alembic не подключён).
-- Upgrade (SQLite):
ALTER TABLE users ADD COLUMN first_start_source VARCHAR(64);
ALTER TABLE users ADD COLUMN last_start_source VARCHAR(64);
ALTER TABLE users ADD COLUMN first_start_at DATETIME;
ALTER TABLE users ADD COLUMN last_start_at DATETIME;

-- Downgrade (SQLite не умеет DROP COLUMN до 3.35; на новых SQLite):
-- ALTER TABLE users DROP COLUMN first_start_source;
-- ALTER TABLE users DROP COLUMN last_start_source;
-- ALTER TABLE users DROP COLUMN first_start_at;
-- ALTER TABLE users DROP COLUMN last_start_at;

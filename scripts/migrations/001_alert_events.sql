-- AN-03: лог успешных алертов (North Star / аналитика)
-- Runtime: таблица создаётся через SQLAlchemy Base.metadata.create_all в init_db().
-- Этот файл — явная миграция для ручного применения на уже существующей SQLite.

CREATE TABLE IF NOT EXISTS alert_events (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    watch_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    price FLOAT NOT NULL,
    threshold FLOAT NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'RUB',
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(watch_id) REFERENCES watches (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_alert_events_watch_id ON alert_events (watch_id);
CREATE INDEX IF NOT EXISTS ix_alert_events_user_id ON alert_events (user_id);
CREATE INDEX IF NOT EXISTS ix_alert_events_sent_at ON alert_events (sent_at);

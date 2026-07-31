-- WA-04 hotfix: idempotency for POST /api/watches
-- Also created via SQLAlchemy metadata.create_all on init_db().

CREATE TABLE IF NOT EXISTS watch_create_idempotency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key VARCHAR(128) NOT NULL,
    watch_id INTEGER NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, key)
);

CREATE INDEX IF NOT EXISTS ix_watch_create_idempotency_user_id
    ON watch_create_idempotency (user_id);
CREATE INDEX IF NOT EXISTS ix_watch_create_idempotency_watch_id
    ON watch_create_idempotency (watch_id);
CREATE INDEX IF NOT EXISTS ix_watch_create_idempotency_created_at
    ON watch_create_idempotency (created_at);

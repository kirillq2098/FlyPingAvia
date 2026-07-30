-- TG-04: share tokens для копирования Watch (opaque token, без raw в БД)
-- Runtime: create_all + этот файл для ручного применения на существующей SQLite.

CREATE TABLE IF NOT EXISTS watch_share_tokens (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    watch_id INTEGER NOT NULL,
    owner_user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    used_count INTEGER NOT NULL DEFAULT 0,
    max_uses INTEGER NOT NULL DEFAULT 20,
    revoked_at DATETIME,
    FOREIGN KEY(watch_id) REFERENCES watches (id) ON DELETE CASCADE,
    FOREIGN KEY(owner_user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_watch_share_tokens_token_hash ON watch_share_tokens (token_hash);
CREATE INDEX IF NOT EXISTS ix_watch_share_tokens_watch_id ON watch_share_tokens (watch_id);
CREATE INDEX IF NOT EXISTS ix_watch_share_tokens_owner_user_id ON watch_share_tokens (owner_user_id);

CREATE TABLE IF NOT EXISTS watch_share_redemptions (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    share_token_id INTEGER NOT NULL,
    recipient_user_id INTEGER NOT NULL,
    created_watch_id INTEGER NOT NULL,
    redeemed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(share_token_id) REFERENCES watch_share_tokens (id) ON DELETE CASCADE,
    FOREIGN KEY(recipient_user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(created_watch_id) REFERENCES watches (id) ON DELETE CASCADE,
    UNIQUE (share_token_id, recipient_user_id)
);

CREATE INDEX IF NOT EXISTS ix_watch_share_redemptions_share_token_id ON watch_share_redemptions (share_token_id);
CREATE INDEX IF NOT EXISTS ix_watch_share_redemptions_recipient_user_id ON watch_share_redemptions (recipient_user_id);

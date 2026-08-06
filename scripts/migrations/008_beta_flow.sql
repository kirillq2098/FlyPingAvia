-- Phase A Closed Beta flow
-- Upgrade: idempotent CREATE TABLE/INDEX IF NOT EXISTS only.
-- Does not ALTER existing non-beta tables or mutate user/watch data.
-- Tables are NOT created by init_db() — apply this migration explicitly
-- before enabling BETA_ENABLED=true.
-- Safe to re-run.
-- Downgrade (SQLite 3.35+):
--   DROP TABLE IF EXISTS beta_jobs;
--   DROP TABLE IF EXISTS beta_bugs;
--   DROP TABLE IF EXISTS beta_surveys;
--   DROP TABLE IF EXISTS beta_participants;

CREATE TABLE IF NOT EXISTS beta_participants (
    user_id INTEGER PRIMARY KEY,
    cohort_code VARCHAR(32) NOT NULL,
    joined_at DATETIME NOT NULL,
    onboarding_sent_at DATETIME,
    consent_at DATETIME,
    messaging_opt_out_at DATETIME,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS beta_surveys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    survey_key VARCHAR(8) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    scheduled_for DATETIME,
    sent_at DATETIME,
    completed_at DATETIME,
    result VARCHAR(32),
    clarity_score INTEGER,
    free_text VARCHAR(1000),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, survey_key)
);

CREATE INDEX IF NOT EXISTS ix_beta_surveys_user_id ON beta_surveys(user_id);

CREATE TABLE IF NOT EXISTS beta_bugs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    severity VARCHAR(8) NOT NULL,
    device_class VARCHAR(16) NOT NULL,
    device_note VARCHAR(128),
    what_did VARCHAR(1000) NOT NULL,
    what_happened VARCHAR(1000) NOT NULL,
    what_expected VARCHAR(1000) NOT NULL,
    created_at DATETIME NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'open',
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_beta_bugs_user_id ON beta_bugs(user_id);
CREATE INDEX IF NOT EXISTS ix_beta_bugs_created_at ON beta_bugs(created_at);

CREATE TABLE IF NOT EXISTS beta_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    logical_key VARCHAR(128) NOT NULL UNIQUE,
    job_type VARCHAR(32) NOT NULL,
    user_id INTEGER,
    run_at DATETIME NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error_summary VARCHAR(500),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_beta_jobs_status_run_at ON beta_jobs(status, run_at);

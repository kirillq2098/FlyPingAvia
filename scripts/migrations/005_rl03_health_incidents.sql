-- RL-03: system health incidents + runtime heartbeat
-- Runtime: create_all + этот файл для ручного применения на существующей SQLite.

CREATE TABLE IF NOT EXISTS system_health_incidents (
    id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    incident_key VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'open',
    first_failed_at DATETIME NOT NULL,
    last_failed_at DATETIME NOT NULL,
    recovered_at DATETIME,
    last_notified_at DATETIME,
    failure_count INTEGER NOT NULL DEFAULT 0,
    last_error_code VARCHAR(64),
    last_error_summary VARCHAR(500),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_system_health_incidents_incident_key
    ON system_health_incidents (incident_key);
CREATE INDEX IF NOT EXISTS ix_system_health_incidents_status
    ON system_health_incidents (status);

CREATE TABLE IF NOT EXISTS system_runtime_state (
    component_key VARCHAR(64) NOT NULL PRIMARY KEY,
    last_started_at DATETIME,
    last_completed_at DATETIME,
    last_success_at DATETIME,
    last_error_at DATETIME,
    last_error_summary VARCHAR(500),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Alerted Watchers (30d) — North Star proxy
-- Пользователи с ≥1 успешным алертом за последние 30 дней.

SELECT COUNT(DISTINCT user_id) AS alerted_watchers_30d
FROM alert_events
WHERE sent_at >= datetime('now', '-30 days');

-- CS-07 MVP: окно гибких дат вокруг основной даты Watch.
-- Существующие строки получают 0 (только эта дата).

ALTER TABLE watches ADD COLUMN flexibility_days INTEGER NOT NULL DEFAULT 0;

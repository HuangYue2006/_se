-- DeadlineMate Cloud 資料表
CREATE TABLE IF NOT EXISTS users (
    key            TEXT PRIMARY KEY,
    semester_start TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS courses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key      TEXT NOT NULL,
    name          TEXT NOT NULL,
    code          TEXT DEFAULT '',
    room          TEXT DEFAULT '',
    day           INTEGER NOT NULL,
    start_period  INTEGER NOT NULL,
    end_period    INTEGER NOT NULL,
    color         TEXT DEFAULT '#4f7cff'
);
CREATE INDEX IF NOT EXISTS idx_courses_user ON courses (user_key);

CREATE TABLE IF NOT EXISTS assignments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_key    TEXT NOT NULL,
    course_id   INTEGER,
    title       TEXT NOT NULL,
    due         TEXT NOT NULL,          -- 台灣時間 "YYYY-MM-DDTHH:MM"
    note        TEXT DEFAULT '',
    priority    INTEGER DEFAULT 2,
    done        INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_assignments_user ON assignments (user_key, done, due);

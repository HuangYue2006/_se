-- 第一次建立資料庫 volume 時自動執行
CREATE TABLE IF NOT EXISTS assignments (
    id          SERIAL PRIMARY KEY,
    course      TEXT NOT NULL,
    title       TEXT NOT NULL,
    due         TIMESTAMP NOT NULL,
    done        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assignments_due ON assignments (due);

INSERT INTO assignments (course, title, due) VALUES
    ('軟體工程', '第 6 週：Docker 使用', NOW() + INTERVAL '2 days'),
    ('計算機結構', 'Verilog 期中實作', NOW() + INTERVAL '5 days'),
    ('資料結構', 'Lab5 二元搜尋樹', NOW() + INTERVAL '1 day'),
    ('網頁程式設計', '個人網站', NOW() - INTERVAL '3 hours');

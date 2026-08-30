
CREATE TABLE IF NOT EXISTS chapter_missions (
    id VARCHAR NOT NULL,
    chapter INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    description VARCHAR,
    "order" INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT true,
    CONSTRAINT pk_chapter_missions PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS idx_chapter_missions_chapter ON chapter_missions (chapter);
CREATE INDEX IF NOT EXISTS idx_chapter_missions_order ON chapter_missions ("order");

INSERT INTO chapter_missions (id, chapter, title, description, "order", is_active) VALUES
    ('chapter_mission_0', 0, 'ログインしてください', 'フロントエンドURLを開き、メールアドレスとパスワードでログインしましょう。', 0, true),
    ('chapter_mission_1', 1, '5000円の経費申請をしてください', '「申請一覧」から新規申請を作成し、経費申請として5000円を申請しましょう。', 1, true),
    ('chapter_mission_2', 2, '上長の承認済み一覧が遅いようなので分析してください', '承認済み一覧の表示が遅い原因をNew Relicで分析しましょう。', 2, true),
    ('chapter_mission_3', 3, '国内出張（北九州→札幌）申請をしてください', '出発地・到着地を指定して国内出張申請を作成しましょう。', 3, true),
    ('chapter_mission_4', 4, '上長で、Awesome AI Coding Agentライセンス費用申請を承認してください', '承認待ちの申請を承認しましょう。', 4, true),
    ('chapter_mission_5', 5, '上長でプロモーション申請をしてください', 'プロモーション申請を作成しましょう。', 5, true)
ON CONFLICT (id) DO NOTHING;

-- Kali ToolKit 数据库结构
-- 注意：实际导入由 backend/import_data.py 内联建表完成，本文件作为结构文档与参考。
-- 中文搜索使用 LIKE 子串匹配（unicode61 分词器不支持中文分词，FTS5 收益有限），故不建 FTS 虚表。

CREATE TABLE IF NOT EXISTS tools (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    subcategory TEXT,
    description_en TEXT NOT NULL,
    description_zh TEXT NOT NULL,
    official_url TEXT,
    manual_page TEXT,
    icon_emoji TEXT DEFAULT '🔧',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id INTEGER NOT NULL,
    command_template TEXT NOT NULL,
    description_en TEXT,
    description_zh TEXT,
    use_case TEXT,
    is_example BOOLEAN DEFAULT 0,
    FOREIGN KEY (tool_id) REFERENCES tools(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    name_zh TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_tags (
    tool_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (tool_id, tag_id),
    FOREIGN KEY (tool_id) REFERENCES tools(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tool_id INTEGER NOT NULL,
    related_tool_id INTEGER NOT NULL,
    relation_type TEXT DEFAULT 'often_used_with',
    FOREIGN KEY (tool_id) REFERENCES tools(id) ON DELETE CASCADE,
    FOREIGN KEY (related_tool_id) REFERENCES tools(id) ON DELETE CASCADE
);

-- 常用查询的索引（tools.name 已有 UNIQUE 索引）
CREATE INDEX IF NOT EXISTS idx_commands_tool_id ON commands(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_tags_tag_id ON tool_tags(tag_id);
CREATE INDEX IF NOT EXISTS idx_relations_tool_id ON relations(tool_id);
CREATE INDEX IF NOT EXISTS idx_relations_related ON relations(related_tool_id);

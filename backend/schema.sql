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
CREATE VIRTUAL TABLE IF NOT EXISTS tools_fts USING fts5(
    name,
    description_en,
    description_zh,
    command_templates,
    content=tools
);
CREATE TRIGGER IF NOT EXISTS tools_fts_after_insert AFTER INSERT ON tools BEGIN
    INSERT INTO tools_fts(rowid, name, description_en, description_zh, command_templates)
    VALUES (new.id, new.name, new.description_en, new.description_zh, '');
END;
CREATE TRIGGER IF NOT EXISTS tools_fts_after_update AFTER UPDATE ON tools BEGIN
    UPDATE tools_fts 
    SET name = new.name, 
        description_en = new.description_en, 
        description_zh = new.description_zh
    WHERE rowid = new.id;
END;
CREATE TRIGGER IF NOT EXISTS tools_fts_after_delete AFTER DELETE ON tools BEGIN
    DELETE FROM tools_fts WHERE rowid = old.id;
END;
CREATE TRIGGER IF NOT EXISTS tools_fts_update_cmd AFTER INSERT ON commands BEGIN
    UPDATE tools_fts 
    SET command_templates = (
        SELECT group_concat(command_template, ' ') 
        FROM commands 
        WHERE tool_id = new.tool_id
    )
    WHERE rowid = new.tool_id;
END;

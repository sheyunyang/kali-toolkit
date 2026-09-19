import sqlite3
import json
import os

def import_tools_from_json(db_path, json_path):
    """从 JSON 文件导入工具数据到 SQLite 数据库"""
    
    if not os.path.exists(json_path):
        print(f"❌ 错误：找不到 {json_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # ========== 自动建表（如果不存在） ==========
    schema = """
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
    """
    cursor.executescript(schema)
    conn.commit()
    # ========== 建表结束 ==========
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"📖 读取到 {len(data.get('tools', []))} 个工具")
    
    # 1. 导入标签
    tag_map = {}
    for tag in data.get('tags_preset', []):
        cursor.execute(
            'INSERT OR IGNORE INTO tags (name, name_zh) VALUES (?, ?)',
            (tag['name'], tag['name_zh'])
        )
        cursor.execute('SELECT id FROM tags WHERE name = ?', (tag['name'],))
        result = cursor.fetchone()
        if result:
            tag_map[tag['name']] = result[0]
    print(f"🏷️ 导入 {len(tag_map)} 个标签")
    
    # 2. 导入工具
    tool_count = 0
    for tool in data.get('tools', []):
        cursor.execute('''
            INSERT OR REPLACE INTO tools 
            (name, category, subcategory, description_en, description_zh, official_url, manual_page, icon_emoji)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            tool['name'], 
            tool.get('category', '未分类'), 
            tool.get('subcategory', ''),
            tool['description_en'], 
            tool['description_zh'],
            tool.get('official_url', ''), 
            tool.get('manual_page', ''),
            tool.get('icon_emoji', '🔧')
        ))
        tool_id = cursor.lastrowid
        tool_count += 1
        
        for cmd in tool.get('commands', []):
            cursor.execute('''
                INSERT INTO commands 
                (tool_id, command_template, description_en, description_zh, use_case)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                tool_id, 
                cmd['command_template'], 
                cmd.get('description_en', ''),
                cmd.get('description_zh', ''),
                cmd.get('use_case', '')
            ))
        
        for tag_name in tool.get('tags', []):
            tag_id = tag_map.get(tag_name)
            if tag_id:
                cursor.execute(
                    'INSERT OR IGNORE INTO tool_tags (tool_id, tag_id) VALUES (?, ?)', 
                    (tool_id, tag_id)
                )
        
        for rel_name in tool.get('relations', []):
            cursor.execute('SELECT id FROM tools WHERE name = ?', (rel_name,))
            rel_result = cursor.fetchone()
            if rel_result:
                cursor.execute(
                    'INSERT OR IGNORE INTO relations (tool_id, related_tool_id) VALUES (?, ?)', 
                    (tool_id, rel_result[0])
                )
    
    conn.commit()
    conn.close()
    
    print(f"✅ 导入完成！共导入 {tool_count} 个工具")
    print(f"📁 数据库文件：{db_path}")

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, 'tools.db')
    json_path = os.path.join(os.path.dirname(script_dir), 'data', 'tools_data.json')
    
    import_tools_from_json(db_path, json_path)
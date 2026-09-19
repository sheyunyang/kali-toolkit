from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
import threading
from typing import List, Optional
from pydantic import BaseModel
import updater

# ========== 数据模型 ==========
class Command(BaseModel):
    command_template: str
    description_en: Optional[str] = ""
    description_zh: Optional[str] = ""
    use_case: Optional[str] = ""

class Tool(BaseModel):
    id: int
    name: str
    category: str
    subcategory: Optional[str] = ""
    description_en: str
    description_zh: str
    official_url: Optional[str] = ""
    manual_page: Optional[str] = ""
    icon_emoji: Optional[str] = "🔧"
    tags: List[str] = []
    relations: List[str] = []
    commands: List[Command] = []

class SearchResult(BaseModel):
    tools: List[Tool]
    total: int

# ========== FastAPI 初始化 ==========
app = FastAPI(title="Kali ToolKit API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "tools.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ========== 搜索核心 ==========
def search_tools(query: str, tag: Optional[str] = None, limit: int = 50) -> List[Tool]:
    conn = get_db()
    cursor = conn.cursor()
    
    sql = """
        SELECT DISTINCT t.id, t.name, t.category, t.subcategory,
               t.description_en, t.description_zh, t.official_url,
               t.manual_page, t.icon_emoji
        FROM tools t
        LEFT JOIN tool_tags tt ON t.id = tt.tool_id
        LEFT JOIN tags tg ON tt.tag_id = tg.id
        WHERE 1=1
    """
    params = []
    
    if query and query.strip():
        sql += " AND (t.name LIKE ? OR t.description_zh LIKE ? OR t.description_en LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])
    
    if tag and tag.strip():
        sql += " AND tg.name = ?"
        params.append(tag)
    
    sql += " LIMIT ?"
    params.append(limit)
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    
    tools = []
    for row in rows:
        tid = row['id']
        
        cursor.execute("""
            SELECT tg.name FROM tags tg
            JOIN tool_tags tt ON tg.id = tt.tag_id
            WHERE tt.tool_id = ?
        """, (tid,))
        tags = [r['name'] for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT t.name FROM tools t
            JOIN relations r ON t.id = r.related_tool_id
            WHERE r.tool_id = ?
        """, (tid,))
        relations = [r['name'] for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT command_template, description_en, description_zh, use_case
            FROM commands WHERE tool_id = ?
        """, (tid,))
        commands = [Command(**dict(c)) for c in cursor.fetchall()]
        
        tools.append(Tool(
            id=row['id'], name=row['name'], category=row['category'],
            subcategory=row['subcategory'] or "",
            description_en=row['description_en'], description_zh=row['description_zh'],
            official_url=row['official_url'] or "", manual_page=row['manual_page'] or "",
            icon_emoji=row['icon_emoji'] or "🔧",
            tags=tags, relations=relations, commands=commands
        ))
    
    conn.close()
    return tools

# ========== API 接口 ==========
@app.get("/")
def root():
    return {"message": "Kali ToolKit API 已启动 🚀", "version": "0.1.0"}

@app.get("/api/search", response_model=SearchResult)
def search(
    q: str = Query("", description="搜索关键词"),
    tag: Optional[str] = Query(None, description="标签过滤"),
    limit: int = Query(2000)
):
    results = search_tools(q, tag, limit)
    return SearchResult(tools=results, total=len(results))

@app.get("/api/tags")
def get_all_tags():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT name, name_zh FROM tags ORDER BY name")
    tags = [{"name": r['name'], "name_zh": r['name_zh']} for r in cursor.fetchall()]
    conn.close()
    return {"tags": tags}

# ========== 自动更新 ==========
@app.on_event("startup")
def start_updater():
    updater.start_update_checker()

@app.get("/api/update/status")
def update_status():
    return updater.get_status()

@app.post("/api/update/install")
def update_install():
    ok, message = updater.install_and_restart()
    return {"ok": ok, "message": message}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
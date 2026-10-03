from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from typing import List, Optional
from pydantic import BaseModel
import updater


# ========== 数据模型 ==========
class Command(BaseModel):
    command_template: str
    description_en: Optional[str] = ""
    description_zh: Optional[str] = ""
    use_case: Optional[str] = ""


class ToolSummary(BaseModel):
    """列表页摘要：不含命令与关联工具，保证搜索响应小而快"""
    id: int
    name: str
    category: str
    subcategory: Optional[str] = ""
    description_en: str
    description_zh: str
    icon_emoji: Optional[str] = "🔧"
    tags: List[str] = []


class Tool(ToolSummary):
    official_url: Optional[str] = ""
    manual_page: Optional[str] = ""
    relations: List[str] = []
    commands: List[Command] = []


class SearchResult(BaseModel):
    tools: List[ToolSummary]
    total: int


# ========== FastAPI 初始化 ==========
@asynccontextmanager
async def lifespan(app: FastAPI):
    updater.start_update_checker()
    yield


app = FastAPI(title="Kali ToolKit API", version="0.2.0", lifespan=lifespan)

# 本应用只服务于本地 file:// 页面，无需携带凭据
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "tools.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ========== 查询辅助 ==========
# 一次 JOIN 拿全标签，按 tool_id 分组，避免 N+1
_TAG_SUBQUERY = """
    SELECT tt.tool_id, tg.name FROM tool_tags tt
    JOIN tags tg ON tg.id = tt.tag_id
    WHERE tt.tool_id IN ({placeholders})
"""

_RELATION_SUBQUERY = """
    SELECT r.tool_id, t.name FROM relations r
    JOIN tools t ON t.id = r.related_tool_id
    WHERE r.tool_id IN ({placeholders})
"""

_COMMAND_SUBQUERY = """
    SELECT tool_id, command_template, description_en, description_zh, use_case
    FROM commands WHERE tool_id IN ({placeholders})
    ORDER BY tool_id, id
"""


def _group_tags(cursor, tool_ids: List[int]) -> dict:
    if not tool_ids:
        return {}
    placeholders = ",".join("?" * len(tool_ids))
    cursor.execute(_TAG_SUBQUERY.format(placeholders=placeholders), tool_ids)
    result = {}
    for row in cursor.fetchall():
        result.setdefault(row["tool_id"], []).append(row["name"])
    return result


def _group_relations(cursor, tool_ids: List[int]) -> dict:
    if not tool_ids:
        return {}
    placeholders = ",".join("?" * len(tool_ids))
    cursor.execute(_RELATION_SUBQUERY.format(placeholders=placeholders), tool_ids)
    result = {}
    for row in cursor.fetchall():
        result.setdefault(row["tool_id"], []).append(row["name"])
    return result


def _group_commands(cursor, tool_ids: List[int]) -> dict:
    if not tool_ids:
        return {}
    placeholders = ",".join("?" * len(tool_ids))
    cursor.execute(_COMMAND_SUBQUERY.format(placeholders=placeholders), tool_ids)
    result = {}
    for row in cursor.fetchall():
        result.setdefault(row["tool_id"], []).append(Command(**dict(row)))
    return result


def _row_to_summary(row: sqlite3.Row, tags: dict) -> ToolSummary:
    return ToolSummary(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        subcategory=row["subcategory"] or "",
        description_en=row["description_en"],
        description_zh=row["description_zh"],
        icon_emoji=row["icon_emoji"] or "🔧",
        tags=tags.get(row["id"], []),
    )


# ========== 搜索核心 ==========
def search_tools(query: str, tag: Optional[str] = None, limit: int = 100) -> List[ToolSummary]:
    conn = get_db()
    try:
        cursor = conn.cursor()

        sql = """
            SELECT DISTINCT t.id, t.name, t.category, t.subcategory,
                   t.description_en, t.description_zh, t.icon_emoji
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

        sql += " ORDER BY t.name LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        tool_ids = [r["id"] for r in rows]
        tags = _group_tags(cursor, tool_ids)

        return [_row_to_summary(row, tags) for row in rows]
    finally:
        conn.close()


def get_tool_detail(tool_id: int) -> Optional[Tool]:
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, name, category, subcategory, description_en, description_zh,
                      official_url, manual_page, icon_emoji
               FROM tools WHERE id = ?""",
            (tool_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        tool_ids = [tool_id]
        tags = _group_tags(cursor, tool_ids)
        relations = _group_relations(cursor, tool_ids)
        commands = _group_commands(cursor, tool_ids)

        return Tool(
            id=row["id"],
            name=row["name"],
            category=row["category"],
            subcategory=row["subcategory"] or "",
            description_en=row["description_en"],
            description_zh=row["description_zh"],
            official_url=row["official_url"] or "",
            manual_page=row["manual_page"] or "",
            icon_emoji=row["icon_emoji"] or "🔧",
            tags=tags.get(tool_id, []),
            relations=relations.get(tool_id, []),
            commands=commands.get(tool_id, []),
        )
    finally:
        conn.close()


# ========== API 接口 ==========
@app.get("/")
def root():
    return {"message": "Kali ToolKit API 已启动 🚀", "version": "0.2.0"}


@app.get("/api/search", response_model=SearchResult)
def search(
    q: str = Query("", description="搜索关键词"),
    tag: Optional[str] = Query(None, description="标签过滤"),
    limit: int = Query(100, ge=1, le=500),
):
    results = search_tools(q, tag, limit)
    return SearchResult(tools=results, total=len(results))


@app.get("/api/tool/{tool_id}", response_model=Tool)
def tool_detail(tool_id: int):
    tool = get_tool_detail(tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="工具不存在")
    return tool


@app.get("/api/tags")
def get_all_tags():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name, name_zh FROM tags ORDER BY name")
        tags = [{"name": r["name"], "name_zh": r["name_zh"]} for r in cursor.fetchall()]
        return {"tags": tags}
    finally:
        conn.close()


# ========== 自动更新 ==========
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

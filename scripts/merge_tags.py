# -*- coding: utf-8 -*-
"""
把 tags_checkpoint.json 合并回 data/tools_data.json，并重建 tools.db
=====================================================================
用法（generate_tags.py 跑完后执行）：
  python scripts/merge_tags.py
"""

import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JSON = os.path.join(ROOT, 'data', 'tools_data.json')
CHECKPOINT = os.path.join(ROOT, 'scripts', 'tags_checkpoint.json')
DB_PATH = os.path.join(ROOT, 'backend', 'tools.db')


def main():
    if not os.path.exists(CHECKPOINT):
        print("❌ 找不到 tags_checkpoint.json，请先运行 generate_tags.py")
        sys.exit(1)

    checkpoint = json.load(open(CHECKPOINT, encoding='utf-8'))
    data = json.load(open(DATA_JSON, encoding='utf-8'))

    # 收集实际用到的标签，生成 tags_preset
    used = {}
    for tool in data['tools']:
        info = checkpoint.get(tool['name'])
        if not info or not info['tags']:
            tool['tags'] = []
            tool['relations'] = []
            continue
        tool['tags'] = info['tags']
        tool['relations'] = info['relations']
        for slug in info['tags']:
            used[slug] = True

    taxonomy = {}
    sys.path.insert(0, os.path.join(ROOT, 'scripts'))
    from generate_tags import TAXONOMY
    for slug, zh in TAXONOMY:
        if slug in used:
            taxonomy[slug] = zh
    data['tags_preset'] = [{"name": s, "name_zh": z} for s, z in taxonomy.items()]

    # 备份原 JSON
    backup = DATA_JSON + '.bak'
    if not os.path.exists(backup):
        with open(backup, 'w', encoding='utf-8') as f:
            json.dump(json.load(open(DATA_JSON, encoding='utf-8')), f,
                      ensure_ascii=False, indent=1)
        print(f"💾 已备份原数据到 {backup}")

    with open(DATA_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"✅ 已更新 {DATA_JSON}：{len(data['tools'])} 个工具，"
          f"{len(taxonomy)} 个标签")

    # ========== 重建 tools.db（删旧建新，避免 INSERT OR REPLACE 造成的数据残留） ==========
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print("🗑️ 已删除旧 tools.db")

    sys.path.insert(0, os.path.join(ROOT, 'backend'))
    from import_data import import_tools_from_json
    import_tools_from_json(DB_PATH, DATA_JSON)

    # ========== 验证 ==========
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tools")
    n_tools = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tags")
    n_tags = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM tool_tags")
    n_tt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM relations")
    n_rel = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM commands")
    n_cmd = cur.fetchone()[0]
    conn.close()

    print(f"\n📊 数据库验证：tools={n_tools}, tags={n_tags}, "
          f"tool_tags={n_tt}, relations={n_rel}, commands={n_cmd}")
    if n_tools != len(data['tools']) or n_cmd < 2000:
        print("⚠️ 数据量异常，请检查！")
        sys.exit(1)
    print("🎉 全部完成")


if __name__ == '__main__':
    main()

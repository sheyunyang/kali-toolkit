# -*- coding: utf-8 -*-
"""
批量生成工具标签与关联数据（DeepSeek API）
============================================
从 data/tools_data.json 读取 781 个工具，分批调用 DeepSeek 生成：
  - tags：从预定义标签体系（taxonomy）中挑选 2-4 个
  - relations：2-4 个常搭配使用的工具名（必须在完整工具名列表中）

特性：
  - 断点续传：每批完成即写入 scripts/tags_checkpoint.json，中断后重跑自动跳过
  - 输出校验：tags 必须在 taxonomy 内，relations 必须是存在的工具名
  - 失败自动重试（最多 3 次，指数退避）

环境变量：
  DEEPSEEK_API_KEY   必填
  DEEPSEEK_BASE_URL  默认 https://api.deepseek.com（兼容 OpenAI 格式的端点均可）
  DEEPSEEK_MODEL     默认 deepseek-chat

用法：
  python scripts/generate_tags.py
"""

import json
import os
import sys
import time
import urllib.request

# ========== 配置 ==========
BASE_URL = os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com').rstrip('/')
API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
MODEL = os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
BATCH_SIZE = 20
MAX_RETRY = 3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JSON = os.path.join(ROOT, 'data', 'tools_data.json')
CHECKPOINT = os.path.join(ROOT, 'scripts', 'tags_checkpoint.json')

# ========== 标签体系（slug, 中文名） ==========
TAXONOMY = [
    ("info-gathering", "信息收集"),
    ("port-scan", "端口扫描"),
    ("network-scan", "网络扫描"),
    ("dns", "DNS"),
    ("subdomain", "子域名"),
    ("osint", "开源情报"),
    ("social-eng", "社会工程"),
    ("phishing", "钓鱼"),
    ("vuln-scan", "漏洞扫描"),
    ("web-scan", "Web扫描"),
    ("web-vuln", "Web漏洞"),
    ("sqli", "SQL注入"),
    ("xss", "XSS"),
    ("api-testing", "API测试"),
    ("fuzzing", "模糊测试"),
    ("password", "密码破解"),
    ("brute-force", "暴力破解"),
    ("wordlist", "字典生成"),
    ("wireless", "无线安全"),
    ("bluetooth", "蓝牙安全"),
    ("mitm", "中间人攻击"),
    ("sniffing", "流量嗅探"),
    ("pcap-analysis", "数据包分析"),
    ("exploit", "漏洞利用"),
    ("pentest-framework", "渗透框架"),
    ("post-exploit", "后渗透"),
    ("privesc", "权限提升"),
    ("lateral-movement", "横向移动"),
    ("tunnel", "隧道代理"),
    ("c2", "C2框架"),
    ("evasion", "免杀绕过"),
    ("reverse", "逆向工程"),
    ("disasm-debug", "反汇编调试"),
    ("binary-analysis", "二进制分析"),
    ("firmware", "固件分析"),
    ("forensics", "数字取证"),
    ("memory-forensics", "内存取证"),
    ("stego", "隐写"),
    ("crypto", "密码学"),
    ("hash", "哈希破解"),
    ("database", "数据库"),
    ("code-audit", "代码审计"),
    ("config-audit", "配置审计"),
    ("sandbox", "沙箱分析"),
    ("vuln-db", "漏洞库"),
    ("reporting", "报告生成"),
    ("recovery", "数据恢复"),
    ("voip", "VoIP"),
    ("mobile", "移动安全"),
    ("cloud", "云安全"),
]
TAXONOMY_SLUGS = {slug for slug, _ in TAXONOMY}


def chat(messages, json_mode=True):
    """调用 DeepSeek 对话接口，返回 content 字符串"""
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 4000,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        BASE_URL + "/chat/completions",
        data=json.dumps(payload).encode('utf-8'),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode('utf-8'))
    return data["choices"][0]["message"]["content"]


def build_prompt(batch, all_names):
    taxonomy_desc = "、".join(f"{slug}({zh})" for slug, zh in TAXONOMY)
    tools_desc = []
    for t in batch:
        cmd_hint = ""
        if t.get('commands'):
            c = t['commands'][0]
            cmd_hint = f"；示例命令: {c.get('command_template', '')[:80]}"
        tools_desc.append(
            f"- {t['name']} [{t.get('category', '')}/{t.get('subcategory') or '通用'}] "
            f"{t.get('description_zh', '')[:150]}{cmd_hint}"
        )
    names_line = ", ".join(all_names)
    return f"""你是 Kali Linux 工具专家。为下面每个工具生成标签和常搭配工具。

可用标签体系（只能从中选 2-4 个，按相关度排序）：
{taxonomy_desc}

可选的关联工具名（relations 必须从这个列表中选 2-4 个，选工作流程上真正先后搭配使用的；没有合适搭档的给 1-2 个同类替代工具）：
{names_line}

待处理工具：
{chr(10).join(tools_desc)}

严格输出 JSON（不要输出其他内容），格式：
{{"results":[{{"name":"工具名","tags":["slug1","slug2"],"relations":["工具名1","工具名2"]}}]}}
results 数组长度必须等于待处理工具数量，name 必须逐字匹配待处理工具名。"""


def parse_and_validate(content, batch, valid_names):
    """解析模型输出并校验，返回 {tool_name: {"tags": [...], "relations": [...]}}"""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip('`')
        if content.startswith('json'):
            content = content[4:]
    data = json.loads(content)
    results = data.get("results", [])
    batch_names = {t['name'] for t in batch}
    out = {}
    for item in results:
        name = item.get("name", "")
        if name not in batch_names:
            # 容错：尝试忽略大小写匹配
            match = next((n for n in batch_names if n.lower() == name.lower()), None)
            if not match:
                continue
            name = match
        tags = [t for t in item.get("tags", []) if t in TAXONOMY_SLUGS]
        relations = [r for r in item.get("relations", [])
                     if r in valid_names and r != name]
        # 去重保序
        tags = list(dict.fromkeys(tags))[:4]
        relations = list(dict.fromkeys(relations))[:4]
        if tags:
            out[name] = {"tags": tags, "relations": relations}
    return out


def main():
    if not API_KEY:
        print("❌ 请先设置环境变量 DEEPSEEK_API_KEY")
        sys.exit(1)

    data = json.load(open(DATA_JSON, encoding='utf-8'))
    tools = data['tools']
    all_names = [t['name'] for t in tools]
    valid_names = set(all_names)

    checkpoint = {}
    if os.path.exists(CHECKPOINT):
        checkpoint = json.load(open(CHECKPOINT, encoding='utf-8'))
        print(f"📂 载入断点：已完成 {len(checkpoint)}/{len(tools)} 个工具")

    batches = [tools[i:i + BATCH_SIZE] for i in range(0, len(tools), BATCH_SIZE)]
    done_before = len(checkpoint)

    for bi, batch in enumerate(batches, 1):
        if all(t['name'] in checkpoint for t in batch):
            continue
        prompt = build_prompt(batch, all_names)
        messages = [{"role": "user", "content": prompt}]

        for attempt in range(1, MAX_RETRY + 1):
            try:
                content = chat(messages)
                results = parse_and_validate(content, batch, valid_names)
                missing = [t['name'] for t in batch if t['name'] not in results]
                if len(missing) > len(batch) * 0.3:
                    raise ValueError(f"缺失过多: {missing[:5]}...")
                checkpoint.update(results)
                # 缺失的用空结果占位，避免无限重试
                for m in missing:
                    checkpoint[m] = {"tags": [], "relations": []}
                with open(CHECKPOINT, 'w', encoding='utf-8') as f:
                    json.dump(checkpoint, f, ensure_ascii=False, indent=1)
                print(f"✅ 批次 {bi}/{len(batches)} 完成（+{len(results)}，缺失 {len(missing)}）"
                      f" 累计 {len(checkpoint)}/{len(tools)}")
                break
            except Exception as e:
                print(f"⚠️ 批次 {bi} 第 {attempt} 次尝试失败: {e}")
                if attempt == MAX_RETRY:
                    print("⏭️ 跳过该批次，重跑本脚本可续传")
                    for t in batch:
                        checkpoint.setdefault(t['name'], {"tags": [], "relations": []})
                    with open(CHECKPOINT, 'w', encoding='utf-8') as f:
                        json.dump(checkpoint, f, ensure_ascii=False, indent=1)
                else:
                    time.sleep(2 ** attempt * 5)

        # 温和限速，避免触发 TPM 限制
        time.sleep(1)

    n_tags = sum(1 for v in checkpoint.values() if v['tags'])
    n_rel = sum(1 for v in checkpoint.values() if v['relations'])
    print(f"\n🎉 生成完成：{len(checkpoint)}/{len(tools)} 个工具，"
          f"{n_tags} 个有标签，{n_rel} 个有关联")
    print(f"📁 断点文件：{CHECKPOINT}")


if __name__ == '__main__':
    main()

"""
从 781 个工具清单，批量爬取每个工具的 Kali 官网详情
支持断点续传
"""
import json
import re
import time
import os
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

SITEMAP_FILE = "kali_sitemap.xml"
OUTPUT_FILE = "all_tools_raw.json"
DELAY = 1.0  # 每个工具间隔 1 秒


def extract_tool_names():
    """从 sitemap 提取工具名"""
    text = open(SITEMAP_FILE, encoding='utf-8').read()
    tools = re.findall(r'<loc>https://www\.kali\.org/tools/([^/]+)/</loc>', text)
    print(f"📋 从 sitemap 提取到 {len(tools)} 个工具")
    return sorted(set(tools))


def extract_clean_description(soup, tool_name):
    """从 Kali 官网页面提取干净描述"""
    h1 = soup.find('h1')
    if not h1:
        return ""
    
    for p in h1.find_all_next('p', limit=10):
        text = p.get_text(strip=True)
        if not text or len(text) < 20 or len(text) > 600:
            continue
        # 过滤示例输出
        bad_keywords = ['root@', '$ ', 'Usage:', 'Starting ', 'NSE:',
                        'Discovered', '192.168.', 'localhost',
                        'Copyright', 'http://nmap', 'Installed size']
        if any(kw in text for kw in bad_keywords):
            continue
        if text.lower() in ['description', 'usage']:
            continue
        return text
    return ""


def extract_commands(soup):
    """提取命令示例"""
    commands = []
    for pre in soup.find_all('pre'):
        text = pre.get_text()
        for line in text.split('\n'):
            line = line.strip()
            match = re.search(r'root@kali[^#]*#\s*(.+)', line)
            if match:
                cmd = match.group(1).strip()
                if cmd and len(cmd) < 300 and not cmd.startswith('exit'):
                    commands.append(cmd)
    return list(dict.fromkeys(commands))[:15]


def scrape_tool(tool_name):
    """爬取单个工具"""
    url = f"https://www.kali.org/tools/{tool_name}/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, 'html.parser')
        return {
            "name": tool_name,
            "description_en": extract_clean_description(soup, tool_name),
            "install_cmd": f"sudo apt install {tool_name}",
            "commands": extract_commands(soup),
            "official_url": url
        }
    except Exception as e:
        return None


def main():
    # 1. 提取工具名
    all_tools = extract_tool_names()
    
    # 2. 断点续传
    results = []
    done_names = set()
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            results = json.load(f)
        done_names = {r['name'] for r in results}
        print(f"♻️  已有 {len(done_names)} 个，继续\n")
    
    # 3. 批量爬取
    total = len(all_tools)
    for i, tool in enumerate(all_tools):
        if tool in done_names:
            continue
        
        print(f"[{i+1}/{total}] {tool}", end=" ", flush=True)
        r = scrape_tool(tool)
        if r:
            results.append(r)
            print(f"✅ ({len(r['commands'])} 命令)")
        else:
            print(f"❌")
        
        # 每 10 个保存
        if len(results) % 10 == 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"    💾 已保存 ({len(results)} 个)")
        
        time.sleep(DELAY)
    
    # 最终保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 完成！共 {len(results)} 个工具 → {OUTPUT_FILE}")


if __name__ == '__main__':
    main()
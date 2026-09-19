import requests
from bs4 import BeautifulSoup
import time
import json
import os
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ========== 100 个核心工具清单 ==========
TOOL_NAMES = [
    # 信息收集
    "nmap", "netdiscover", "arp-scan", "dnsrecon", "whois", "theharvester",
    "dnsenum", "fierce", "recon-ng", "maltego", "sslscan", "sslyze",
    "wafw00f", "whatweb", "dmitry", "nbtscan", "smbmap", "enum4linux",
    # 漏洞分析
    "sqlmap", "nikto", "wpscan", "nuclei", "gvm", "skipfish", "wapiti",
    "exploitdb", "lynis", "gobuster", "ffuf", "dirb", "dirbuster",
    "wfuzz", "commix", "xsser", "joomscan",
    # 密码攻击
    "hydra", "john", "hashcat", "crunch", "cewl", "medusa", "ncrack",
    "ophcrack", "responder", "patator", "hash-identifier",
    # 无线攻击
    "aircrack-ng", "reaver", "wifite", "kismet", "bully",
    "bettercap", "hcxdumptool", "hcxtools",
    # 维持访问
    "metasploit-framework", "veil", "shellter", "powershell-empire",
    "sliver", "chisel",
    # 权限提升
    "peass-ng", "pspy", "linux-exploit-suggester", "beef-xss",
    "powersploit", "unix-privesc-check", "seatbelt",
    # 流量分析
    "wireshark", "tcpdump", "ngrep", "driftnet", "ettercap", "dsniff",
    "urlsnarf", "mitmproxy", "net-creds",
    # 逆向工程
    "ghidra", "radare2", "apktool", "dex2jar", "jd-gui",
]


def extract_clean_description(soup, tool_name):
    """提取干净的工具描述"""
    h1 = soup.find('h1')
    if not h1:
        return ""
    
    for p in h1.find_all_next('p', limit=10):
        text = p.get_text(strip=True)
        if not text or len(text) < 20 or len(text) > 600:
            continue
        bad_keywords = ['root@', '$ ', 'Usage:', 'Starting ', 'NSE:',
                        'Discovered', '192.168.', 'localhost', 'nmap -',
                        'Copyright', 'http://nmap']
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
    return list(dict.fromkeys(commands))[:10]


def scrape_tool(tool_name):
    """抓取单个工具"""
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
        print(f"  ❌ {e}")
        return None


if __name__ == '__main__':
    output_file = 'kali_tools_batch.json'

    results = []
    done_names = set()
    if os.path.exists(output_file):
        with open(output_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        done_names = {r['name'] for r in results}
        print(f"📂 已有 {len(done_names)} 个，继续抓取\n")

    total = len(TOOL_NAMES)
    for i, tool in enumerate(TOOL_NAMES):
        if tool in done_names:
            print(f"[{i+1}/{total}] {tool} ⏭️  已存在")
            continue

        print(f"[{i+1}/{total}] {tool}", end=" ")
        r = scrape_tool(tool)
        if r:
            results.append(r)
            desc_preview = r['description_en'][:50] if r['description_en'] else "(无描述)"
            print(f"✅ {desc_preview}...")
        else:
            print(f"❌")

        # 每 10 个保存一次
        if len(results) % 10 == 0:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

        time.sleep(1)

    # 最终保存
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！共 {len(results)} 个工具 → {output_file}")
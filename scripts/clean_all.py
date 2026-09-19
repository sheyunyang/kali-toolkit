"""
清洗 781 个工具数据：
1. 按工具名分配分类
2. 修复描述粘黏
3. 去重、格式化
"""
import json
import re

INPUT_FILE = "all_tools_raw.json"
OUTPUT_FILE = "all_tools_cleaned.json"

# ========== 关键词 → 分类映射 ==========
CATEGORY_KEYWORDS = {
    # 信息收集
    "信息收集": [
        "nmap", "netdiscover", "arp-scan", "dnsrecon", "whois", "theharvester",
        "dnsenum", "fierce", "recon-ng", "maltego", "sslscan", "sslyze",
        "wafw00f", "whatweb", "dmitry", "nbtscan", "smbmap", "enum4linux",
        "dnsutils", "masscan", "zmap", "fping", "hping3", "amass", "subfinder",
        "assetfinder", "httpx", "gobuster", "ffuf", "dnschef", "dnsmap",
        "dnswalk", "dnsrecon", "dnsutils", "host", "dig", "nslookup",
    ],
    # 漏洞分析
    "漏洞分析": [
        "sqlmap", "nikto", "wpscan", "nuclei", "gvm", "skipfish", "wapiti",
        "exploitdb", "lynis", "dirb", "dirbuster", "wfuzz", "commix",
        "xsser", "joomscan", "w3af", "openvas", "zap", "zaproxy",
        "searchsploit", "wpscan", "droopescan", "joomscan", "cmseek",
    ],
    # 密码攻击
    "密码攻击": [
        "hydra", "john", "hashcat", "crunch", "cewl", "medusa", "ncrack",
        "ophcrack", "responder", "patator", "hash-identifier", "mimikatz",
        "crowbar", "samdump2", "fcrackzip", "hashid", "hash-identifier",
        "johnny", "ophcrack", "rainbowcrack", "rcracki",
    ],
    # 无线攻击
    "无线攻击": [
        "aircrack", "reaver", "wifite", "kismet", "bully", "bettercap",
        "hcxtools", "hcxdumptool", "pixiewps", "wash", "airgraph",
        "airbase", "airdecap", "airdecloak", "aireplay", "airmon",
        "airodump", "airolib", "airtun", "eapmd5pass", "fern",
    ],
    # 维持访问
    "维持访问": [
        "metasploit", "msfvenom", "veil", "shellter", "empire", "sliver",
        "chisel", "cobalt", "covenant", "pupy", "merlin", "hoaxshell",
        "villain", "maccdc", "stowaway", "ligolo", "frp", "ngrok",
    ],
    # 权限提升
    "权限提升": [
        "peass", "linpeas", "winpeas", "pspy", "linux-exploit-suggester",
        "beef", "powersploit", "unix-privesc", "seatbelt", "gtfobins",
        "linuxprivchecker", "windows-privesc", "powerup", "sherlock",
    ],
    # 流量分析
    "流量分析": [
        "wireshark", "tcpdump", "ngrep", "driftnet", "ettercap", "dsniff",
        "urlsnarf", "mitmproxy", "net-creds", "tshark", "dumpcap",
        "responder", "netsniff", "p0f", "sslstrip", "sslsplit",
    ],
    # 逆向工程
    "逆向工程": [
        "ghidra", "radare2", "apktool", "dex2jar", "jd-gui", "gdb",
        "ollydbg", "ida", "binaryninja", "cutter", "rizin", "angr",
        "frida", "objection", "jadx", "bytecode", "recaf", "jbe",
    ],
    # 社会工程
    "社会工程": [
        "setoolkit", "gophish", "evilginx", "king-phisher", "socialfish",
        "shellphish", "blackeye", "hiddeneye", "zphisher",
    ],
}


def guess_category(name):
    """根据工具名猜分类"""
    name_lower = name.lower()
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return cat
    return "其他"


def clean_description(desc, tool_name):
    """清洗描述"""
    if not desc:
        return ""
    
    # 去掉工具名粘黏
    desc = re.sub(rf'\b{re.escape(tool_name)}\b', '', desc, count=1, flags=re.IGNORECASE)
    
    # 去掉常见污染后缀
    bad_patterns = [
        r'Compare yesterday.+',
        r'Read in a list.+',
        r'Scan a domain.+',
        r'Scan the local network.+',
        r'Do not a reverse lookup.+',
        r'Run a default scan.+',
        r'Search for results.+',
        r'Specify the wordlist.+',
        r'Installed size:.+',
        r'How to install:.+',
    ]
    for pattern in bad_patterns:
        desc = re.sub(pattern, '', desc, flags=re.IGNORECASE)
    
    # 去多余空格
    desc = re.sub(r'\s+', ' ', desc).strip()
    
    # 首字母大写
    if desc:
        desc = desc[0].upper() + desc[1:]
    
    return desc


def main():
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    
    print(f"📖 读取 {len(raw)} 个工具")
    
    cleaned = []
    cat_count = {}
    
    for i, tool in enumerate(raw):
        name = tool['name']
        category = guess_category(name)
        cat_count[category] = cat_count.get(category, 0) + 1
        
        # 清洗描述
        desc = clean_description(tool.get('description_en', ''), name)
        
        # 补全命令模板
        commands = []
        for cmd in tool.get('commands', []):
            commands.append({
                "command_template": cmd,
                "description_en": "",
                "description_zh": "",
                "use_case": ""
            })
        
        cleaned.append({
            "name": name,
            "category": category,
            "subcategory": "",
            "description_en": desc,
            "description_zh": "",
            "official_url": tool.get('official_url', ''),
            "manual_page": f"man {name}",
            "icon_emoji": "🔧",
            "commands": commands,
            "tags": [],
            "relations": []
        })
        
        if (i + 1) % 100 == 0:
            print(f"  已处理 {i+1}/{len(raw)}")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({"tools": cleaned, "tags_preset": []}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 清洗完成！{len(cleaned)} 个工具 → {OUTPUT_FILE}")
    print(f"\n分类统计：")
    for cat, count in sorted(cat_count.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} 个")


if __name__ == '__main__':
    main()
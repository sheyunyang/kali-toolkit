"""
数据清洗：
1. 修正描述（去掉尾部示例、粘黏、多余空格）
2. 按工具名分配分类和子分类
3. 补全默认命令说明和标签
"""
import json
import re
import os

# ========== 工具分类映射 ==========
CATEGORY_MAP = {
    "nmap": ("信息收集", "端口扫描"),
    "netdiscover": ("信息收集", "主机发现"),
    "arp-scan": ("信息收集", "主机发现"),
    "dnsrecon": ("信息收集", "DNS侦察"),
    "whois": ("信息收集", "域名查询"),
    "theharvester": ("信息收集", "邮箱收集"),
    "dnsenum": ("信息收集", "DNS侦察"),
    "fierce": ("信息收集", "DNS侦察"),
    "recon-ng": ("信息收集", "综合侦察"),
    "maltego": ("信息收集", "情报分析"),
    "sslscan": ("信息收集", "SSL扫描"),
    "sslyze": ("信息收集", "SSL扫描"),
    "wafw00f": ("信息收集", "WAF识别"),
    "whatweb": ("信息收集", "指纹识别"),
    "dmitry": ("信息收集", "综合侦察"),
    "nbtscan": ("信息收集", "NetBIOS扫描"),
    "smbmap": ("信息收集", "SMB枚举"),
    "enum4linux": ("信息收集", "SMB枚举"),
    
    "sqlmap": ("漏洞分析", "SQL注入"),
    "nikto": ("漏洞分析", "Web扫描"),
    "wpscan": ("漏洞分析", "CMS扫描"),
    "nuclei": ("漏洞分析", "模板扫描"),
    "gvm": ("漏洞分析", "漏洞管理"),
    "skipfish": ("漏洞分析", "Web扫描"),
    "wapiti": ("漏洞分析", "Web扫描"),
    "exploitdb": ("漏洞分析", "漏洞库"),
    "lynis": ("漏洞分析", "系统审计"),
    "gobuster": ("漏洞分析", "目录爆破"),
    "ffuf": ("漏洞分析", "模糊测试"),
    "dirb": ("漏洞分析", "目录爆破"),
    "dirbuster": ("漏洞分析", "目录爆破"),
    "wfuzz": ("漏洞分析", "模糊测试"),
    "commix": ("漏洞分析", "命令注入"),
    "xsser": ("漏洞分析", "XSS检测"),
    "joomscan": ("漏洞分析", "CMS扫描"),
    
    "hydra": ("密码攻击", "暴力破解"),
    "john": ("密码攻击", "密码破解"),
    "hashcat": ("密码攻击", "哈希破解"),
    "crunch": ("密码攻击", "字典生成"),
    "cewl": ("密码攻击", "字典生成"),
    "medusa": ("密码攻击", "暴力破解"),
    "ncrack": ("密码攻击", "暴力破解"),
    "ophcrack": ("密码攻击", "哈希破解"),
    "responder": ("密码攻击", "中间人"),
    "patator": ("密码攻击", "暴力破解"),
    "hash-identifier": ("密码攻击", "哈希识别"),
    
    "aircrack-ng": ("无线攻击", "WEP/WPA破解"),
    "reaver": ("无线攻击", "WPS破解"),
    "wifite": ("无线攻击", "自动化破解"),
    "kismet": ("无线攻击", "无线侦测"),
    "bully": ("无线攻击", "WPS破解"),
    "bettercap": ("无线攻击", "中间人"),
    "hcxdumptool": ("无线攻击", "WPA抓包"),
    "hcxtools": ("无线攻击", "WPA分析"),
    
    "metasploit-framework": ("维持访问", "漏洞利用框架"),
    "veil": ("维持访问", "Payload生成"),
    "shellter": ("维持访问", "Payload注入"),
    "powershell-empire": ("维持访问", "C2框架"),
    "sliver": ("维持访问", "C2框架"),
    "chisel": ("维持访问", "隧道代理"),
    
    "peass-ng": ("权限提升", "自动枚举"),
    "pspy": ("权限提升", "进程监控"),
    "linux-exploit-suggester": ("权限提升", "漏洞建议"),
    "beef-xss": ("权限提升", "XSS框架"),
    "powersploit": ("权限提升", "PowerShell工具集"),
    "unix-privesc-check": ("权限提升", "提权检查"),
    "seatbelt": ("权限提升", "安全审计"),
    
    "wireshark": ("流量分析", "协议分析"),
    "tcpdump": ("流量分析", "抓包"),
    "ngrep": ("流量分析", "流量匹配"),
    "driftnet": ("流量分析", "图片嗅探"),
    "ettercap": ("流量分析", "中间人"),
    "dsniff": ("流量分析", "密码嗅探"),
    "urlsnarf": ("流量分析", "URL嗅探"),
    "mitmproxy": ("流量分析", "中间人代理"),
    "net-creds": ("流量分析", "凭证嗅探"),
    
    "ghidra": ("逆向工程", "反编译"),
    "radare2": ("逆向工程", "反汇编"),
    "apktool": ("逆向工程", "APK分析"),
    "dex2jar": ("逆向工程", "APK分析"),
    "jd-gui": ("逆向工程", "Java反编译"),
}


def clean_description(desc, tool_name):
    """清洗描述"""
    if not desc:
        return ""
    
    # 1. 去掉工具名粘黏（如 "Web server security scannerNikto is..."）
    desc = re.sub(rf'\b{tool_name}\b', '', desc, count=1, flags=re.IGNORECASE)
    
    # 2. 去掉尾部示例（"Compare yesterday's port scan" 这类）
    bad_suffixes = [
        r'Compare yesterday.+',
        r'Read in a list.+',
        r'Scan a domain.+',
        r'Scan the local network.+',
        r'Do not a reverse lookup.+',
        r'Run a default scan.+',
        r'Search for results.+',
        r'Scan .+ port scan.+',
        r'Scan a target.+',
        r'Specify the wordlist.+',
    ]
    for pattern in bad_suffixes:
        desc = re.sub(pattern, '', desc, flags=re.IGNORECASE)
    
    # 3. 去多余空格
    desc = re.sub(r'\s+', ' ', desc).strip()
    
    # 4. 首字母大写
    if desc:
        desc = desc[0].upper() + desc[1:]
    
    return desc


def main():
    input_file = 'kali_tools_batch.json'
    output_file = 'kali_tools_cleaned.json'
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"📖 读取到 {len(data)} 个工具")
    
    cleaned = []
    for tool in data:
        name = tool['name']
        
        # 分类
        cat_info = CATEGORY_MAP.get(name, ("其他", ""))
        category, subcategory = cat_info
        
        # 清洗描述
        desc = clean_description(tool.get('description_en', ''), name)
        
        # 补全命令的默认说明
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
            "subcategory": subcategory,
            "description_en": desc,
            "description_zh": "",  # 待翻译
            "official_url": tool.get('official_url', ''),
            "manual_page": f"man {name}",
            "icon_emoji": "🔧",
            "commands": commands,
            "tags": [],
            "relations": []
        })
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({"tools": cleaned, "tags_preset": []}, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 清洗完成！{len(cleaned)} 个工具 → {output_file}")


if __name__ == '__main__':
    main()
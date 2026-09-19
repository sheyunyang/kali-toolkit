"""
数据优化脚本：
1. 修复描述粘黏（工具名重复、标题正文粘连）
2. 替换"命令示例型"描述为标准介绍
3. 补全空描述
"""
import json
import re

INPUT_FILE = 'kali_tools_translated.json'
OUTPUT_FILE = 'kali_tools_final.json'

# ========== 预设：为工具定制的"标准"中文描述 ==========
# 这些工具的官网描述要么为空，要么是命令示例，我们手工填最好的描述
MANUAL_DESCRIPTIONS = {
    "nmap": "网络探测和安全审计工具，用于主机发现、端口扫描、服务识别、操作系统检测等，是渗透测试中最常用的信息收集工具。",
    "hydra": "支持多种协议（SSH、FTP、HTTP、RDP 等）的并行登录密码破解工具，可用于对目标服务进行暴力破解测试。",
    "aircrack-ng": "完整的 802.11 WEP/WPA/WPA2 无线网络审计工具套件，支持抓包、注入、密码破解等完整无线渗透流程。",
    "arp-scan": "使用 ARP 请求扫描本地网络的工具，用于快速发现局域网内的存活主机和 MAC 地址。",
    "dnsrecon": "DNS 枚举和侦察工具，支持区域传输、子域名爆破、DNS 缓存探测等多种 DNS 侦察技术。",
    "fierce": "DNS 侦察工具，用于发现目标域名的子域名、IP 段和非连续 IP 空间。",
    "recon-ng": "模块化的 Web 侦察框架，类似 Metasploit 的交互方式，集成大量开源情报（OSINT）模块。",
    "wpscan": "WordPress 安全扫描器，用于枚举用户、插件、主题并检测已知漏洞。",
    "theharvester": "开源情报（OSINT）收集工具，用于从公开来源收集邮箱、子域名、主机、员工姓名等信息。",
    "dnsenum": "多线程 DNS 枚举工具，用于收集 DNS 记录、子域名、区域传输信息。",
    "sslyze": "快速 SSL/TLS 配置扫描器，用于检测服务器的 SSL/TLS 配置弱点和漏洞。",
    "smbmap": "SMB 共享枚举工具，用于快速列出目标主机上的共享目录和权限。",
    "lynis": "Unix/Linux 系统安全审计工具，用于检测系统配置弱点、缺失补丁和合规性问题。",
    "exploitdb": "漏洞利用数据库（Exploit Database）的命令行搜索工具，可通过 searchsploit 命令查询本地漏洞库。",
    "gobuster": "高性能目录/DNS/虚拟主机爆破工具，用 Go 编写，速度快。",
    "ffuf": "用 Go 编写的快速 Web 模糊测试工具，支持目录发现、虚拟主机发现和参数模糊测试。",
    "joomscan": "OWASP Joomla 漏洞扫描器，用于检测 Joomla CMS 的已知漏洞和配置问题。",
    "xsser": "自动化 XSS 漏洞检测和利用框架，支持多种注入技术和绕过方式。",
    "gvm": "Greenbone 漏洞管理器（原 OpenVAS），模块化的安全审计工具，用于远程漏洞扫描和管理。",
    "wifite": "自动化无线攻击工具，自动化执行 WPS/WPA 破解流程。",
    "bully": "WPS 暴力破解工具，用 C 语言编写，兼容 reaver 的功能。",
    "bettercap": "强大的 MITM 框架，用于网络攻击和监控，支持 WiFi、BLE、以太网等多种协议。",
    "hcxtools": "无线抓包转换工具集，将捕获的 WLAN 流量转换为 hashcat 或 John the Ripper 可用的格式。",
    "powershell-empire": "PowerShell 后渗透 C2 框架，用于在 Windows 环境中进行横向移动和维持访问。",
    "medusa": "快速、并行的网络登录暴力破解工具，支持多种协议。",
    "peass-ng": "特权提升工具集，包含 LinPEAS 和 WinPEAS，用于自动化枚举 Linux/Windows 的提权路径。",
    "pspy": "无需 root 权限即可监控 Linux 进程的命令行工具，常用于 CTF 和提权枚举。",
}


def fix_sticky_description(desc, tool_name):
    """修复描述粘黏问题"""
    if not desc:
        return desc
    
    # 修复工具名重复：如 "主动/被动网络地址扫描器，使用ARP请求。Netdiscover是一款..."
    # 模式：短描述 + 工具名 + "是/是一款"
    pattern = rf'^(.+?)({re.escape(tool_name)}|{re.escape(tool_name.capitalize())}|{re.escape(tool_name.upper())})[\s]*[是为一款]'
    match = re.match(pattern, desc)
    if match:
        # 如果前半部分太短（少于 30 字），说明只是标题，用后半部分
        if len(match.group(1)) < 30:
            desc = desc[len(match.group(1)):].strip()
    
    # 修复中英混杂：如 "智能客户端此包为WHOIS..."
    # 找出连续的中文 + 突然出现"此包"/"这是一个"等，加句号
    desc = re.sub(r'(客户端|工具|扫描器|框架|程序|软件)(此包|这个包|这是一个|它是一个)', r'\1。\2', desc)
    desc = re.sub(r'([a-zA-Z0-9])(此包|这个包)', r'\1。\2', desc)
    
    # 修复英文单词后直接跟中文，加空格
    desc = re.sub(r'([a-zA-Z])([\u4e00-\u9fa5])', r'\1 \2', desc)
    desc = re.sub(r'([\u4e00-\u9fa5])([a-zA-Z])', r'\1 \2', desc)
    
    # 去掉多余空格
    desc = re.sub(r'\s+', ' ', desc).strip()
    
    return desc


def main():
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tools = data['tools']
    print(f"📖 读取 {len(tools)} 个工具\n")
    
    fixed_count = 0
    replaced_count = 0
    filled_count = 0
    
    for tool in tools:
        name = tool['name']
        old_desc = tool.get('description_zh', '').strip()
        
        # 优先级 1：有手工预设的，直接用
        if name in MANUAL_DESCRIPTIONS:
            tool['description_zh'] = MANUAL_DESCRIPTIONS[name]
            replaced_count += 1
            print(f"✅ [{name}] 使用预设描述")
            continue
        
        # 优先级 2：修复粘黏
        if old_desc:
            new_desc = fix_sticky_description(old_desc, name)
            if new_desc != old_desc:
                tool['description_zh'] = new_desc
                fixed_count += 1
                print(f"🔧 [{name}] 修复粘黏")
                print(f"    旧: {old_desc[:60]}...")
                print(f"    新: {new_desc[:60]}...")
        else:
            # 优先级 3：空描述，暂不处理
            filled_count += 1
            print(f"⚠️  [{name}] 描述为空，待补")
    
    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ 优化完成！")
    print(f"   使用预设描述：{replaced_count} 个")
    print(f"   修复粘黏：{fixed_count} 个")
    print(f"   仍为空描述：{filled_count} 个")
    print(f"   输出：{OUTPUT_FILE}")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
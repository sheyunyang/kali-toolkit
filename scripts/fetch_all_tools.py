"""
从 Kali apt 仓库获取完整工具清单（调试增强版）
"""
import gzip
import json
import sys
import requests

# 多个镜像，按顺序尝试
MIRRORS = [
    "https://mirrors.ustc.edu.cn/kali/dists/kali-rolling/main/binary-amd64/Packages.gz",
    "https://mirror.iscas.ac.cn/kali/dists/kali-rolling/main/binary-amd64/Packages.gz",
    "https://mirrors.tuna.tsinghua.edu.cn/kali/dists/kali-rolling/main/binary-amd64/Packages.gz",
    "http://http.kali.org/kali/dists/kali-rolling/main/binary-amd64/Packages.gz",
]

OUTPUT_FILE = "all_kali_tools.json"


def download_packages():
    """尝试多个镜像，下载包列表"""
    for url in MIRRORS:
        print(f"🌐 尝试下载: {url}")
        try:
            res = requests.get(url, timeout=60, stream=True)
            print(f"   HTTP 状态码: {res.status_code}")
            if res.status_code == 200:
                content = res.content
                print(f"   ✅ 下载成功，大小: {len(content) / 1024 / 1024:.2f} MB")
                return content
            else:
                print(f"   ❌ 状态码异常，换下一个镜像")
        except Exception as e:
            print(f"   ❌ 异常: {e}")
    return None


def parse_packages(content):
    """解析 Packages 文件"""
    print(f"\n📦 解压中...")
    try:
        raw = gzip.decompress(content)
        text = raw.decode('utf-8', errors='ignore')
        print(f"   ✅ 解压成功，共 {len(text)} 字符")
    except Exception as e:
        print(f"   ❌ 解压失败: {e}")
        return []
    
    packages = []
    current = {}
    for line in text.split('\n'):
        if not line.strip():
            if current:
                packages.append(current)
                current = {}
            continue
        if ':' in line and not line.startswith(' '):
            key, value = line.split(':', 1)
            current[key.strip()] = value.strip()
    
    if current:
        packages.append(current)
    
    print(f"   ✅ 解析出 {len(packages)} 个包")
    return packages


def filter_tools(packages):
    """过滤出 Kali 工具"""
    tools = []
    for pkg in packages:
        section = pkg.get('Section', '')
        # 只要 kali-tools-* 分类的
        if section.startswith('kali-tools') or section.startswith('kali-'):
            name = pkg.get('Package', '')
            desc = pkg.get('Description', '').split('\n')[0]
            if name:
                tools.append({
                    "name": name,
                    "description_en": desc,
                    "section": section,
                    "homepage": pkg.get('Homepage', ''),
                })
    
    # 去重
    seen = set()
    unique = []
    for t in tools:
        if t['name'] not in seen:
            seen.add(t['name'])
            unique.append(t)
    
    return unique


def main():
    print("=" * 60)
    print("Kali 工具清单抓取工具")
    print("=" * 60 + "\n")
    
    # 1. 下载
    content = download_packages()
    if not content:
        print("\n❌ 所有镜像都失败了，检查网络连接")
        sys.exit(1)
    
    # 2. 解析
    packages = parse_packages(content)
    if not packages:
        print("\n❌ 解析失败")
        sys.exit(1)
    
    # 3. 过滤工具
    print(f"\n🔍 过滤 Kali 工具...")
    tools = filter_tools(packages)
    print(f"   ✅ 过滤出 {len(tools)} 个 Kali 工具")
    
    # 4. 按分类统计
    from collections import Counter
    sections = Counter(t['section'] for t in tools)
    print("\n📊 分类统计：")
    for sec, count in sections.most_common(20):
        print(f"   {sec}: {count} 个")
    
    # 5. 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump({"tools": tools, "total": len(tools)}, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 已保存到: {OUTPUT_FILE}")
    print(f"📁 完整路径: {__import__('os').path.abspath(OUTPUT_FILE)}")


if __name__ == '__main__':
    main()